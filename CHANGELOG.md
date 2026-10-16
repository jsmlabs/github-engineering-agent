# Changelog

[← README](README.md) · [Verification evidence](VERIFICATION.md) · [Security](SECURITY.md)

Notable changes are grouped by release. **`Unreleased` is not a published release.** [`pyproject.toml`](pyproject.toml) now declares development metadata **0.3.0.dev3** to reflect the new CLI/GUI and installation capabilities since 0.2.0; this is not a tag, signed artifact or production approval.

## Unreleased

### Installer GUI input and status feedback

- Reject nonhexadecimal or incorrectly sized SHA-256 inputs before starting a local installation worker; accept both hexadecimal letter cases.
- Report which maintenance action completed or failed instead of a generic result state; add offline input-validation regression tests.
- No additional network capabilities, privileges or dependency requirements; development metadata advances to **0.3.0.dev3** without a release.


### Offline wheel packaging verification

- Add a disposable-source, no-index wheel build and isolated-venv installation check for exact package metadata and the `gh-engineer` console entry point.
- Explicitly bootstrap exact-version, SHA-256-locked build wheels in the CI setup step (networked); keep the subsequent wheel build and installed-CLI verification offline to avoid unreliable runner tool preinstalls.
- Run a separate Ubuntu/macOS/Windows Python 3.11 packaging matrix while preserving the existing seven-job offline regression suite.
- Advance unpublished development metadata to **0.3.0.dev2** to identify this pre-release quality-gate iteration; this is not a tagged or published release.

### Installer state validation (unreleased)

- Reject a boolean `schema` value that Python previously considered equal to integer 1; require all installation-state fields before access.
- Bound local state reads to 256,000 bytes and reject duplicate JSON keys and nonstandard numeric constants. Invalid state fails closed without overwriting the file.
- Add focused negative-path regression tests; advance unpublished development metadata to **0.3.0.dev1** (no release, API change, dependency or migration).

### Launcher runtime fix and development metadata

- Keep installed interactive GUI/menu sessions running until the application exits, instead of imposing the 240-second maintenance subprocess timeout; retain bounded installation and verification operations.
- Add a mocked launch-contract regression test and refresh the verified #30 CI baseline documentation.
- Advance package metadata from 0.2.0 to **0.3.0.dev0** (pre-release MINOR version reflecting cumulative unreleased CLI/GUI/installer features); synchronize badges and architecture references. No publication, migration, dependency or authorization change.

### Offline user-scoped installation manager (preview)

- Add a local-wheel installation, verification, isolated release update/repair, verified rollback and guarded uninstallation CLI plus optional Tkinter maintenance GUI.
- Require an explicit SHA-256 matching a trusted local wheel; preserve CLI permission boundaries and avoid automatic network downloads.
- Add regression coverage, installation/recovery documentation and disclose incomplete transaction isolation and lack of trusted automatic release discovery.


### Optional GUI-first desktop workflow

- Add an optional Tkinter desktop application (`gh-engineer gui`) with workspace overview, eligible-file multiselect, validated plan preview and help tabs.
- Keep the GUI local and read-only: no HTTP listener, model call, source upload, repository mutation or PR publication. Provide error handling for missing Tkinter or headless environments, with the existing terminal menu as fallback.
- Add GUI backend allowlist and headless regression coverage without adding mandatory Python dependencies.

### Scoped file discovery and task recipes

- Add `gh-engineer files` to search eligible tracked file paths locally, with bounded result counts (1-50), name filtering and JSON output; protect excluded paths and never read selected contents or approve their upload.
- Add `gh-engineer recipes` with fixed, topic-filtered workflow examples for onboarding, scope selection, review, verification, publishing and recovery; examples are never executed.
- Extend the interactive menu with Files and Recipes (choices 0-10), five regression tests and offline CLI smoke checks. Preserve existing consent boundaries and zero additional runtime dependencies.

### Workspace awareness and approval-safe plan preparation

- Add `workspace` with human-readable and JSON local Git readiness, clean/dirty reporting, optional origin identity verification, and credential-presence checks without revealing secret values or contacting a provider.
- Add `prepare` for validated, explicit file-scope and output-path input, returning a safe JSON argv preview without executing a plan, authorizing upload, writing a proposal or querying GitHub/OpenAI.
- Extend the bounded interactive menu with Workspace and Prepare options (0–8), regression tests, documentation and offline smoke coverage while preserving all existing authorization boundaries and package dependencies.

### Command discovery and local workflow dashboard

- Add a searchable command catalog with task categories, explicit side-effect labels and optional JSON output for terminal or scripts.
- Add a read-only proposal dashboard for validated PROPOSED, APPLIED, VERIFIED_LOCAL and BLOCKED stages, including saved SHA, checkout, changed-file and committed-blob integrity checks. A local PASS never implies remote PR publication or CI success.
- Expand the interactive menu with direct catalog and dashboard navigation. Extend negative-path tests and offline CLI smoke commands without new dependencies or permission changes.

### Terminal menu and accessible interaction

- Add explicit `gh-engineer menu` with numbered local-only navigation, reusable proposal path within the session, TTY detection, bounded input loops and safe EOF/interrupt handling.
- Support optional ANSI styling with `--no-color` and `NO_COLOR` plain-text fallback. Keep non-interactive automation on the existing ordinary CLI commands.
- Expand CLI regression and offline smoke checks for menu behavior, no mutation/network effects, invalid choices, local state and cross-platform help.

### Terminal experience and guided operation

- Introduce a concise CLI home screen, `guide` step-by-step onboarding, offline `doctor` preflight and read-only `next` suggestions backed by local proposal/receipt/verification checks.
- Default `--checkout` to the current working directory, while preserving all explicit path options and the original `plan`/`review`/`apply`/`verify`/`status`/`publish`/`run` commands and authorization contracts.
- Extend regression coverage for terminal navigation, no-network/no-mutation guidance, dirty-checkout diagnostics, and stale/failed verification states; add CLI smoke checks across the platform matrix.

### API data validation and test compatibility

- Fail closed on malformed repository archive/default-branch metadata and on non-string GitHub issue bodies, including empty lists, objects, booleans and numbers; preserve valid null or string bodies.
- Add regression tests for accepted and rejected API shapes and a focused Ubuntu/Python 3.12 CI job alongside the existing six-job OS/Python matrix.
- Align package description with supported draft and opt-in review-ready pull requests; no schema, permission, dependency or package-version change.

### Expanded engineering scope (unreleased)

- Permit explicitly allowlisted creation of new files and directories and updates to named workflows, build configuration and dependency/lockfiles while retaining path/secret checks and scoped staging. Workflow changes require the reviewed `plan → review → apply` flow; unreviewed `run` blocks workflow scopes before planning.
- Raise bounded plans from five to twelve files, 20 KB to 32 KB/file, 55 KB to 96 KB aggregate and 400 to 1,600 changed lines; raise the local state JSON read cap to 512,000 bytes and remove the fixed candidate-file tree ceiling.
- Remove one redundant model selection call per plan; retain the existing proposal/receipt schema and deterministic validation.
- Run isolated tests in a writable disposable checkout copy, preserving the operator checkout, restricted Docker privileges and offline networking.
- Allow opt-in review-ready PR creation with `--ready-for-review`; keep draft creation as default and preserve independent remote verification.
- Add regression coverage for new path scopes, symlink/untracked denial, test isolation and CLI review-ready mode.

### Security and input validation

- Reject boolean or malformed test-report exit codes rather than treating JSON `false` as numeric zero. Require true integer issue numbers in GitHub API responses and normalize disconnected HTTP transports to controlled errors; add focused regression tests.
- Reject invalid Unicode on outbound API/model JSON paths with controlled errors before network access; add a regression test.
- Harden shared JSON decoding against finite-syntax overflow (`1e999`) and unpaired Unicode surrogates; cap proposal/receipt/verification file reads at 256,000 bytes and add targeted regressions. Valid JSON and application schemas are unchanged.

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

- Polish the README presentation with a compact hero, clearer three-pillar overview, mobile-friendly workflow diagram, progressive-disclosure examples, and more prominent safety/operational guidance; no application behavior changes.
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

See [VERIFICATION.md](VERIFICATION.md) for executed CI/test evidence. Development package metadata may advance in reviewed changes, but publishing a version, tag or release remains a separately authorized process subject to verification and release gates.
