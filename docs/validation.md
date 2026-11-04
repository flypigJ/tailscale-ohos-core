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

The standalone library produced here has not been loaded into a device application during this extraction. Its successful compilation is not a connectivity, DNS, exit-node, Taildrop or background-lifecycle acceptance test.

MeshArc's earlier K7 acceptance used its own compiler/package identities. Those historical checks motivated the extraction, but they do not certify this newly built standalone library. A consumer must validate packaging, VPN permissions, route protection, account/state migration and real traffic using its own signed application.

There is no full signed sample HAP and no exported automatic rollback utility. [The C smoke example](../examples/smoke.c) is a minimal loader/ownership check; [Integration](integration.md) explains the application responsibilities and state-restoration limits.
