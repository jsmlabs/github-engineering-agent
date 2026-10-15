# Security model and operating policy

[← README](README.md) · [Architecture & recovery](docs/ARCHITECTURE.md) · [Verification evidence](VERIFICATION.md)

> [!WARNING]
> **Reference software, not a security certification.** The agent may upload selected source code to a model provider and push a draft or review-ready PR to GitHub. A **pull request is a real remote change**: its source is visible to repository readers and its creation may trigger CI or third-party automation. Operate only with explicit authorization, least-privilege credentials, and independent review.

## Security at a glance

**The model proposes data; trusted code enforces permissions.** GitHub issues, repository files, API responses and model output are untrusted inputs. No prompt can expand the operator's file allowlist, grant a new capability, approve a commit, or bypass publication gates.

| Boundary | Primary control | Important residual risk |
| :--- | :--- | :--- |
| Issue/source → model | Explicit `--allow-source-upload`, exact file allowlist, sensitive-content heuristics, bounded input | Heuristics cannot detect every secret or confidential datum; model behavior remains probabilistic |
| Model/API → proposal | Strict JSON decoding, allowed schemas/paths, SHA-256 source binding, size/syntax checks | Syntactically valid code may be unsafe or incorrect |
| Proposal → local commit | Human-reviewed digest plus `--approve`, clean checkout, commit/blob and file-set checks | Local files/hashes are not signed or protected against a malicious host |
| Local commit → remote branch | Separate `--approve-publish`, current issue/base checks, create-only Git push lease | Git and its helpers are trusted; concurrent changes and ambiguous network outcomes remain possible |
| Remote branch → PR | Exact head/base and expected draft/ready-state verification; conflicting or closed PR is rejected | Push and PR creation are not atomic; external CI may start |
| Local Docker verification | Operator-selected digest-pinned image, resource/network/filesystem constraints | Docker daemon, host kernel and image provenance remain operator-trusted |

## Authorization and invariants

| Operation | Required authorization | Maximum intended effect |
| --- | --- | --- |
| `menu`, `guide`, `doctor`, `next` | No permission grants | Local interactive navigation, instructions or read-only state checks; never model or remote writes |
| `plan` | `--allow-source-upload` and 1–12 explicit `--allowed-file` entries | Read issue and selected source; send bounded content to the chosen model; create a private proposal outside checkout |
| `review` | None | Print full proposed diff/digest, **no modification** |
| `apply` | `--approve` with the exact `--expected-sha256` from review | New local branch, edits to approved tracked files, commit and receipt |
| `verify` | Explicit pinned image and command | Execute operator-selected test in constrained Docker, write commit-bound verification report |
| `status` | None | Inspect local state; `--remote` adds read-only remote lookups |
| `publish` | `--approve-publish` and PASS report or explicit no-test exception | Create-only branch push and **open PR (draft by default)** |
| `run` | Upload, local-write and remote-publish approvals up front, plus verification configuration or no-test exception | Combined plan/apply/verify/publish **without human proposal-review pause** |

The terminal assumes the current working directory as the checkout unless `--checkout` is supplied. The explicit `menu` command requires a TTY, has a bounded input loop and never invokes `plan`, `apply`, `publish` or `run`; it calls local-only `guide`, `doctor`, `next` or `status` without remote lookup. ANSI styling is disabled when redirected, when `NO_COLOR` is set or with `--no-color`. Avoid treating terminal output or local receipt files as trusted evidence of live provider behavior. `doctor` inspects local Git and reports credential presence only; `next` never executes its suggestions and refuses mismatched state. Neither command attests to the security of the local host, credentials or dependencies.

The agent **does not** merge, approve PR reviews, deploy, delete files, create unapproved files, execute model-proposed shell commands, or mutate arbitrary paths. Security controls are deterministic checks in application code, not guarantees provided by model instructions.

## Input, data and repository controls

**Scope.** GitHub Actions workflow changes require the reviewed `plan → review → apply` path and are rejected before side effects in high-trust `run`, because even a draft PR may trigger CI. All model-editable paths must be repository-relative and explicitly allowlisted by the operator. Existing tracked or new regular UTF-8 files, including new directories, lock/configuration files and explicitly named `.github/workflows/*.yml`/`.yaml`, are allowed within resource budgets. Secret-bearing paths, unknown hidden files, symlinks, path escapes and unapproved changes are rejected. Proposed edits are complete file replacements; deletions, moves and arbitrary commands remain unavailable.

**JSON and model responses.** Proposal/receipt/verification records, remote API JSON, generated JSON source and structured model output reject duplicate object keys (including nested duplicates), non-finite constants, overflowed numbers and unpaired Unicode surrogates. Local state JSON reads are limited to 512,000 bytes. Repository metadata must contain a boolean archived flag and a valid default-branch name; issue bodies must be null or strings. Malformed model items, unexpected message parts, explicit refusals and incomplete messages fail closed. The model has no tool-execution authority. These controls do not prove semantics or exclude all prompt-injection effects.

**Data disclosure.** `plan` sends the issue title/body and full content of explicitly selected source files to the configured OpenAI endpoint. Review content may appear in terminal transcripts. Protect proposal JSON, apply receipts, verification reports, terminal output and backups. The source scanner only detects **selected common** credential patterns and control characters; it is not DLP. Classify inputs **before** permitting source upload.

**Repository identity and Git.** The target repository must match the checkout's single exact `origin` fetch/push destination (supported HTTPS/SSH forms). A clean worktree, recorded base and exact objects are checked at relevant boundaries. Git hooks are disabled for invoked commands where supported, but credential helpers, global/local configuration, filters, the trusted Git executable and the filesystem are **not sandboxed**. Avoid shared hosts, untrusted Git installations and concurrent mutators.

**Remote publication.** The new branch uses an explicit create-only push lease and cannot overwrite another branch. Base SHA, issue update timestamp, local commit contents, remote branch and PR state are rechecked. Closed/ambiguous PR results, stale state and conflicting refs stop publication. HTTP timeouts may occur **after** a server-side effect: reconcile observed GitHub state before retrying.

## Credentials and minimum privileges

- Use a scoped, short-lived `GITHUB_TOKEN` with **Issues: read** for planning. Publishing also requires **Contents: write** and **Pull requests: write** API privileges. Git push authorization is supplied separately through approved SSH credentials or a credential helper. Repository-specific rules may impose additional restrictions.
- Give `OPENAI_API_KEY` only the model permissions needed for planning. Verify model compatibility, provider data-handling terms and applicable project policies. Never put tokens in remote URLs, CLI arguments, proposals or shared logs.
- Use a dedicated trusted checkout and a private directory **outside** it for proposal/receipt/test-report state. Exclusive creation uses restrictive permissions (mode `0600` where supported); this is not cryptographic integrity or a secure storage service.
- Treat unexpected credential disclosure as an incident: stop publication, preserve non-secret evidence, revoke/rotate affected credentials and audit provider/repository activity.

## Isolated verification is optional, not a universal sandbox

The POSIX-host `verify` operation requires an operator-supplied image pinned by `sha256` digest and an explicit JSON argv array. It uses a preloaded image (`--pull=never`), writable disposable checkout copy and read-only root filesystem, disabled container network, no Linux capabilities, `no-new-privileges`, host-UID-mapped container user, limited CPU/memory/PIDs and scratch space, and a bounded timeout.

> [!CAUTION]
> A Docker daemon with host-level privileges is a trusted dependency, **not** contained by these flags. Use a dedicated rootless/isolated worker and images from a vetted source. Native Windows Docker execution is not supported; the project's Windows **offline CI tests** are a different capability. Timeout cleanup is best effort: check for surviving containers.

The test command is **operator-selected**, not discovered or proposed for execution by the model. Test success proves only that this command returned exit code zero for that recorded commit in that environment.

### Publication gate

A matching, commit-bound `.verified.json` with outcome **PASS** and a genuine integer exit code of zero permits publication; boolean or malformed exit codes fail closed. **FAIL**, malformed, or stale records block it. Only when **no report exists**, `--approve-unverified --unverified-reason "..."` can authorize a documented exception; the reason must have 12–300 characters. This is an explicit acceptance of missing test evidence, not a claim of safety. The verification report is an unsigned local artifact; a malicious host can tamper with it.

## Failure response and recovery

**Never blindly replay a failed mutation.** First use read-only `status`, inspect `git status`, current branch/commit, proposal/receipt/report and exact remote refs. Consult the [recovery matrix](docs/ARCHITECTURE.md#failure-and-recovery-matrix).

| Situation | Response |
| --- | --- |
| `LOCAL_APPLY_INCOMPLETE` | Preserve the branch and worktree; inspect before manual repair. There is no automatic destructive rollback. |
| Push timeout/unknown outcome | Inspect the exact remote ref SHA and compare against the approved local commit before any new push. |
| PR creation timeout/unknown outcome | Check expected head, base, `open` state and `draft` flag; stop if they differ or search results are incomplete. |
| Issue/base changed after push | Stop PR creation and preserve the remote branch for manual reconciliation. |
| Suspected malicious generated edit | Block publication or review/merge, examine proposal and committed blobs, determine any remote exposure and follow incident policy. |

## Reporting a vulnerability

Report security issues **privately** to the repository owner using an established private contact channel. Do not place exploit details, tokens or sensitive reproductions in public issues or PRs. No managed security support or response SLA is advertised.

## Assurance boundaries

The [offline verification workflow](.github/workflows/offline-verification.yml) uses SHA-pinned official GitHub Actions, `contents: read` permissions, non-persistent checkout credentials and a 15-minute per-job timeout. This is defense in depth, not a runner/security attestation.

**Not demonstrated by the offline suite:** live OpenAI/GitHub authentication and API correctness, real Docker test execution, production branch-protection behavior, complete secret detection, semantic correctness of generated code, or end-to-end security of arbitrary target repositories. Review [commit-specific evidence and open gaps](VERIFICATION.md) before making deployment decisions.
