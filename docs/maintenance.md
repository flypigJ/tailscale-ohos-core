# Maintain the port

## Update cadence and responsibility

The scheduled GitHub workflow checks stable upstream tags and the main development branch every day. It maintains one tracking issue when the qualified release or observed branch differs. No change means no issue update. A workflow run can also be started manually.

Monitoring is automatic; integration and validation are separate work. This project does not promise an unconditional same-day release or merge untested upstream code. Security releases take priority over new features. A newly opened tracker means triage is needed, not that the new version is supported.

## Review an upstream change

1. Read the upstream release/security notes and compare changes affecting runtime, networking, state and public interfaces.
2. Create a `codex/upstream-<version>` or contributor feature branch from the current qualified revision. Keep the last qualified branch/tag available.
3. Replay platform changes on the exact upstream commit. Resolve conflicts by understanding the new implementation; remove patches already covered upstream.
4. Update source manifests from the reviewed result. Never change hashes merely to make a failed verification green.
5. Run script tests, host behavioral tests and native SDK compilation. Record failures and skipped checks separately.
6. For runtime, C ABI, TUN, authentication or state changes, perform target-device checks. Prior-device evidence does not transfer automatically to a rebuilt binary.
7. Open a focused PR with the upstream version/commit, retained/dropped patches, compatibility impact and validation links. Merge only after review and passing required checks.
8. Update `qualified_tag` after a validated upgrade. Update `observed_mainline_commit` after explicitly reviewing that branch delta; this acknowledges triage, not a release.

## Keep evidence usable

Record the actual source commit, toolchain identity, SDK/API, commands, exit codes and binary SHA-256. Keep raw credentials, node identities, login URLs, account state and signing material out of commits, issues and Actions artifacts. Target logs require deliberate redaction before publication.

CI artifacts are intermediate build outputs, not automatically supported releases. A public binary should be tied to an immutable source tag, accompanied by checksums and a compatibility matrix, and clearly identify this downstream project.

## Documentation rules

- The README answers what the project does, supported scope, prerequisites and the first runnable command.
- Build, integration, maintenance and validation guides have separate tasks. Use descriptive links and at most three heading levels.
- Every command must have a working-directory context. Explain required user-specific paths; do not present fabricated test results or placeholder credentials as working examples.
- Distinguish host tests, cross-compilation, packaging, installation and device behavior. A skipped/unrun test is never a pass.
- Keep English technical documentation and the Chinese overview aligned when scope changes.
- Update documentation in the same PR as behavior or compatibility changes. Link evidence to the exact revision and date.

## Reporting defects

Include the repository commit, `go version`, host OS/architecture, target OS/API, SDK version, the failing command and a minimal redacted log. State whether the failure happened during build, loading or runtime. Never attach a provisioning profile, authentication URL or account-state file.
