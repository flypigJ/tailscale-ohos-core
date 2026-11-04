# Contribute

Start with the README and maintenance guide. Small changes with a reproducible failure are easier to review than combined platform, API and UI changes.

1. Open an issue describing the use case or defect without credentials or private device data.
2. Work on a branch. Preserve upstream copyright headers and identify borrowed/adapted code.
3. Add a test for behavior that can regress; do not replace real validation with a test that merely matches implementation text.
4. Run the documented script and host tests. For target changes, include SDK/device evidence or explicitly mark it not run.
5. Describe what changed, why, how it was tested, and remaining limits. Update the relevant documentation and source locks.

The initial target is API 26 / arm64. Broader support requires explicit tests and documentation; silently relaxing a gate is not a platform port.

Do not send credentials, app signing files or account state. Large binary artifacts belong in controlled build artifacts, not Git history. This project does not accept an unreviewed automatic version bump as an upgrade.
