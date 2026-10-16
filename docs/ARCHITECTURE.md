# Architecture, state transitions and recovery

[← README](../README.md) · [Security](../SECURITY.md) · [Verification](../VERIFICATION.md)

**Implemented contract for development package metadata `0.3.0.dev7` (unreleased; last prior release baseline `0.2.0`).** One local Python CLI process orchestrates Git, bounded HTTPS calls and private JSON state. It is **not** a server, background agent, job queue, deployment service or automatic merger.

## System overview

~~~mermaid
flowchart TB
    O["Operator: CLI flags, file scope and approvals"] --> C["gh_agent/cli.py"]
    C --> P["gh_agent/core.py: Git, paths, checksums, JSON, filesystem policy"]
    C --> S["gh_agent/services.py: GitHub + OpenAI HTTPS"]
    C --> V["gh_agent/verification.py: Docker checks + publish gate"]
    C --> L[("Private proposal, receipt, verification JSON outside checkout")]
    P --> G[("Trusted Git + local target checkout")]
    S --> GH[("GitHub issue, refs, draft/ready PR")]
    S --> AI[("Responses Structured Outputs")]
    V --> D[("Trusted Docker daemon + operator image")]
    G --> GH
~~~

| Component | Responsibility | Does **not** guarantee |
| --- | --- | --- |
| `cli.py` | Explicit consent, read/mutation boundaries, orchestration and reconciled publication | Safe semantics of generated code |
| `core.py` | Repository/path identity, file budgets, strict local JSON, SHA-256, Git worktree/blob checks | Isolation from a malicious Git installation or host |
| `services.py` | Allowlisted HTTPS, size/time limits, strict API/model JSON and shape checks | API availability, authenticated vendor behavior, model correctness |
| `verification.py` | POSIX-host operator-selected Docker tests, commit-bound reports and publication gate | Uncompromised daemon, trusted image, sufficient target test coverage |

### Trusted and untrusted data

- **Operator authorization:** CLI flags define the permission to disclose source, edit the specific files locally and publish remotely. The model cannot grant any of these.
- **Untrusted issue/source:** GitHub issue text and selected files provide task context, never executable instructions or permission to extend scope.
- **Untrusted model/API response:** Strict parsing, structural checks, allowed paths, content budgets and original-file hashes constrain proposed data before any local edit.
- **Locally trusted dependencies:** Python process, filesystem, Git executable, Git configuration/filters/helpers, Docker daemon and operator-selected image require independent trust and isolation.
- **Remote observations:** GitHub issue, base, ref and PR state are true only at observation time; push and PR creation cannot form one atomic transaction. Repository archive/default-branch fields and issue bodies are type-checked before planning to avoid ambiguous provider data.

For threat assumptions and residual risks see [Security](../SECURITY.md).

## End-to-end lifecycle

~~~mermaid
flowchart LR
    A["plan: private proposal"] --> B["review: full diff + digest"]
    B --> C{"Exact approval?"}
    C -->|Yes| D["apply: new branch and commit"]
    C -->|No| STOP["Stop"]
    D --> E["verify: record PASS or FAIL"]
    E --> F{"publish gate"}
    F -->|PASS| G["publish: create-only push"]
    F -->|FAIL/stale| STOP
    F -->|No report + explicit exception| G
    G --> H["Confirm remote SHA"]
    H --> I["Create or reconcile open PR"]
    I --> J["Independent human review + CI"]
~~~

An optional GUI frontend (`gh_agent/gui.py`) imports Tkinter lazily and shows local workspace, file paths, proposal progress and read-only plan previews in a desktop window. It reuses the CLI's validation through a strict read-only command allowlist. It neither starts HTTP listeners nor executes the mutating agent flow. The existing CLI permission boundaries remain authoritative.

The `files` CLI uses the existing trusted local `tracked_sources` and path eligibility checks to list bounded, searchable filenames without loading content or contacting remote providers; this is not an authorization decision or a secret scan. `recipes` renders fixed, task-specific examples without executing their commands. Both offer JSON output and are accessible from the bounded TTY menu.

Read-only `workspace` reports current checkout branch, commit, clean status, optional origin identity and presence of credentials/Docker CLI without checking network validity. `prepare` performs a local scope/identity/output preflight and returns a JSON argv preview with the source-upload permission intentionally absent. In the TTY menu the same preview is available after bounded operator prompts; no action is executed or persisted.

The `dashboard` command constructs a read-only snapshot of proposal/receipt identity, commit-parent and file-blob consistency, clean checkout and bound verification state. It exposes a stable minimal JSON form, but deliberately never reports remote publication success. The `commands` catalog is static, filterable, and also supports JSON output; it cannot invoke the listed commands.

The explicit `menu` command adds bounded TTY-only navigation across read-only local guidance, checkout checks and local state inspection. It keeps the last proposal path only in process memory, supports monochrome output, refuses non-interactive input, and never calls mutating/model/remote operations. No navigation choice grants permission for `plan`, `apply`, `publish` or `run`.

The user-friendly CLI entrypoint displays a short home screen with no subcommand. `guide` prints a five-step review-first walkthrough, `doctor` inspects local prerequisites without network requests, and `next` checks the saved proposal/receipt/report and local commit before suggesting a step. All four are read-only; `--checkout` defaults to the current working directory, and existing explicit paths remain supported.

The operator can call `status` at any time to inspect local recovery state (and optionally the remote) **without mutation**. `run` calls `plan → apply → verify (if configured) → publish` after up-front permission checks; it **skips** the proposal-specific `review` pause. As a deterministic preflight boundary, `run` rejects any explicitly selected `.github/workflows/` file; workflow changes require manual diff review and exact-digest approval.

### 1. `plan` - proposal, no checkout mutation

1. Require `--allow-source-upload`, one target `owner/name`, an open numbered issue, an exact operator-specified file allowlist and an output path outside the checkout.
2. Verify the clean target worktree, matching single `origin`, current default/base ref and tracked source eligibility; reject likely sensitive content and oversize input.
3. Send explicitly approved paths and their full source contents (empty for new paths) to a single structured-output model request.
4. Accept only changed-file replacements within that allowlist, with exact original SHA-256, valid UTF-8, syntax and bounded resources; no model commands or deletions.
5. Exclusively create a private **schema-2** proposal; do not print generated source during planning.

A successful plan uses one model call; a model-proposed empty edit list is **not** accepted as a successful no-op. Model text never causes direct command execution.

### 2. `review` and `apply` - explicit local mutation boundary

`review` revalidates the clean base and proposal, prints its entire unified diff and the SHA-256 of the exact proposal file, and changes nothing. `apply` requires `--approve` **and that exact SHA-256**.

After verifying the same base and scoped paths, `apply` creates `agent/issue-<issue>-<base-sha-prefix>`. It writes approved full-file replacements, stages only proposed paths, checks the Git staged diff and changed-line budget, makes a local commit, verifies the committed blob bytes, then exclusively creates `<proposal>.applied.json`.

The receipt captures proposal digest, repo, issue, base/branch/commit, changed files and local check outcomes. **If a failure occurs after branch creation, a changed worktree or commit can remain.** No automatic destructive rollback is attempted.

### 3. `verify` and `status` - recorded evidence and read-only inspection

`verify` checks proposal and receipt identity, clean checkout/branch and exact approved commit. On a supported POSIX host it invokes Docker with a trusted, already available digest-pinned image and explicit argv array. A disposable checkout copy is mounted writable with no container network, reduced privileges and bounded resources. A private `<proposal>.verified.json` is exclusively written for PASS or FAIL (schema **1**) and bound to the exact proposal SHA, branch and commit.

The report records exit code, image, argv and bounded output excerpts. It is **not signed** and does not attest to the target application's correctness. A test failure is never overridden by publication's no-test exception.

`status` reads receipt, local branch/HEAD/cleanliness and verification gate; `--remote` can additionally compare the exact remote ref and inspect a corresponding PR. It does not reset, repair, retry, create or push anything.

### 4. `publish` - remote effect with reconciliation

1. Require `--approve-publish`, valid proposal/receipt identity, a clean checkout at the expected commit, matching changed-file set and committed bytes.
2. Require an exact recorded **PASS** with a true integer zero exit code; or, **only if no report exists**, explicitly accept `--approve-unverified` with a 12–300-character justification.
3. Re-read repository metadata and open issue; reject a moved default branch, changed issue timestamp or different remote base SHA.
4. Check the exact remote branch ref. If absent, push using `--force-with-lease=refs/heads/<branch>:` as a **create-only** lease, not a force overwrite. Re-read and verify its exact SHA.
5. Recheck base and issue after push. Search for an existing matching PR; reject closed, ambiguous, malformed or conflicting results. Create or verify an open draft PR by default, or an open review-ready PR when `--ready-for-review` is explicitly supplied, whose head matches the approved commit.

`publish` does not merge or deploy. A GitHub API timeout is not proof that a remote operation failed; reconciliation inspects current state rather than blindly replaying writes.

## Files, identifiers and budgets

| Resource | Implemented contract |
| --- | --- |
| Proposal | Private `<name>.json` outside checkout; proposal **schema 2** |
| Apply receipt | Private `<name>.json.applied.json`, created once; receipt **schema 2** |
| Verification report | Private `<name>.json.verified.json`, created once; report **schema 1** |
| Allowed source | 1–12 explicitly approved existing/new UTF-8 files, max 32,000 bytes/file, 96,000 bytes aggregate |
| Candidate tree | No fixed tree-size ceiling; exact allowlist and context budget bound model input |
| Diff | Max 1,600 changed lines, 180,000 bytes in proposal review diff |
| Issue | Open issue (not PR), bounded title and 12,000-character body, required revision timestamp |
| Git/HTTP | Exact SHA/branch checks and Git remote identity; allowlisted HTTPS endpoints with size/time limits |
| JSON | Strict duplicate-key, non-finite/overflow-number and invalid-Unicode rejection across local state, model content and API responses; local state reads capped at 512,000 bytes |

JSON source parsing and Python AST validation are **syntax checks** only. There is no built-in validator for the other allowed source formats, no automatic target-test selection, no transactional push/PR operation, and no generalized resumable job store.

## Failure and recovery matrix

| Boundary | Evidence to inspect | Recovery condition |
| --- | --- | --- |
| Invalid source/scope or stale base before planning | Clean checkout, allowed tracked files, default branch SHA | Fix inputs or replan; no code mutation should have occurred |
| Proposal changed after review | Full proposal diff and SHA-256 | Require a fresh review/approval; never reuse an old digest |
| `LOCAL_APPLY_INCOMPLETE` | Current branch, `git status`, local commit and receipt path | Preserve work; manually reconcile; **no automatic reset** |
| Docker timeout, failure or stale report | Exact report outcome/commit, possible surviving containers | Investigate safely; do not override recorded FAIL; rerun only after intentional state handling |
| Push timed out | Exact `refs/heads/agent/...` remote SHA | Resume only after proving the branch effect; never push over a conflicting SHA |
| Base/issue moved after push | Remote default SHA and issue `updated_at` | Leave branch for inspection; do not create a stale PR |
| PR creation uncertain | Open PR head/base, draft flag, search completeness | Accept only an exact matching open draft; otherwise stop |
| Unexpected PR closed, duplicate or conflicting | Returned records and remote ref | Stop and reconcile manually; do not infer absence from incomplete results |

> [!CAUTION]
> A branch can exist remotely without its PR. A local commit can exist without its receipt. A verification **PASS** reflects only the operator-selected test command. None of these states implies successful target CI, mergeability or production readiness.

## Supported vs. intentionally unsupported

**Supported:** explicitly scoped code/configuration/workflow replacements and new files/directories, one-call plans, reviewed commits, writable disposable isolated tests, draft or opted-in review-ready PRs, bounded source disclosure, and read-only recovery.

**Unsupported:** file deletion, rename/move operations, unapproved/unknown hidden paths, model-suggested command execution, autonomous reviews/merges/deployments, background jobs, automatic target-test discovery, complete secret detection, cryptographic attestation and generalized recovery.

Use [Verification](../VERIFICATION.md) for observed results, and [Security](../SECURITY.md) for operational safeguards and incident handling.


### GUI local inspection execution

The optional Tkinter desktop delegates allowlisted local inspections to isolated, bounded Python child processes on worker threads. Completion data is marshalled through a queue to the Tkinter event loop. One operation at a time is permitted; no additional remote, write, or approval authority is introduced. File-search results are discarded when inputs change before completion.


### Worker recovery and UI lifecycle

Local GUI workers turn unexpected Python exceptions into generic failure messages before returning to the Tk event loop. During a running inspection, additional file-search requests do not clear selected scope. The window refuses closure while an inspection is active to avoid orphaned work. This does not expand the read-only GUI permission boundary.


### Desktop activity feedback

The read-only GUI uses a Tk-managed indeterminate activity indicator and temporarily disables competing inspection buttons while a bounded subprocess runs. Completion restores controls through the UI thread and reports a local-only outcome. No repository writes or remote access are introduced.


### Keyboard navigation

The optional read-only GUI exposes Ctrl+F to activate Files and focus the search entry, and F5 to re-run discovery from the active Files tab. The actions retain the existing local-only inspection contract.
