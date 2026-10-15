# Security, trust boundaries and limitations

This CLI is a bounded **reference implementation**, not a production-security certification. The operator must own the target repository and authorize each external action. Tokens grant only the platform permissions configured by the operator.

## Trust model

| Input / actor | Trust level | Enforcement |
| --- | --- | --- |
| Operator CLI scope and credentials | Privileged | Explicit flags, exact repository and file allowlist |
| GitHub issue title/body | Untrusted | Bounded size, treated only as task data, credential heuristics |
| Repository source text | Untrusted data | Exact path scope, size/UTF-8 checks, credential heuristics |
| AI output | Untrusted proposal | JSON shape, file scope, original SHA, budgets, syntax checks |
| Git client and local checkout | Privileged environment | Must be dedicated, clean, configured and maintained by operator |
| Remote GitHub state | Authoritative for remote commit/PR | Re-read exact refs, issue timestamp, PR draft/state/commit |

For interactive local apply, the operator must supply the exact SHA-256 printed by review. The autonomous `run` mode is a separate high-trust, blanket-approval path and does not require inspecting that particular proposal. Credentials and scope remain under deterministic control.

The model **never** grants new authorization, executes its own shell commands or gains credentials. Authorization lives in the deterministic CLI, Git credential system and GitHub permissions.

## Protected areas

Paths are restricted to eligible tracked regular UTF-8 files in exact operator-approved scope. Examples of protected areas: `.git`, `.github`, hidden files, symlinks, dependency/vendor/build directories, lockfiles, credential/key filenames and executable/binary formats. A sensitive code file can still be among eligible files if the operator explicitly authorizes it; this is a **limitation**, not an endorsement of making security changes.

The source-content scanner blocks common recognizable token/key patterns, including GitHub and OpenAI credential prefixes, but cannot guarantee that arbitrary secrets, PII or proprietary data are absent. **Do not use it as a substitute for data classification, repository review, or DLP.**

## Denied capabilities

No force-push, merge, deployment, change to GitHub workflows, broad repository mutation, automatic recovery after unknown side effects, execution of model-suggested commands or automatic target test execution. Never bypass repository policies, required checks or approvals.

## Important residual risks

1. **Generated code defects:** valid syntax and scoped paths do not guarantee correct, secure or maintainable code. CI/review remains mandatory prior to merge.
2. **Local Git execution:** untrusted Git filters, credential helpers, environment configuration and external programs can execute outside model controls. Use isolated, trusted build workers and credentials.
3. **Local races:** concurrent writers and file-system races between check/read/write/commit are not fully prevented. Use a dedicated workspace controlled by a single operator.
4. **Mutable receipts:** proposal SHA binds ordinary accidental modifications, but a local attacker who can edit both files can forge an unkeyed hash. Use external signing/attestation for stronger provenance.
5. **Issue text injection:** source/issue text may contain malicious instructions. They are not granted authority, but the AI can still produce undesirable valid code. Treat its output as untrusted and review.
6. **Remote partial outcomes:** network failures can leave a branch pushed without a PR. Exact remote-ref validation and create-only push lease prevent overwriting a concurrently created branch, but do not make branch push plus PR creation atomic. Inspect remote refs before retry; never blindly replay effects.
7. **Unvalidated live APIs:** no real external integration test was run; response semantics and permissions may differ by installed token, model and repository configuration.

## Operational response

On suspicion of credential exposure, stop execution, restrict access, review logs/provider records and rotate or revoke affected credentials using their normal management process. If a remote publication has an uncertain result, inspect the exact branch, commit and PR before any recovery attempt. The CLI intentionally avoids destructive cleanup.

## Reporting

Report vulnerabilities privately to the project owner; do not publish secrets or token-bearing reproductions. This package has no hosted issue tracker or incident-response SLA.
