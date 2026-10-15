# Changelog

Notable changes are grouped by release. The package uses its declared version in `pyproject.toml`; documentation-only edits do not independently increment the application version.

## Unreleased

### Structured model-output validation

- Fail closed on duplicate JSON object keys (including nested keys) and non-finite numeric constants in model-generated structured output before proposal validation.
- Add malformed-response regression coverage; no CLI, proposal schema, version, or permission changes.

### Strict JSON source validation

- Reject duplicate JSON object keys, including nested duplicates, and non-standard non-finite values (`NaN`, `Infinity`, `-Infinity`) before accepting generated JSON edits.
- Add regression coverage without changing the proposal schema, CLI options, or package version.

### Verification and recovery (integrated into `main`)

- Reject actual newline and carriage-return characters in Docker bind-mount paths before invoking Docker; add a no-subprocess regression test.
- Added optional operator-configured Docker tests using an explicit digest-pinned image and bounded, no-network container invocation.
- Required an exact commit-bound passing verification record before draft publication, with an explicit auditable exception only for unexecuted tests.
- Added read-only local/remote status inspection, negative verification tests and a multi-platform offline CI matrix.
- Kept proposal schema 2 and package version 0.2.0 unchanged; these changes have not been assigned a new release version.


### Reliability

- Integrate fail-closed OpenAI Responses message-content validation and its positive/negative regression tests from PR #3.
- Fail closed with `AgentError` when GitHub pull-request search results contain malformed records or nested fields, instead of leaking an unhandled exception. Added positive and negative regression tests.

### Documentation

- Reorganized the README around onboarding, **reviewed vs. high-trust execution**, authorization flags, state checks, and recovery.
- Added a focused [architecture and recovery guide](docs/ARCHITECTURE.md) covering model/deterministic boundaries, side effects and partial outcomes.
- Reworked [security guidance](SECURITY.md) with a threat-boundary matrix, least-privilege setup and incident handling.
- Clarified in [verification evidence](VERIFICATION.md) what was tested offline and what remains unverified in live GitHub/OpenAI integrations.
- Documentation-only restructuring introduced no CLI, source-code, proposal-format or package-version changes; the separately listed verification/reliability work does change implementation.

## 0.2.0 - 2026-10-15

### Scope and approvals

- Required explicit `--allowed-file` boundaries for planning and autonomous execution; removed implicit repository-wide file selection.
- Bound manual `apply` authorization to the SHA-256 printed by `review`; kept opt-in `run` as a separate high-trust mode.
- Added complete proposal diff inspection with `review` and prevented automatic source-diff printing during `plan`.

### Integrity and safety

- Tightened exact remote-ref checks, rejected incomplete PR results and closed PR collisions, and rechecked issue/base before PR creation.
- Used a create-only Git push lease to reject concurrent remote branch creation without overwriting another commit.
- Added conservative credential and terminal-control checks for issue text, selected source and generated edits.
- Added Python/JSON syntax checks, applied-proposal SHA-256 receipts and exact committed Git blob verification.
- Strengthened issue timestamps, input validation and offline tests for race conditions, tampering, remote effects and explicit consent.

### Breaking compatibility

- **Proposal schema 2 is incompatible with v0.1.0 schema 1.** Previously generated proposals/receipts cannot be applied or published by v0.2.0; create a fresh plan with explicit file scope.

## 0.1.0 - 2026-10-15

- Initial standalone, bounded `plan`, `apply`, `publish` and `run` issue-to-draft-PR reference implementation.
