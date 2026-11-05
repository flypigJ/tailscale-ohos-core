# Run the libraries in a signed Debug application

This is the probe source used for the [2026-11-05 device check](../../docs/validation.md). It loads either the Go example or the Tailscale core on a N-API worker, then calls Go from four native threads. It does not log in, start the backend, create a VPN interface, or open persisted account state.

Use a dedicated development application with your own bundle identity and Debug signing profile. These files are a feature-module source example, not a complete DevEco project or a distributable HAP. No signing material is included. Never install a test feature into someone else's application.

## Prepare the application

Prerequisites are the [native build](../../docs/build.md), the Go repository's `sdk-smoke` output, DevEco Studio with API 26, and an authorized arm64 device. The recorded build used Hvigor 6.26.1 and native SDK 26.0.0.105.

1. Create a Stage-model native C++ development application and a feature module named `portprobe`. Keep its entry module minimal: no other Go runtime or background service should load during a probe.
2. Copy this directory's `src/main/` into the feature module. Provide the application's usual `AppScope/resources/base/media/app_icon` resource; the supplied manifest references it. Register the feature in the root `build-profile.json5` as `name: "portprobe"`, with its actual module directory as `srcPath` and the default product/target. Set the feature's `externalNativeOptions.path` to `./src/main/cpp/CMakeLists.txt`. Use a Debug build and your own valid local signing configuration.
3. Add `"libportprobe.so": "file:./src/main/cpp/types/libportprobe"` to the feature's `oh-package.json5` dependencies. The included declaration exposes `run(mode: string): Promise<string>`.
4. Copy the Go example's `ohos/out/arm64/libohos_example.so` into the feature's `libs/arm64-v8a/`. Copy this repository's `out/arm64-v8a/libtailscale_go.so` into the same directory as **`libportprobe_core.so`**. This changes only its filename. Keep each input SHA-256 and build receipt.
5. Build the feature's Debug HAP with DevEco/Hvigor, verify its signature/profile and inspect its packaged `module.json`: the module must be `portprobe`, type `feature`, and the ability must be `PortProbeAbility`. Record the packaged libraries' hashes too. Hvigor stripped the libraries in the recorded run; each packaged library matched an independently generated `llvm-strip --strip-all` output byte for byte.

The probe expects `go1.27.3-ohos-devel`, Tailscale `1.104.5` and the current 41-symbol ABI. When qualifying a new version, review these assertions and `exports.inc` against the new header. Do not relax them just to obtain a passing result.

## Execute one mode per process

The commands below run in PowerShell, after assigning `$device` to your connected HDC device, `$bundle` to your development bundle, and `$hap` to the verified Debug feature HAP. Install the development application's entry HAP first. Check `bm dump -n $bundle` before adding the feature; retain its metadata for the cleanup comparison.

```powershell
hdc -t $device install -r $hap
hdc -t $device shell bm dump -n $bundle
$mode = 'go'
$runId = 'probe-' + [guid]::NewGuid().ToString('N')
hdc -t $device shell aa force-stop $bundle
hdc -t $device shell aa start -b $bundle -m portprobe -a PortProbeAbility --ps probeRunId $runId --ps probeMode $mode
hdc -t $device shell hilog -x -T PortProbe
```

Look for exactly one `RESULT` with this run ID within 60 seconds. Repeat the log command while waiting. A command's host exit status alone is insufficient: HDC can print a remote failure while returning zero. Confirm installation/start success and reject errors, duplicate results, missing results or `passed:false`.

Run `go` three times and `core` three times, using a fresh run ID and `aa force-stop` before every start. Each result must come from a distinct process ID. Never run both libraries in the same process. The probe also rejects a second invocation or an already loaded known Go library; it intentionally never calls `dlclose`.

| Result | Go example | Core |
| --- | --- | --- |
| `passed` | `true` | `true` |
| `threads` / `callbacks` / `failures` | `4` / `400` / `0` | `4` / `400` / `0` |
| `exports` | `2` | `41` |
| `versionMatched`, `backendStopped`, `engineInitialized`, `mediaSelfTest` | `null` (not applicable) | all `true` |

The Go hello function checks platform identity and invokes GC on every callback. The core checks its exact Tailscale version, stopped backend, four media self-test cases, and successful creation/closure of the userspace engine without login. `TSHello` checks the compiler identity on every callback. Every returned C string is freed by the library that allocated it.

`not_cold` or `existing_runtime` means the process is unsuitable; fix the application lifecycle and start a fresh process. `dlopen` or `symbols` means loading/ABI resolution failed; inspect packaged library names and device linker logs. A timeout or process death is a failed run requiring diagnosis, not a pass inferred from installation.

## Remove the feature

Run cleanup even after a failed probe. The following command removes only the named test module:

```powershell
hdc -t $device shell aa force-stop $bundle
hdc -t $device shell bm uninstall -n $bundle -m portprobe
hdc -t $device shell bm dump -n $bundle
hdc -t $device shell aa start -b $bundle -m entry -a EntryAbility
```

Confirm `portprobe` is absent and the original entry metadata, version, UID, signer, first-install time and install time are unchanged. A feature installation may change bundle update time. Preserve application state; do not substitute a whole-bundle uninstall. The recorded MeshArc run also compared the connection-intent record before and after testing; it remained disconnected and unchanged. That application-specific check is not supplied as a generic account-data backup utility.

## Evidence and limits

The [receipt](../../docs/evidence/device-hap-probe.json) binds the tested source, compiler, input libraries, stripped packaged libraries and signed HAP to six cold-process results. [The log excerpt](../../docs/evidence/device-hap-probe.log) contains only probe BEGIN/RESULT lines. Signing material, device serials and account data are excluded.

These checks establish application-context loading and a bounded set of CGO/core operations on one API 26 arm64 device. They do not establish VPN traffic, full standard-library support, signal chaining, long-running stability or background lifecycle behavior. See [Integration](../../docs/integration.md) for the remaining application responsibilities.
