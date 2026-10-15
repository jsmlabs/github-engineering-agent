# Changelog

Notable changes are grouped by release. The package uses its declared version in `pyproject.toml`; documentation-only edits do not independently increment the application version.

## Unreleased

### Reliability

- Reject malformed OpenAI Responses message content with a controlled `AgentError` instead of an uncaught type error; add malformed and valid-response regression cases (execution pending).
- Fail closed with `AgentError` when GitHub pull-request search results contain malformed records or nested fields, instead of leaking an unhandled exception. Added positive and negative regression tests.

### Documentation

- Reorganized the README around onboarding, **reviewed vs. high-trust execution**, authorization flags, state checks, and recovery.
- Added a focused [architecture and recovery guide](docs/ARCHITECTURE.md) covering model/deterministic boundaries, side effects and partial outcomes.
- Reworked [security guidance](SECURITY.md) with a threat-boundary matrix, least-privilege setup and incident handling.
- Clarified in [verification evidence](VERIFICATION.md) what was tested offline and what remains unverified in live GitHub/OpenAI integrations.
- **No CLI, source-code, proposal-format or package-version change.**

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
