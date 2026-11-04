# Sources and attribution

- Bridge and lifecycle code: extracted from [MeshArc / Tailscale-OHOS](https://github.com/flypigJ/Tailscale-OHOS), including its uncommitted K7 integration snapshot. The extraction manifest records file digests; it is not represented as an upstream Git commit.
- Tailscale: version 1.104.5, canonical commit recorded in `source.json`; copyright Tailscale Inc and contributors. The original license is preserved in `patches/LICENSE-Tailscale` and in the fetched source.
- Platform integration patch: MeshArc's reviewed 1.104.5 adaptation, including inherited project work. It is not claimed as an official Tailscale patch or as entirely new work in this extraction.
- Cold-peer patch: the external-TUN integration keeps canonical Tailnet destinations on the userspace stack while the peer map arrives. This is a fix for this adaptation; no general upstream vulnerability claim is made.
- Go: requires the separate OpenHarmony port. That repository documents Go and OpenHarmony SIG provenance.
- Go modules and native SDK components retain their own licenses. The SDK is not bundled. This document is not a complete transitive dependency license inventory for a redistributed application package.

No account state, authentication keys, original device identifiers, provisioning profiles or signing keys belong in this repository.
