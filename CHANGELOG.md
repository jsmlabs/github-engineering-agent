# Changelog

[← README](README.md) · [Verification evidence](VERIFICATION.md) · [Security](SECURITY.md)

Notable implementation and documentation changes are grouped by release. **`Unreleased` is not a published package release.** The version declared in [`pyproject.toml`](pyproject.toml) remains **0.2.0**; documentation edits alone do not change it.

## Unreleased

### Security and input validation

- **Unified strict JSON boundaries:** reject duplicate object keys, including nested duplicates, and non-standard `NaN`/`Infinity` constants in generated JSON source, model Structured Outputs, GitHub/OpenAI HTTP responses, and private proposal/receipt/verification records. Treat excessive JSON nesting as a controlled error. Consolidate the shared parser.
- **Fail-closed model output:** reject explicit refusals (including responses mixing refusal and text), unexpected output items/message parts, incomplete messages, ambiguous structured JSON and malformed outbound model/API JSON. Valid reasoning plus one completed structured-text response remains supported.
- **Repository and GitHub identity:** reject malformed/non-string `owner/name` values and malformed API repository `full_name` with `AgentError` instead of uncaught type/attribute errors.
- **PR reconciliation:** fail closed on malformed GitHub PR entries, multiple matching open PR records, incomplete searches and closed PR collisions; never silently choose an ambiguous match.
- **Recovery input:** reject `status --remote` receipts missing repository/base identity before attempting remote access.

### Verification, recovery and CI

- Add operator-configured Docker tests with preloaded digest-pinned images, bounded execution, no container network, read-only checkout and restricted privileges. Reject mount paths containing real newline/carriage return characters or commas before launch.
- Bind verification reports to exact proposal SHA, branch and commit. Require **PASS** before draft publication; permit a justified explicit exception only when **no** report exists. Known FAIL or stale reports block publishing.
- Provide a read-only `status` view for local and optional remote recovery, with negative tests for stale/ambiguous outcomes and simulated publication retries.
- Expand offline GitHub Actions to Linux, macOS and Windows with Python 3.11 and 3.13. Upgrade official `actions/checkout` and `actions/setup-python` to v7, pin verified commit SHAs, retain read-only permissions and no persisted checkout credentials, and set a 15-minute per-job timeout.
- Add positive and adversarial regression tests for JSON ambiguity, model output, repository identity, PR reconciliation, Docker configuration and recovery. See [commit-specific evidence](VERIFICATION.md) for actual executed results.

### Documentation and developer experience

- Redesign the README with a clearer task-oriented start, linked navigation, accessible workflow diagram, authorization matrix, concise command examples and separate reviewed versus high-trust modes.
- Consolidate [security boundaries](SECURITY.md) by trust boundary and operator responsibility; clarify provider disclosure, residual risks, and incident handling.
- Reorganize [architecture and recovery](docs/ARCHITECTURE.md) around implementation contracts, exact state transitions, file schemas and partial-failure reconciliation.
- Refresh [verification](VERIFICATION.md) to prioritize current commit-specific CI results while retaining historical evidence and explicit unverified capabilities.
- Normalize changelog grouping and reduce redundant historical notes. These documentation changes **do not** alter CLI flags, proposal schema, permission gates, package dependencies or application version.

## 0.2.0 - 2026-10-15

### Authorization and workflows

- Require explicit `--allowed-file` scopes; remove implicit repository-wide model file selection.
- Bind manual `apply` to the exact proposal SHA-256 printed by `review`; retain `run` as an explicitly authorized, high-trust mode.
- Print complete proposed source changes only during review, not automatically during planning.

### Repository integrity and safety

- Tighten repository/remote branch identity checks, refuse incomplete PR results and closed PR collisions, and recheck the issue/base before PR creation.
- Use a create-only Git push lease to prevent overwriting another remote branch; verify the resulting remote ref.
- Introduce conservative source/issue credential heuristics and terminal-control checks.
- Validate Python/JSON syntax, proposal/source hashes, staged changes and exact committed Git blobs; record private apply receipts.
- Extend offline regression tests for authorization, stale state, tampering, race conditions and side effects.

### Compatibility break

> [!WARNING]
> **Proposal/receipt schema 2 is incompatible with v0.1.0 schema 1.** Older proposals and receipts cannot be applied or published with v0.2.0. Create a new plan with an explicit file allowlist; no automatic migration is available.

## 0.1.0 - 2026-10-15

- Initial standalone Python reference CLI supporting bounded issue-to-draft-PR `plan`, `apply`, `publish` and `run` workflows.

---

See [VERIFICATION.md](VERIFICATION.md) for executed CI/test evidence. Version and release metadata must be updated only when a release is intentionally prepared under repository policy.
