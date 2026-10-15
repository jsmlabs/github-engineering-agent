# Security policy and operating boundaries

[README](README.md) · [Architecture](docs/ARCHITECTURE.md) · [Verification](VERIFICATION.md)

> [!WARNING]
> **Reference implementation, not a security certification.** This tool can publish AI-generated code to a remote draft pull request. A draft still exposes code to anyone with repository access and may trigger downstream automation. Use it only on repositories and files you are authorized to modify, with least-privilege credentials and independent review gates.

## Security model

The model proposes **data**, not executable authority. The trusted Python/Git layer enforces file selection, inputs, consent flags, revision checks, and observable tool outcomes. Repository source, issue text, model output and remote responses are treated as untrusted until checked at the relevant boundary.

| Source or component | Threat | Enforced boundary | Residual risk |
| --- | --- | --- | --- |
| GitHub issue text | Prompt injection, disguised commands, private data | Open-issue check, size bound, known-token heuristics; no authority from issue | Model may still be influenced; private information may escape heuristics |
| Selected repository files | Secrets, hidden paths, unsafe source | Exact operator allowlist, tracked regular UTF-8 files, protected paths, size and known-token checks | Other sensitive content can be present; data sent to provider |
| Model response | Unauthorized edits, malformed code | Strict edit structure, original SHA, allowlisted paths, limits, Python/JSON parsing | Correct-looking code may have bugs or backdoors |
| Local checkout and Git | Unexpected side effects, race conditions | Clean checkout, exact origin, recorded SHA, staged path and committed byte checks | Host, hooks/filters, helpers, concurrent writers or malicious repository may be unsafe |
| Proposal and receipt files | Tampering, stale approval | Separate private files, SHA-256 binding, recorded branch/commit | Local attacker able to rewrite files can forge an unkeyed hash |
| GitHub push and PR API | Stale branches, collision, partial effects | Exact refs, create-only push lease, issue/base rechecks, expected open draft PR | Push and PR creation are not atomic; review/CI may run automatically |

### Authorization and scope

- **Read/plan:** explicit `--allow-source-upload` is required before issue/source data is sent to the model provider. `--allowed-file` is an exact per-file list, not a pattern or recursive grant.
- **Local edit:** `apply` requires both `--approve` and the exact SHA-256 printed by `review`. It only writes eligible pre-existing tracked files and creates a local feature branch.
- **Remote publish:** `publish` independently requires `--approve-publish`, a matching receipt and remote preconditions. It may create a remote branch and an **open draft PR**; it cannot merge or deploy.
- **Combined automation:** `run` requires explicit source, local and remote authorizations but **does not pause for human inspection of the generated edit**. Treat it as a high-trust, low-risk-only mode.

Nothing in GitHub issue text, repository files or model output may expand these permissions. The caller must also enforce GitHub token scopes, branch protections and organization policies independently.

## Deployment and credential hygiene

1. Operate in a **dedicated, clean and trusted checkout**, preferably an isolated worker. Avoid shared worktrees or concurrent mutators.
2. Use a short-lived, repository-scoped GitHub credential with **Issues: read**; add **Contents: write** and **Pull requests: write** only for publication. Supply Git push credentials separately via an approved credential helper or SSH identity. No token belongs in a Git remote URL or command-line argument.
3. Use a model credential with approved data-processing/retention terms. Plan mode sends issue text and the full contents of selected source files to the provider. Classify data **before** opting in. The built-in scanner is heuristic, not a DLP system.
4. Keep proposal JSON, receipts and terminal review output private. Proposal files contain complete replacement source; terminal diff output may reveal sensitive code. Check filesystem ACLs, backups and central logging policy.
5. Independently test and review proposed changes before publication where practical. Before merge, enforce required branch protections, CI, maintainers' reviews, code scanning and deployment policy **outside this tool**.
6. Audit the trusted Git executable, global/local configuration, credential helpers and filters. This tool does not sandbox those dependencies. Git hooks are disabled for invoked Git commands where supported, but that does not neutralize all execution or supply-chain risks.

## Explicitly unsupported

The program does **not** support automatic merge, deployment, PR review approval, workflow modifications, broad filesystem edits, new files, deletion, arbitrary shell execution suggested by the model, automatic selection of target-project tests, cryptographic attestation, full secret detection or generalized recovery from all ambiguous failures. The operator may explicitly configure isolated test execution through `verify`.

It performs no live proof of generated code's security, maintainability or compliance. Python `ast.parse` and JSON parsing are syntactic checks, not runtime execution or semantic validation. Other allowed file formats need independent tooling.

## Partial failure and incident response

**Do not blindly retry a failed mutating operation.** A transport timeout may mean the remote change already occurred. Consult [Architecture and recovery](docs/ARCHITECTURE.md) and inspect exact GitHub refs, issue revision, PR head/base and draft state before acting.

- **After local apply failure:** preserve branch/worktree/receipt evidence; there is no automatic destructive rollback. Inspect before making further changes.
- **After uncertain push/PR creation:** verify the exact remote branch commit and PR state. Stop if a collision, stale base, closed PR, incomplete search result or malformed PR response appears.
- **Suspected credential exposure:** stop use, restrict access, preserve relevant non-secret evidence, revoke/rotate compromised credentials and audit GitHub/provider activity. Avoid sharing token-bearing logs.
- **Suspected malicious generated change:** stop publication or review/merge, inspect the approved proposal and committed blobs, assess whether the change reached a remote branch, and follow the repository's incident process if necessary.

## Reporting vulnerabilities

Report security defects privately to the repository owner through an established private contact channel. Do not post credentials, exploit secrets or sensitive reproductions in public issues. **No response SLA or managed security-support process is advertised for this reference project.**

## Assurance and evidence

The project has deterministic offline tests, including temporary Git repositories and simulated GitHub/OpenAI requests. Their observed scope is recorded in [VERIFICATION.md](VERIFICATION.md). They **do not establish** real GitHub authorization behavior, production security, live model compatibility, CI quality, or overall reliability in an arbitrary target repository.


## Optional isolated verification and publication gate

`verify` accepts only a trusted, preloaded digest-pinned Docker image and an explicit JSON argv array. It uses a read-only checkout mount, `--network=none`, no Linux capabilities, no-new-privileges, an unprivileged container user, read-only root filesystem and bounded CPU, memory, PIDs, execution time and temporary scratch storage. No shell is implicitly introduced. **A Docker daemon remains a trusted host-level dependency; these options are not a sandbox against daemon compromise, kernel vulnerabilities or unsafe host configuration.** Run on a dedicated, rootless/isolated worker. Container image provenance and test correctness remain operator responsibilities.

`publish` requires a matching commit-bound PASS record. The explicit `--approve-unverified --unverified-reason` path permits an auditable exception only when no test report exists; a recorded test failure or mismatched commit can never be overridden by that flag. The verification report is a private, local, *unsigned* record under the existing trusted-filesystem assumption, not an attestation. Report output excerpts can contain sensitive text and must not be broadly shared. `status` reads local state and optionally a remote branch; it never repairs, resets, or mutates state.
