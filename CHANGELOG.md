# Changelog

## 0.2.0 - 2026-10-15

- Require operator-defined `--allowed-file` boundaries on planning and autonomous execution; eliminate repository-wide implicit file scope.
- Bind manual `apply` approval to the exact SHA-256 printed by the `review` command (autonomous `run` remains separately opt-in).
- Require exact remote-ref matches, fail closed on incomplete PR search pages, and recheck issue/base before PR creation.
- Use a create-only Git lease to reject concurrent branch creation without force-overwriting remote state.
- Block ASCII terminal-control payloads from issue/source/generated content; add local bare-Git push-lease and race-condition regression coverage.
- Add `review` command for full proposal diff, separate from `plan` output.
- Prevent automatic source diff printing in `plan` logs.
- Add conservative credential-pattern checks for issue text, selected source and generated edits.
- Parse generated Python and JSON before local mutation; reject obvious syntax errors.
- Bind apply receipts to the original proposal SHA-256 and verify exact committed Git blob bytes.
- Reject closed pull requests when reconciling a draft PR publication.
- Require an issue update timestamp and strengthen input validation.
- Extend offline unit/integration-style tests including opt-in execution boundaries, tampering, suspicious input and mocked publishing.
- Explicit **incompatible proposal format**: version 0.1.0 schema 1 records cannot be applied or published; regenerate under schema 2.

## 0.1.0 - 2026-10-15

- Initial bounded `plan`, `apply`, `publish`, `run` issue-to-draft-PR reference implementation.
