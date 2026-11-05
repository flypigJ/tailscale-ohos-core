# Validation record

This record covers the initial standalone developer preview, prepared on 2026-11-05 (Asia/Shanghai). It separates bridge behavior, target compilation and device integration.

## Inputs

[source.json](../source.json) identifies Tailscale 1.104.5 at `73a48057aaf5f60e4f770b398e9b7af576b01dbe`, both adaptation patches, all changed dependency files and the exact downstream Go checkout. [extraction.json](extraction.json) records the MeshArc source snapshot and the extracted files, including the module-path change. The original dirty working tree is not represented as a clean upstream commit.

## Checks and evidence

Run commands from the repository root, with prerequisites from [Build](build.md).

| Check | Environment | Evidence |
| --- | --- | --- |
| `python scripts/manage.py prepare` and `verify` | Windows Git | Exact upstream commit, patch hashes and resulting source hashes checked |
| `python -m unittest discover -s tests -v` | Windows Python 3.12 | Build helper and upstream-monitor regressions |
| `python3 scripts/manage.py test --go-root <official-go-root>` | Linux/amd64 under WSL, official Go 1.27.3, CGO disabled | [Host result](evidence/linux-host-tests.json) |
| `python scripts/manage.py build --go-root <pinned-go-root> --sdk <native-sdk>` | Windows/amd64, API 26 native SDK `26.0.0.105` | [Native build result](evidence/windows-native-build.json), including 41 C declarations and binary metadata |

58 top-level Go tests passed (86 results including subtests), with zero failures or skips. The native check also verifies actual ELF exports/TLS and compiles the C smoke client with warnings treated as errors.

The Linux tests exercise lifecycle, route selection, state backup/leases and file-service behavior. The platform C entry file is excluded with CGO disabled. The native build is a separate check of that entry file, linker and public header.

[GitHub Actions](https://github.com/flypigJ/tailscale-ohos-core/actions/workflows/core.yml) repeats preparation and host tests from a clean checkout. Consult its exact commit and conclusion; do not infer a remote CI result from a local receipt. GitHub-hosted CI does not bundle the Huawei SDK or sign/install an application.

## Device boundary

A supplemental HDC-shell attempt on API 26 (`OpenHarmony-7.0.0.111`, arm64) verified all transferred binary hashes, but the Go example loader could not execute: permission denied, exit 126, despite `0755` mode and shell ownership. The run stopped before trying the core loader. [The receipt](evidence/device-shell-attempt.json) records this as blocked; temporary files were removed. That historical restriction remains recorded; the following application-context check uses a signed Debug feature HAP.

On 2026-11-05, the newly built standalone core and Go example both executed inside a signed Debug feature HAP on that device. Each library passed three cold-process runs, with four native threads and 400 CGO callbacks per run (1,200 callbacks per library, zero failures). The core resolved all 41 exports, matched Tailscale 1.104.5, reported a stopped backend, passed the four-case media self-test, and created/closed the userspace engine without login.

The [HAP receipt](evidence/device-hap-probe.json) records exact source/compiler/library/package hashes and each run's result and process ID; the [probe log](evidence/device-hap-probe.log) records all six BEGIN/RESULT pairs. Hvigor's packaged libraries matched independently stripped inputs byte for byte. The temporary feature was removed afterward, the entry module metadata and selected app identity/state fields were unchanged, and the normal application was reopened. This comparison is not a byte-for-byte audit of all application data.

This is a bounded loading/CGO/engine check. It is not a connectivity, DNS, exit-node, Taildrop or background-lifecycle acceptance test.

MeshArc's earlier K7 acceptance used its own compiler/package identities. Those historical checks motivated the extraction, but they do not certify this newly built standalone library. A consumer must validate packaging, VPN permissions, route protection, account/state migration and real traffic using its own signed application.

The tested [HAP probe sources and reproduction steps](../examples/hap-probe/README.md) are published. There is no distributable signed HAP, complete DevEco sample project or exported automatic rollback utility. [The C smoke example](../examples/smoke.c) is a minimal loader/ownership check; [Integration](integration.md) explains the application responsibilities and state-restoration limits.
