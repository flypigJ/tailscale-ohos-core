package main

import (
	"bytes"
	"errors"
	"io"
	"testing"

	"github.com/tailscale/wireguard-go/tun"
	"golang.org/x/sys/unix"
)

func TestHarmonyTunSlabReadPreservesSpacingAndDescriptor(t *testing.T) {
	fds, err := unix.Socketpair(unix.AF_UNIX, unix.SOCK_DGRAM, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer unix.Close(fds[0])
	defer unix.Close(fds[1])
	d, err := newHarmonyTunDevice(fds[0], 1280)
	if err != nil {
		t.Fatal(err)
	}
	defer d.Close()
	payload := []byte{0x60, 1, 2, 3, 4, 5, 6, 7}
	if _, err := unix.Write(fds[1], payload); err != nil {
		t.Fatal(err)
	}
	slab := bytes.Repeat([]byte{0xa5}, len(payload)+2*tun.ReadPacketSpacing)
	packets := make([]tun.ReadPacket, d.BatchSize())
	n, err := d.Read(slab, packets)
	if err != nil || n != 1 {
		t.Fatalf("Read = %d, %v", n, err)
	}
	p := packets[0]
	if p.Offset != tun.ReadPacketSpacing || p.Size != len(payload) || !bytes.Equal(slab[p.Offset:p.Offset+p.Size], payload) {
		t.Fatal("slab packet boundary or payload changed")
	}
	if !bytes.Equal(slab[:p.Offset], bytes.Repeat([]byte{0xa5}, tun.ReadPacketSpacing)) ||
		!bytes.Equal(slab[p.Offset+p.Size:], bytes.Repeat([]byte{0xa5}, tun.ReadPacketSpacing)) {
		t.Fatal("WireGuard headroom or tailroom was overwritten")
	}
	if d.readCount.Load() != 1 || d.readByteCount.Load() != uint64(len(payload)) {
		t.Fatal("TUN counters changed semantics")
	}
	if err := d.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := unix.FcntlInt(uintptr(fds[0]), unix.F_GETFD, 0); err != nil {
		t.Fatal("closed the platform-owned descriptor")
	}
}

func TestHarmonyTunSlabReadRejectsInvalidBuffers(t *testing.T) {
	d := &harmonyTunDevice{}
	for _, size := range []int{0, 1, 2*tun.ReadPacketSpacing - 1, 2 * tun.ReadPacketSpacing} {
		if n, err := d.Read(make([]byte, size), make([]tun.ReadPacket, 1)); n != 0 || err == nil {
			t.Fatalf("accepted slab size %d", size)
		}
	}
	if n, err := d.Read(make([]byte, 512), nil); n != 0 || err == nil {
		t.Fatal("accepted missing packet metadata")
	}
}

type scriptedTunWrite struct {
	steps  []scriptedTunWriteStep
	output []byte
}

type scriptedTunWriteStep struct {
	count int
	err   error
}

type scriptedTunRead struct {
	steps []scriptedTunReadStep
}

type scriptedTunReadStep struct {
	data []byte
	err  error
}

func (r *scriptedTunRead) Read(packet []byte) (int, error) {
	if len(r.steps) == 0 {
		return 0, io.EOF
	}
	step := r.steps[0]
	r.steps = r.steps[1:]
	return copy(packet, step.data), step.err
}

func (w *scriptedTunWrite) Write(packet []byte) (int, error) {
	if len(w.steps) == 0 {
		return 0, io.ErrNoProgress
	}
	step := w.steps[0]
	w.steps = w.steps[1:]
	if step.count > len(packet) {
		step.count = len(packet)
	}
	w.output = append(w.output, packet[:step.count]...)
	return step.count, step.err
}

func TestReadTunPacketRetriesTransientErrors(t *testing.T) {
	reader := &scriptedTunRead{
		steps: []scriptedTunReadStep{
			{err: unix.EAGAIN},
			{err: unix.EINTR},
			{data: []byte("packet")},
		},
	}

	packet := make([]byte, 16)
	read, err := readTunPacket(reader, packet)
	if err != nil {
		t.Fatalf("readTunPacket returned error: %v", err)
	}
	if got := string(packet[:read]); got != "packet" {
		t.Fatalf("readTunPacket returned %q, want packet", got)
	}
}

func TestWriteTunPacketCompletesShortAndTransientWrites(t *testing.T) {
	writer := &scriptedTunWrite{
		steps: []scriptedTunWriteStep{
			{count: 2},
			{err: unix.EAGAIN},
			{count: 3},
		},
	}

	packet := []byte("hello")
	written, err := writeTunPacket(writer, packet)
	if err != nil {
		t.Fatalf("writeTunPacket returned error: %v", err)
	}
	if written != len(packet) {
		t.Fatalf("writeTunPacket wrote %d bytes, want %d", written, len(packet))
	}
	if string(writer.output) != string(packet) {
		t.Fatalf("writeTunPacket output %q, want %q", writer.output, packet)
	}
}

func TestWriteTunPacketRejectsNoProgress(t *testing.T) {
	writer := &scriptedTunWrite{
		steps: []scriptedTunWriteStep{{count: 0}},
	}
	if _, err := writeTunPacket(writer, []byte("packet")); !errors.Is(err, io.ErrNoProgress) {
		t.Fatalf("writeTunPacket error = %v, want io.ErrNoProgress", err)
	}
}
