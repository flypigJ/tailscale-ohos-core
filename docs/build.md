# Build the native core

## Prerequisites

- Git and Python 3.11 or newer.
- The `flypigJ/go-ohos` source commit named by `toolchain_commit` in [source.json](../source.json), bootstrapped using that repository's instructions. Its compiler identifies itself as `go1.27.3-ohos-devel`.
- Huawei's **API 26 Release native SDK**, containing `oh-uni-package.json`, `llvm/bin` and `sysroot`. SDK release type is unrelated to the app's Debug/Release signing mode.
- Network access for pinned Go modules and the initial Tailscale checkout.

Windows/amd64 is the initial native-build qualification environment. Linux is used for bridge host tests. Other host builds need their own recorded qualification; the Python scripts being portable is not proof of a successful macOS native build.

## Prepare dependencies

From this repository's root:

```text
python scripts/manage.py prepare
python scripts/manage.py verify
```

The source commit and patch contents are verified before compilation. Existing dependency edits stop the process. To investigate, run `git -C .deps/tailscale status`; preserve your work before preparing a separate fresh clone. Do not blindly reset or delete a failed dependency directory.

## Cross-compile on Windows

The following assumes the two public repositories are siblings and DevEco Studio is installed at its standard location:

```powershell
$goRoot = (Resolve-Path ../go-ohos).Path
$nativeSdk = 'C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/native'
python scripts/manage.py build --go-root $goRoot --sdk $nativeSdk
```

The script validates the Go source commit, runtime/compiler source manifest, compiler binary receipts, identity and SDK baseline. It builds with `GOTOOLCHAIN=local`, `GOENV=off`, `GOWORK=off`, readonly modules, `GOOS=openharmony`, `GOARCH=arm64` and CGO. It does not modify persistent Go settings or install an app.

| Output | Use |
| --- | --- |
| `out/arm64-v8a/libtailscale_go.so` | Unstripped native library; retain for debugging |
| `out/arm64-v8a/libtailscale_go.h` | Generated C ABI; checked against the public header |
| `out/arm64-v8a/smoke` | SDK-compiled minimal loader; execution is a separate device step |
| `out/arm64-v8a/build.json` | Input identity, source and binary hashes, SDK and result |

Do not reuse an old `build.json` after a failed build. A failed compilation writes a failed receipt. A new binary requires new symbol/package matching and device verification in its consuming application.

## Test separately from cross-compilation

```bash
python3 -m unittest discover -s tests -v
python3 scripts/manage.py test --go-root "$(go env GOROOT)"
```

Run these on Linux with official Go 1.27.3. CGO is disabled so the bridge tests do not require the platform-only C entry file. They cover state backup/locking, lifecycle, routing and file-service behavior. They do not execute HarmonyOS system APIs.

## Common failures

| Failure | Action |
| --- | --- |
| Wrong toolchain commit or identity | Check out the pinned Go commit and bootstrap it; stock Go cannot substitute |
| Source digest or patch set differs | Inspect local changes; do not edit the lock merely to suppress the error |
| SDK baseline rejected | Point `--sdk` at the complete API 26 native SDK, not its parent directory |
| Module download failed | Restore network access and rerun; no automatic dependency upgrade is performed |
| Build succeeds, app cannot load | Inspect native dependencies, package symbols and target loader behavior; host checks do not establish device support |
