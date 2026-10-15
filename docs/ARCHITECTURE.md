# Architecture, state transitions and recovery

[← README](../README.md) · [Security](../SECURITY.md) · [Verification](../VERIFICATION.md)

**Implemented contract for package `0.2.0` (including unreleased hardening).** One local Python CLI process orchestrates Git, bounded HTTPS calls and private JSON state. It is **not** a server, background agent, job queue, deployment service or automatic merger.

## System overview

~~~mermaid
flowchart TB
    O["Operator: CLI flags, file scope and approvals"] --> C["gh_agent/cli.py"]
    C --> P["gh_agent/core.py: Git, paths, checksums, JSON, filesystem policy"]
    C --> S["gh_agent/services.py: GitHub + OpenAI HTTPS"]
    C --> V["gh_agent/verification.py: Docker checks + publish gate"]
    C --> L[("Private proposal, receipt, verification JSON outside checkout")]
    P --> G[("Trusted Git + local target checkout")]
    S --> GH[("GitHub issue, refs, draft PR")]
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
- **Remote observations:** GitHub issue, base, ref and PR state are true only at observation time; push and PR creation cannot form one atomic transaction.

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
    H --> I["Create or reconcile open draft PR"]
    I --> J["Independent human review + CI"]
~~~

The operator can call `status` at any time to inspect local recovery state (and optionally the remote) **without mutation**. `run` calls `plan → apply → verify (if configured) → publish` after up-front permission checks; it **skips** the proposal-specific `review` pause.

### 1. `plan` - proposal, no checkout mutation

1. Require `--allow-source-upload`, one target `owner/name`, an open numbered issue, an exact operator-specified file allowlist and an output path outside the checkout.
2. Verify the clean target worktree, matching single `origin`, current default/base ref and tracked source eligibility; reject likely sensitive content and oversize input.
3. Model request **one** chooses a subset of pre-authorized paths; reject any escape or duplicate.
4. Model request **two** returns complete UTF-8 replacement text and original SHA-256 for the chosen files; reject malformed output, unchanged edits, unsafe paths, invalid Python/JSON syntax or exceeded budgets.
5. Exclusively create a private **schema-2** proposal; do not print generated source during planning.

A successful plan uses two model calls; a model-proposed empty edit list is **not** accepted as a successful no-op. Model text never causes direct command execution.

### 2. `review` and `apply` - explicit local mutation boundary

`review` revalidates the clean base and proposal, prints its entire unified diff and the SHA-256 of the exact proposal file, and changes nothing. `apply` requires `--approve` **and that exact SHA-256**.

After verifying the same base and scoped paths, `apply` creates `agent/issue-<issue>-<base-sha-prefix>`. It writes approved full-file replacements, stages only proposed paths, checks the Git staged diff and changed-line budget, makes a local commit, verifies the committed blob bytes, then exclusively creates `<proposal>.applied.json`.

The receipt captures proposal digest, repo, issue, base/branch/commit, changed files and local check outcomes. **If a failure occurs after branch creation, a changed worktree or commit can remain.** No automatic destructive rollback is attempted.

### 3. `verify` and `status` - recorded evidence and read-only inspection

`verify` checks proposal and receipt identity, clean checkout/branch and exact approved commit. On a supported POSIX host it invokes Docker with a trusted, already available digest-pinned image and explicit argv array. The checkout is mounted read-only with no container network, reduced privileges and bounded resources. A private `<proposal>.verified.json` is exclusively written for PASS or FAIL (schema **1**) and bound to the exact proposal SHA, branch and commit.

The report records exit code, image, argv and bounded output excerpts. It is **not signed** and does not attest to the target application's correctness. A test failure is never overridden by publication's no-test exception.

`status` reads receipt, local branch/HEAD/cleanliness and verification gate; `--remote` can additionally compare the exact remote ref and inspect a corresponding draft PR. It does not reset, repair, retry, create or push anything.

### 4. `publish` - remote effect with reconciliation

1. Require `--approve-publish`, valid proposal/receipt identity, a clean checkout at the expected commit, matching changed-file set and committed bytes.
2. Require an exact recorded **PASS** with zero exit code; or, **only if no report exists**, explicitly accept `--approve-unverified` with a 12–300-character justification.
3. Re-read repository metadata and open issue; reject a moved default branch, changed issue timestamp or different remote base SHA.
4. Check the exact remote branch ref. If absent, push using `--force-with-lease=refs/heads/<branch>:` as a **create-only** lease, not a force overwrite. Re-read and verify its exact SHA.
5. Recheck base and issue after push. Search for an existing matching PR; reject closed, ambiguous, malformed or conflicting results. Create or verify **only an open draft PR** whose head matches the approved commit.

`publish` does not merge or deploy. A GitHub API timeout is not proof that a remote operation failed; reconciliation inspects current state rather than blindly replaying writes.

## Files, identifiers and budgets

| Resource | Implemented contract |
| --- | --- |
| Proposal | Private `<name>.json` outside checkout; proposal **schema 2** |
| Apply receipt | Private `<name>.json.applied.json`, created once; receipt **schema 2** |
| Verification report | Private `<name>.json.verified.json`, created once; report **schema 1** |
| Allowed source | 1–5 existing tracked UTF-8 files, max 20,000 bytes/file, 55,000 bytes aggregate |
| Candidate tree | At most 1,000 eligible tracked files |
| Diff | Max 400 changed lines, 85,000 bytes in proposal review diff |
| Issue | Open issue (not PR), bounded title and 6,000-character body, required revision timestamp |
| Git/HTTP | Exact SHA/branch checks and Git remote identity; allowlisted HTTPS endpoints with size/time limits |
| JSON | Strict duplicate-key, non-finite/overflow-number and invalid-Unicode rejection across local state, model content and API responses; local state reads capped at 256,000 bytes |

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

**Supported:** bounded scoped proposals, source-upload consent, human digest approval, local commits, optional isolated tests, explicit missing-test exception, remote create-only draft PR, and read-only recovery.

**Unsupported:** new/deleted files, broad or hidden file edits, workflow modifications by the agent, model-suggested command execution, autonomous reviews/merges/deployments, background operation, target-test discovery, full secret detection, cryptographic attestation, and automatic recovery from arbitrary partial failures.

Use [Verification](../VERIFICATION.md) for observed results, and [Security](../SECURITY.md) for operational safeguards and incident handling.
