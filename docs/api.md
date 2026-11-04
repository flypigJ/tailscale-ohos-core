# C interface reference

This document describes the 41 exports in [tailscale_ohos.h](../include/tailscale_ohos.h). It documents the inherited MeshArc contract at the pinned revision, not a new protocol version. Follow [Integration](integration.md) for startup, TUN ownership and state recovery.

## Common rules

- Inputs are NUL-terminated UTF-8 strings, valid throughout the synchronous call. JSON numbers carrying identifiers and byte counts originate from Go `int64`; consumers must avoid JavaScript precision loss.
- Every returned `char *`, including errors and empty strings, must be copied and released once with `TSFreeString`. The library retains no ownership of the caller's input strings.
- Calls can block on locks, I/O or network requests. Run them off the UI thread. A successful start response means startup was requested; poll state and verify real traffic separately.
- Text status generally begins with `OK`, `FAILED`, `PENDING` or `STOPPED`, with `|` separators. An `OK` prefix alone is not evidence of authentication or traffic readiness. JSON operations use their own `state`/`reason` fields; do not apply one parser to every export.
- Account, peer, file and authentication results can contain private information. Do not log whole responses or attach them unredacted to issues. Treat unknown JSON fields as additive and unknown states as unsupported, not successful.

## Identity, lifecycle and authentication

| Export | Inputs and result |
| --- | --- |
| `TSHello` | No arguments. Human-readable downstream Go identity and platform; no network check |
| `TSTailscaleVersion` | No arguments. Tailscale version string |
| `TSBackendStart` | Absolute private `stateDir`, `deviceModel`, `osVersion`, `controlURL`. Returns text startup status; creates/opens persisted state |
| `TSBackendRestartWithTun` | Same four strings plus valid platform `fd`. Duplicates the descriptor and restarts with external TUN; returns text status |
| `TSBackendStop` | No arguments. Stops the backend and returns text status; not account logout |
| `TSBackendLogout` | No arguments. Requests logout and local preference cleanup; returns text status |
| `TSBackendStatus` | No arguments. Text state and diagnostics, including `state=`, `tun=`, traffic counters and startup phase when available |
| `TSBackendSnapshot` | No arguments. JSON containing `status`, `exitNodes`, `peers`, `networkSettings`, `account`, `taildrop`, `taildrive`, `meshArcReceiver` |
| `TSBackendAuthURL` | No arguments. Returns an HTTP(S) login URL, `PENDING` text or `FAILED` text. Polling can start interactive login once per backend generation |
| `TSBackendLoginWithAuthKey` | `authKey`: a device authentication key. Management/API and OAuth client keys are rejected. Returns text; `needs_approval` is not authenticated traffic readiness |
| `TSBackendAccount` | No arguments. Account JSON: display/login names, profile picture URL, Tailnet/device names, addresses, approval and expiry state |
| `TSFreeString` | One library-returned pointer; returns `void`. NULL is accepted by the underlying C allocator |

The caller selects the control server explicitly. Reuse the same absolute private directory and control URL for a persisted identity. Do not run two processes against that identity. Do not store an authentication key in a sample project or public build configuration.

## VPN, preferences and peers

| Export | Inputs and result |
| --- | --- |
| `TSBackendVPNConfig` | No arguments. On success, `IPv4\|IPv6\|comma-separated-CIDR-routes`; IPv6 may be empty. On failure, `FAILED` text. This is not JSON and does not configure platform DNS |
| `TSBackendNetworkSettings` | No arguments. JSON booleans `routeAll` and `exitNodeAllowLANAccess` |
| `TSBackendSetNetworkSetting` | `key`: `routeAll` or `exitNodeAllowLANAccess`; `enabled`: zero/one. Returns text status and persists the preference |
| `TSBackendExitNodes` | No arguments. JSON array of `{id,name,online,selected}`; unavailable state can produce an empty array |
| `TSBackendSetExitNode` | `id` from the exit-node list; an empty string disables selection. Returns text status; app routes still need updating |
| `TSBackendPeers` | No arguments. JSON array with stable `key`, display metadata, addresses, online/exit/expiry state and LocalSend status |
| `TSBackendNetworkChanged` | `interfaceName`: the host-selected interface. Returns text refresh status; does not change the system's default network |
| `TSBackendPeerProbe` | No arguments. TSMP diagnostic against an eligible peer; text status, not application-protocol reachability |
| `TSBackendPeerConnectivity` | `peerKey` from the peer list. JSON with state/reason, sent/received/loss counts, latency metrics, path type and relay region |
| `TSBackendLocalSendRefresh` | No arguments. Refreshes peer service information; text status; performs network work |
| `TSBackendSunshineProbe` | `peerKey`. JSON with state, check time, latency and optional server metadata/error category |
| `TSBackendMediaServiceProbe` | `peerKey`. JSON with state, check time and discovered media services (`type`, `name`, `url`, optional version/latency) |

Peer keys are opaque values returned by this bridge, not authentication keys. Byte counters are bytes, latency fields ending in `Ms` are milliseconds, and timestamps ending in `Ms` are Unix milliseconds. Neither a diagnostic response nor a selected exit-node preference proves platform routing works.

## File operations

These operations can transfer or delete files. The application must obtain the user's intent, constrain local paths to its private storage and handle cancellations from another worker. Send/download/upload calls perform the transfer synchronously; poll snapshots independently if progress is needed.

| Export | Input and result |
| --- | --- |
| `TSBackendTaildropSend` | JSON `taildropSendRequest`; returns transfer JSON |
| `TSBackendTaildropCancel` | No arguments. Cancels the tracked send and returns its transfer snapshot |
| `TSBackendTaildropIncomingSnapshot` | No arguments. JSON array of incoming file name, declared size, received bytes and start time |
| `TSBackendTaildropReceive` | JSON `taildropReceiveRequest`; returns action result with request ID, state/reason, name, size and local path |
| `TSBackendTaildriveList` | JSON `{"path":"/"}` or a valid remote path; returns state, normalized path, entries and optional reason |
| `TSBackendTaildriveStat` | JSON with `path`; returns state, entry metadata and optional reason |
| `TSBackendTaildriveMutate` | JSON with `operation`, `path`, optional `newPath`/`overwrite`; operations are `mkdir`, `delete`, `rename`, `move` |
| `TSBackendTaildriveDownload` | JSON `taildriveTransferRequest`; tracked download, returns transfer JSON |
| `TSBackendTaildriveManualDownload` | Same request; an independent manual download outside the single tracked preview slot. Its progress is not represented by that slot |
| `TSBackendTaildriveUpload` | JSON `taildriveTransferRequest`; tracked upload, returns transfer JSON |
| `TSBackendTaildriveTransferSnapshot` | No arguments. Current tracked transfer JSON; idle when no transfer has started |
| `TSBackendTaildriveCancel` | No arguments. Cancels the tracked transfer and returns its snapshot; does not promise cancellation of an independent manual download |

Request fields are defined in [backend.go](../backend.go) and [taildrive.go](../taildrive.go):

| Request | Fields |
| --- | --- |
| `taildropSendRequest` | Integer `requestId`, opaque `targetKey`, absolute `outboxRoot`, `files` array of `{path,name,size}`. Sizes are bytes |
| `taildropReceiveRequest` | Integer `requestId`, `action` (`stage`, `delete`, `clear`), `name`, `inboxRoot`, `path`; required fields depend on the action |
| `taildriveTransferRequest` | Integer `requestId`, `remotePath`, absolute `localRoot`, `localPath`; optional `sourceModifiedAtMs` and `overwrite` |

For Taildrop receive, `stage` requires `path` to equal `<inboxRoot>/<requestId>.taildrop`; the application subsequently exports the staged file. `delete` accepts the name with empty root/path, and `clear` requires empty name/root/path. Request IDs must be positive.

Remote paths are validated WebDAV paths, not arbitrary external URLs. Local roots and paths must satisfy the bridge's confinement checks. Use names and opaque identifiers returned by the corresponding listing; do not construct them from display labels. File transfer snapshots include `state`, `reason`, request identity and progress. A `queued` or `transferring` result is not completion.

## Diagnostics

| Export | Input and result |
| --- | --- |
| `TSBackendPathDiagnostic` | JSON command; returns a schema-1 diagnostic envelope with result, build identity and trace |
| `TSControlProbe` | No arguments. Starts/polls DNS/TLS diagnostics for `controlplane.tailscale.com`; text result. It does not test a custom control URL |
| `TSProbeEngine` | No arguments. Creates and closes a diagnostic userspace engine; text result. It is not backend login or a connectivity test |
| `TSTunFDProbe` | Valid platform `fd`; adapts and closes a duplicate. Text result; caller retains original descriptor ownership |
| `TSMediaProbeSelfTest` | No arguments. Runs built-in media response classification checks; JSON with `state` and `cases`, not a real peer check |

For path capture, send `{"action":"start","seconds":30}` only after explicit diagnostic consent and an active external-TUN backend. Other actions are `snapshot`, `stop`, `clear`, `probe` and `host`. `probe` performs bounded active network diagnostics and is rate limited. `host` accepts the integration's network/protection metadata; see [path_diagnostics.go](../path_diagnostics.go) for the numeric field contract. Do not populate these fields with guessed platform state.

Capture is diagnostic data, not general application telemetry. Review/redact any exported report before sharing it. The build source identifier comes from the verified build receipt; it is never an account key.
