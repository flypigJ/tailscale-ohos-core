package main

import (
	"errors"
	"io"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/tailscale/wireguard-go/tun"
	"golang.org/x/sys/unix"
)

// harmonyTunDevice adapts the raw IP packet descriptor returned by
// vpnExtension.VpnConnection.create to wireguard-go's tun.Device interface.
// HarmonyOS owns interface creation and routing, so Linux TUN ioctls and
// netlink monitoring are intentionally not used here.
type harmonyTunDevice struct {
	file             *os.File
	mtu              int
	events           chan tun.Event
	closeOnce        sync.Once
	readCount        atomic.Uint64
	writeCount       atomic.Uint64
	readByteCount    atomic.Uint64
	writeByteCount   atomic.Uint64
	readErrorCount   atomic.Uint64
	writeErrorCount  atomic.Uint64
	trafficSession   uint64
	dnsQueryCount    atomic.Uint64
	dnsResponseCount atomic.Uint64
	dnsAnswerCount   atomic.Uint64
}

func newHarmonyTunDevice(fd, mtu int) (*harmonyTunDevice, error) {
	if fd < 0 {
		return nil, errors.New("invalid TUN descriptor")
	}
	duplicate, err := unix.Dup(fd)
	if err != nil {
		return nil, err
	}
	// wireguard-go's TUN reader treats any read error other than its own
	// special cases as fatal. In particular, it closes the device on EAGAIN.
	// Harmony's VPN descriptor may be returned as non-blocking, so explicitly
	// clear O_NONBLOCK on our duplicate and let the reader block for the next
	// packet. This also prevents a busy-loop while the tunnel is idle.
	if err := unix.SetNonblock(duplicate, false); err != nil {
		_ = unix.Close(duplicate)
		return nil, err
	}
	device := &harmonyTunDevice{
		file:           os.NewFile(uintptr(duplicate), "harmony-vpn-tun"),
		mtu:            mtu,
		events:         make(chan tun.Event, 2),
		trafficSession: uint64(time.Now().UnixMilli()),
	}
	device.events <- tun.EventUp
	return device, nil
}

func (d *harmonyTunDevice) File() *os.File { return d.file }

func (d *harmonyTunDevice) Read(slab []byte, packets []tun.ReadPacket) (int, error) {
	// The upstream slab API reserves headroom and tailroom around each packet.
	// Our single-queue descriptor still produces one complete IP packet per read.
	const spacing = tun.ReadPacketSpacing
	if len(packets) == 0 || len(slab) <= 2*spacing {
		return 0, errors.New("invalid TUN read buffer")
	}
	packets[0] = tun.ReadPacket{}
	buffer := slab[spacing : len(slab)-spacing]
	n, err := readTunPacket(d.file, buffer)
	if n > 0 {
		packets[0] = tun.ReadPacket{Offset: spacing, Size: n}
		d.readCount.Add(1)
		d.readByteCount.Add(uint64(n))
		d.observeDNSPacket(buffer[:n], true)
		return 1, nil
	}
	if err != nil && !isRetriableTunError(err) {
		d.readErrorCount.Add(1)
	}
	return 0, err
}

func (d *harmonyTunDevice) Write(bufs [][]byte, offset int) (int, error) {
	written := 0
	for _, buf := range bufs {
		if offset < 0 || offset > len(buf) {
			return written, errors.New("invalid TUN write buffer")
		}
		packet := buf[offset:]
		n, err := writeTunPacket(d.file, packet)
		if err != nil {
			if !isRetriableTunError(err) {
				d.writeErrorCount.Add(1)
			}
			return written, err
		}
		if n != len(packet) {
			d.writeErrorCount.Add(1)
			return written, io.ErrShortWrite
		}
		d.writeCount.Add(1)
		d.writeByteCount.Add(uint64(n))
		d.observeDNSPacket(packet, false)
		written++
	}
	return written, nil
}

func readTunPacket(reader io.Reader, packet []byte) (int, error) {
	for {
		n, err := reader.Read(packet)
		if err != nil && isRetriableTunError(err) {
			// A blocking descriptor should not normally produce EAGAIN, but
			// never hand a transient interruption to wireguard-go as a
			// device-fatal read error.
			continue
		}
		return n, err
	}
}

// writeTunPacket preserves packet boundaries even when the underlying VPN
// descriptor accepts only a partial write. A short write must never be
// reported as a successfully written packet: doing so would silently drop
// the rest of a decrypted TCP segment.
func writeTunPacket(writer io.Writer, packet []byte) (int, error) {
	written := 0
	for written < len(packet) {
		n, err := writer.Write(packet[written:])
		if n > 0 {
			written += n
		}
		if err != nil {
			if isRetriableTunError(err) {
				continue
			}
			return written, err
		}
		if n == 0 {
			return written, io.ErrNoProgress
		}
	}
	return written, nil
}

func (d *harmonyTunDevice) MTU() (int, error) { return d.mtu, nil }

func (d *harmonyTunDevice) Name() (string, error) { return "tailscale0", nil }

func (d *harmonyTunDevice) Events() <-chan tun.Event { return d.events }

func (d *harmonyTunDevice) Close() error {
	var err error
	d.closeOnce.Do(func() {
		d.events <- tun.EventDown
		close(d.events)
		err = d.file.Close()
	})
	return err
}

func (d *harmonyTunDevice) BatchSize() int { return 1 }

func (d *harmonyTunDevice) packetCounts() (read uint64, written uint64) {
	return d.readCount.Load(), d.writeCount.Load()
}

// trafficCounts reports bytes for the current VPN TUN lifetime. Reading from
// the TUN is device upload; writing decrypted packets back is device download.
func (d *harmonyTunDevice) trafficCounts() (txBytes uint64, rxBytes uint64, session uint64) {
	return d.readByteCount.Load(), d.writeByteCount.Load(), d.trafficSession
}

func (d *harmonyTunDevice) errorCounts() (readErrors uint64, writeErrors uint64) {
	return d.readErrorCount.Load(), d.writeErrorCount.Load()
}

func isRetriableTunError(err error) bool {
	return errors.Is(err, unix.EAGAIN) ||
		errors.Is(err, unix.EWOULDBLOCK) ||
		errors.Is(err, unix.EINTR)
}

func (d *harmonyTunDevice) dnsCounts() (queries uint64, responses uint64, answers uint64) {
	return d.dnsQueryCount.Load(), d.dnsResponseCount.Load(), d.dnsAnswerCount.Load()
}

// observeDNSPacket records only coarse DNS counters. It deliberately does not
// retain query names, addresses, transaction IDs, or packet payloads.
func (d *harmonyTunDevice) observeDNSPacket(packet []byte, fromSystem bool) {
	if len(packet) < 20 || packet[0]>>4 != 4 {
		return
	}
	headerLength := int(packet[0]&0x0f) * 4
	if headerLength < 20 || len(packet) < headerLength+8+12 || packet[9] != 17 {
		return
	}
	udp := packet[headerLength:]
	sourcePort := uint16(udp[0])<<8 | uint16(udp[1])
	destinationPort := uint16(udp[2])<<8 | uint16(udp[3])
	dns := udp[8:]
	isResponse := dns[2]&0x80 != 0
	if fromSystem && destinationPort == 53 && !isResponse {
		d.dnsQueryCount.Add(1)
		return
	}
	if !fromSystem && sourcePort == 53 && isResponse {
		d.dnsResponseCount.Add(1)
		answerCount := uint16(dns[6])<<8 | uint16(dns[7])
		if answerCount > 0 {
			d.dnsAnswerCount.Add(1)
		}
	}
}

var _ tun.Device = (*harmonyTunDevice)(nil)
