package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/sys/unix"
)

func TestStopReleasesProductionStateLease(t *testing.T) {
	root := privateUpgradeTestDirectory(t)
	lease, err := prepareEngineStateUpgrade(root)
	if err != nil {
		t.Fatal(err)
	}
	controller := &backendController{engineLease: lease}
	if _, err := acquireEngineStateLease(root); err == nil {
		t.Fatal("active identity lease was not exclusive")
	}
	controller.stop()
	reopened, err := acquireEngineStateLease(root)
	if err != nil {
		t.Fatalf("stop retained the identity lease: %v", err)
	}
	defer reopened.Close()
	if controller.engineLease != nil {
		t.Fatal("stopped controller retains lease")
	}
}

func TestRejectedStateUpgradeClosesTunAndPreservesState(t *testing.T) {
	base := t.TempDir()
	profile := controlServerStateDir(base, "https://controlplane.tailscale.com")
	if err := os.MkdirAll(profile, 0700); err != nil {
		t.Fatal(err)
	}
	marker := filepath.Join(profile, engineUpgradeMarker)
	if err := os.WriteFile(marker, []byte("invalid-existing-marker"), 0600); err != nil {
		t.Fatal(err)
	}
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	defer writer.Close()
	device, err := newHarmonyTunDevice(int(reader.Fd()), 1280)
	if err != nil {
		t.Fatal(err)
	}
	fd := int(device.file.Fd())
	controller := &backendController{}
	result := controller.startWithDevice(base, "test", "https://controlplane.tailscale.com", device)
	if result != "FAILED | backend start | private state upgrade" || controller.server != nil || controller.engineLease != nil {
		t.Fatal("unverified state reached server startup")
	}
	if _, err := unix.FcntlInt(uintptr(fd), unix.F_GETFD, 0); err != unix.EBADF {
		t.Fatal("rejected duplicate TUN retained")
	}
	if bytes, err := os.ReadFile(marker); err != nil || string(bytes) != "invalid-existing-marker" {
		t.Fatal("existing state marker overwritten")
	}
	lease, err := acquireEngineStateLease(profile)
	if err != nil {
		t.Fatal("failed upgrade leaked identity lock")
	}
	lease.Close()
}

func TestRejectedStartClosesUnclaimedTun(t *testing.T) {
	for _, scenario := range []string{"invalid-control", "already-starting"} {
		t.Run(scenario, func(t *testing.T) {
			reader, writer, err := os.Pipe()
			if err != nil {
				t.Fatal(err)
			}
			defer reader.Close()
			defer writer.Close()
			device, err := newHarmonyTunDevice(int(reader.Fd()), 1280)
			if err != nil {
				t.Fatal(err)
			}
			defer device.Close()
			fd := int(device.file.Fd())
			controller := &backendController{}
			control := "not-a-url"
			if scenario == "already-starting" {
				controller.starting = true
				control = "https://controlplane.tailscale.com"
			}
			result := controller.startWithDevice(t.TempDir(), "test", control, device)
			if scenario == "invalid-control" && !strings.HasPrefix(result, "FAILED") {
				t.Fatal(result)
			}
			if _, err := unix.FcntlInt(uintptr(fd), unix.F_GETFD, 0); err != unix.EBADF {
				t.Fatalf("unclaimed duplicate still open: %v", err)
			}
			if _, err := reader.Stat(); err != nil {
				t.Fatalf("caller descriptor was closed: %v", err)
			}
		})
	}
}
