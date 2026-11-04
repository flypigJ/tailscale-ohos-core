# Integrate the C ABI

This guide describes the existing bridge contract. It is not a complete signed HAP template. The consumer supplies Stage-model abilities, permissions, signing and lifecycle handling.

## Ownership

All returned `char *` values are allocated by the Go library. Copy the value before calling `TSFreeString` exactly once. Input strings must remain valid for the duration of the synchronous C call. Never free a returned string with the host application's allocator.

The backend is a process-wide singleton. Use one VPN-owning process per node identity. Stop the old backend before transferring ownership. Do not use `dlclose` while any Go runtime, callback or worker is alive.

## Connection sequence

1. Call `TSHello` and `TSTailscaleVersion` to identify the loaded library. These are not connectivity checks.
2. Call `TSBackendStart` with an absolute app-private state directory, device description, OS version and explicitly chosen control URL.
3. Poll `TSBackendAuthURL`/`TSBackendStatus` without logging authentication URLs or keys. Open interactive authentication in the application's normal browser flow; auth-key login is an explicit alternative.
4. Obtain assigned addresses and route information using `TSBackendVPNConfig`. Do not create a VPN from placeholder addresses.
5. In the VPN Extension, obtain user authorization and create the system VPN configuration. The application owns system addresses/routes and must prevent control/DERP traffic from looping through its own tunnel.
6. Pass the descriptor returned by the platform to `TSBackendRestartWithTun`. The bridge duplicates it; the caller retains ownership of its original descriptor. Check the returned status.
7. Validate real traffic. `Running` or a successful ping alone does not prove application traffic, DNS, exit-node or subnet behavior.
8. Stop via `TSBackendStop` and tear down the platform VPN under the application's lifecycle policy.

Use an asynchronous N-API worker for operations that can block. A worker completing after a UI page closes must not update a stale page/session. Do not infer safe concurrency from the C interface alone.

## Interface groups

| Group | C exports / behavior |
| --- | --- |
| Identity and lifecycle | `TSBackendStart`, `TSBackendStop`, `TSBackendLogout`, `TSBackendRestartWithTun` |
| Authentication/status | `TSBackendAuthURL`, `TSBackendLoginWithAuthKey`, `TSBackendStatus`, `TSBackendSnapshot` |
| Routes and peers | `TSBackendVPNConfig`, `TSBackendPeers`, `TSBackendExitNodes`, settings and exit-node setters |
| File operations | `TSBackendTaildrop*`, `TSBackendTaildrive*`; request/response JSON remains MeshArc's established contract |
| Service and path checks | LocalSend, Sunshine, media and path diagnostics; the caller chooses targets and controls consent |
| Memory | `TSFreeString` |

The full signatures are in [the header](../include/tailscale_ohos.h). Response formats include both status strings and JSON; this preview does not promise a new uniformly versioned SDK protocol. See [C interface reference](api.md) for all 41 exports, response types and request fields; consult the corresponding Go function for exact validation rules.

## State migration and recovery

State is isolated by the control URL. First use of the upgraded engine creates a private backup and marker and holds an exclusive lease. A corrupt backup/marker stops startup. State and keys must remain inside the application sandbox.

Installing an older binary is not a state rollback. After new-engine writes, stop all processes and perform app-owned offline restoration using the validated backup procedure before an old-engine launch. The internal restoration function is tested but is not exported as a public recovery command. This preview does not ship a one-click recovery application.

## Minimal loading example

[examples/smoke.c](../examples/smoke.c) checks library loading and string ownership without logging in or modifying account state. Compile it with the matching SDK C compiler and run only in an authorized target environment. A desktop host cannot execute an arm64 HarmonyOS library.

The complete application reference remains [MeshArc](https://github.com/flypigJ/Tailscale-OHOS); its product-specific UI and recovery policy are intentionally outside this core repository.
