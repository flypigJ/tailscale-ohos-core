# Tailscale OHOS core

[![Host checks](https://github.com/flypigJ/tailscale-ohos-core/actions/workflows/core.yml/badge.svg?branch=main)](https://github.com/flypigJ/tailscale-ohos-core/actions/workflows/core.yml)

A community Tailscale 1.104.5 C ABI for HarmonyOS applications, extracted from MeshArc.

[中文说明](README.zh-CN.md) · [Build](docs/build.md) · [Integration](docs/integration.md) · [C API](docs/api.md) · [Validation](docs/validation.md) · [Maintenance](docs/maintenance.md)

**Developer preview.** This is a native library, not a complete VPN app or an official Tailscale distribution. The qualified target is **HarmonyOS API 26 / arm64**. Building it requires the separately prepared [OpenHarmony Go port](https://github.com/flypigJ/go-ohos) and Huawei's matching native SDK. A successful host test does not prove device connectivity.

## What this repository provides

- The MeshArc Go bridge, its 41-function C interface and behavioral tests.
- Fixed Tailscale source plus reviewable platform and cold-peer patches; `source.json` records exact commits and content hashes.
- External TUN descriptor integration. The application creates the VPN interface and owns system routes, permissions and lifecycle.
- Taildrop/Taildrive operations, peer information, opt-in path diagnostics and private-state upgrade checks used by MeshArc.

The bridge is a `package main` compiled as `c-shared`; it is not currently an importable Go SDK. Its established MeshArc response formats are retained. DNS configuration, UI, application signing and automatic reconnection remain application responsibilities.

## Start with host tests

Use Linux, Git, Python 3.11+ and official Go 1.27.3:

```bash
git clone https://github.com/flypigJ/tailscale-ohos-core.git
cd tailscale-ohos-core
python3 scripts/manage.py prepare
python3 -m unittest discover -s tests -v
python3 scripts/manage.py test --go-root "$(go env GOROOT)"
```

The preparation command verifies the upstream tag's commit and patch hashes. It never resets an existing dependency checkout. The Linux tests disable CGO and exercise bridge behavior; they do not compile the C entry file.

For the real arm64 shared library, follow [Build the native core](docs/build.md). The outputs are `out/arm64-v8a/libtailscale_go.so`, its generated header and `build.json`.

## Use it in an application

Start with the [C smoke client](examples/smoke.c) and [integration sequence](docs/integration.md). The full reference application is [MeshArc](https://github.com/flypigJ/Tailscale-OHOS). The public header is [include/tailscale_ohos.h](include/tailscale_ohos.h).

Every returned string belongs to the library and must be released with `TSFreeString`. Keep blocking operations off ArkUI's UI thread. Never unload a running Go runtime or run the same persisted node identity in two processes.

## Upstream and maintenance

This repository owns the adaptation and bridge; Tailscale's source remains an independently fetched dependency. Upstream versions are pinned, not taken from a moving branch. Daily monitoring checks both stable tags and `main`; it maintains one tracking issue only when there is drift. Upgrades require reviewed patches and new validation, not an automatic version substitution. See [Maintenance](docs/maintenance.md).

## License and attribution

The bridge is BSD-3-Clause. Tailscale and other dependencies retain their own notices. See [NOTICE.md](NOTICE.md). This community project is not affiliated with or endorsed by Tailscale or Huawei. Commercial SDKs, credentials and provisioning profiles are not distributed here.
