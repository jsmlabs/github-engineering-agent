# Verification and evidence

[← README](README.md) · [Architecture](docs/ARCHITECTURE.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

> [!IMPORTANT]
> **Evidence ledger, not certification.** A green offline test matrix verifies the checks that actually ran for **that commit**. It does not prove authenticated OpenAI/GitHub integration, safe generated code, trusted Docker execution or production readiness.

## Last inspected integrated baseline (before this change)

**Merged PR [#32](https://github.com/jsmlabs/github-engineering-agent/pull/32) on `main`, inspected 2026-10-16.** The results below apply to the baseline commit, not to this unmerged packaging change.

| Item | Observed evidence |
| --- | --- |
| Inspected `main` commit | [`113bbf64ee9eef5a35be50a8caabd7c30907bf07`](https://github.com/jsmlabs/github-engineering-agent/commit/113bbf64ee9eef5a35be50a8caabd7c30907bf07) |
| Offline CI on that commit | [Run 38861070720](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38861070720): **completed / success**, seven test jobs |
| Test coverage observation | [PR-head run 38860858920](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38860858920): Ubuntu/Python 3.13 passed **133 offline tests**, including malformed-state regressions |
| Baseline metadata | Unpublished development version `0.3.0.dev1` |
| Proposed metadata | Unpublished development version `0.3.0.dev2`; not a release |
| Distribution and live integration | No independently observed wheel build/install, signed distribution or authenticated GitHub/OpenAI workflow at this baseline |

**New verification gate proposed in this PR:** the existing seven offline regression jobs plus three OS-specific Python 3.11 wheel-build/install jobs. Only exact-commit CI evidence can establish that this new gate passes.

## Recent change evidence

| Scope | PR-head CI | Integrated target-branch evidence | What it establishes |
| --- | --- | --- | --- |
| [#12 strict JSON](https://github.com/jsmlabs/github-engineering-agent/pull/12) | [38809280416](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38809280416), **6/6 pass** | [38809470388](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38809470388), **success** on `afb17a292c3e4979a1a77a6fbb431c69d51a9228` | Local state, API/model JSON and source JSON parsing regressions in the offline suite |
| [#13 CI action pinning](https://github.com/jsmlabs/github-engineering-agent/pull/13) | [38809679328](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38809679328), **6/6 pass** | [38809884465](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38809884465), **success** on `e1f63c573ef30467cef54e801175818dd000595b` | SHA-pinned official GitHub Actions function in the configured matrix |
| [#14 model/recovery hardening](https://github.com/jsmlabs/github-engineering-agent/pull/14) | [38810108472](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38810108472), **6/6 pass** | [38810284708](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38810284708), **success** on `5c698720bc6de352d08e83b6d790fbeb9d14a757` | Offline regressions for model output, outbound JSON and recovery handling |
| [#15 documentation refresh](https://github.com/jsmlabs/github-engineering-agent/pull/15) | [38812066285](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38812066285), **6/6 pass** | [38812223896](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38812223896), **success** on `48eed2ab94909e0232937b3db3ed6351351a570e` | Documentation-only structure and navigation alongside unchanged source tests |
| [#16 README visual refresh](https://github.com/jsmlabs/github-engineering-agent/pull/16) | [38813390691](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38813390691), **6/6 pass** | [38813621301](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38813621301), **success** on `1001bbf3390f171186d8feb4ebbaf49463530492` | Documentation-only presentation improvements |
| [#17 JSON hardening](https://github.com/jsmlabs/github-engineering-agent/pull/17) | [38814929977](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38814929977), **6/6 pass** | [38815112621](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38815112621), **success** on `45d49e3436cc53cf8cbc38df43463ba394d09bcd` | Offline regressions including overflowed numbers, Unicode validation and bounded state JSON |
| [#18 expanded scope](https://github.com/jsmlabs/github-engineering-agent/pull/18) | [38820016938](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38820016938), **6/6 pass** | [38820648522](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38820648522), **success** on `98a2139c4474be54fcdb3f462ebf8834e6c6cc69` | Offline 74-test suite includes new file, workflow-review gate, isolation and PR-readiness regressions |
| [#19 type and transport hardening](https://github.com/jsmlabs/github-engineering-agent/pull/19) | [38821493237](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38821493237), **6/6 pass** | [38821668140](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38821668140), **success** on `00e5db16842be3034831cb1b7540b9507f76c2ed` | Offline regressions for exact verification exit-code types, issue number typing and disconnected API responses |
| [#20 three-pass quality improvements](https://github.com/jsmlabs/github-engineering-agent/pull/20) | [38823292220](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38823292220), **7/7 pass** | [38823441682](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38823441682), **success** on `0e0c6ec5c431ad600138175d7ee032899df1c91e` | Offline 79-test suite across 7 OS/Python jobs including Ubuntu/Python 3.12 |
| [#21 guided terminal UX](https://github.com/jsmlabs/github-engineering-agent/pull/21) | [38824736177](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38824736177), **7/7 pass** | [38824915815](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38824915815), **success** on `d87eae27f0f4978b4f3e7075cc1810bf3a54f172` | Offline 83-test suite plus CLI start/help smoke across seven jobs |
| [#22 interactive terminal menu](https://github.com/jsmlabs/github-engineering-agent/pull/22) | [38825599974](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38825599974), **7/7 pass** | [38825769320](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38825769320), **success** on `4511a89f97e1e0eb1b67baadee1c4a44bbf967e5` | Offline 87-test suite with menu, TTY, no-color and safe-navigation regressions |
| [#23 dashboard and catalog](https://github.com/jsmlabs/github-engineering-agent/pull/23) | [38826491153](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38826491153), **7/7 pass** | [38826698236](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38826698236), **success** on `5ba2d2607c4b23e8a19417af1626f4e3009ad497` | Offline 92-test suite including dashboard-state and command-catalog regressions |
| [#24 workspace and plan preview](https://github.com/jsmlabs/github-engineering-agent/pull/24) | [38827438995](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38827438995), **7/7 pass** | [38827691004](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38827691004), **success** on `b589a95ebbfc688afb998614f5c7ce59a56ab3b3` | Offline 97-test suite with workspace, dry-run plan-preview and menu safety regressions |
| [#25 file finder and task recipes](https://github.com/jsmlabs/github-engineering-agent/pull/25) | [38829976622](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38829976622), **7/7 pass** | [38830186202](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38830186202), **success** on `98b950c90616141ff2510d530361f6d599f08afe` | 102 offline tests including menu, file scope and static recipe coverage |
| [#30 offline installer and GUI launchers](https://github.com/jsmlabs/github-engineering-agent/pull/30) | [38853767093](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38853767093), **7/7 pass** | [38854528719](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38854528719), **success** on `115eaae86f0394c6e99262e8ff09cb9ae678754b` | 130 offline tests cover local wheel installation, recovery, launcher prerequisites and related contracts; not a real desktop E2E test |
| [#31 long-running launcher fix](https://github.com/jsmlabs/github-engineering-agent/pull/31) | [38858644621](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38858644621), **7/7 pass** | [38858874008](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38858874008), **success** on `e60013f8951722730c0154a0bcc7562b65f29284` | 131 offline tests on PR head, including launch contract regression; real desktop endurance testing remains open |
| [#32 strict installer state validation](https://github.com/jsmlabs/github-engineering-agent/pull/32) | [38860858920](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38860858920), **7/7 pass** | [38861070720](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38861070720), **success** on `113bbf64ee9eef5a35be50a8caabd7c30907bf07` | 133 offline tests on PR head, including strict installer state parsing; no wheel distribution validation |
| Older reference integration | N/A | [38798940522](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38798940522), **success** on `b3b7d871a8f7b36d9ce09dc8f3310ff0fc989f5a` | Earlier verification/recovery implementation's offline workflow |

**Important distinction:** PR and merge activity performed by a GitHub maintainer or separate integration tooling is **not** an authenticated end-to-end test of this CLI's own `publish` method.

## Reproduce the offline checks

Run from a trusted checkout of this repository with Python 3.11+ and Git:

~~~bash
python scripts/verify.py
python scripts/verify_package.py
python -m unittest discover -s tests -v
python -m gh_agent --help
~~~

`scripts/verify.py` runs: (1) `python -m compileall -q gh_agent tests`, (2) verbose unittest discovery, then (3) `python -m gh_agent --help`. The CLI enhancement adds read-only smoke commands for the home screen, guide, doctor help, and next help. It exits nonzero on a failed command.

The default tests use temporary Git repositories and test doubles for network/model behavior. They do not require GitHub/OpenAI tokens or a live Docker daemon. The configured GitHub Actions workflow runs seven offline test jobs plus three Python 3.11 packaging jobs (Ubuntu, macOS and Windows), with read-only repository permission, non-persistent checkout credentials, SHA-pinned actions and a 15-minute job timeout. The package checker requires an already available build backend; package indexes are disabled and no wheel is uploaded. **A successful packaging job establishes only a local wheel build, temporary installation and CLI smoke check on the specific OS.** This CLI UX change additionally tests the home screen, guide and command help; only the exact-commit CI result can establish whether those pass.

### Evidence classification

| Label | Required evidence |
| --- | --- |
| **Executed and passed** | Identified command or CI job, commit, environment and observed success |
| **Offline simulated** | Unit tests with mocks, fixtures or local temporary Git remotes |
| **Not tested** | No observed corresponding runtime call or environment |
| **Inferred from implementation** | Code review supports intended controls but live behavior remains unproven |
| **Not a guarantee** | All results: no finite test suite establishes complete security or semantic correctness |

## Historic checks (retained for provenance)

| Milestone | Observed result | Limitation |
| --- | --- | --- |
| Initial v0.2.0 package validation, 2026-10-15 | Linux, Python 3.13.5, Git 2.47.3; **38/38** offline unit tests, compile and CLI help | No authenticated GitHub/OpenAI calls or target-project CI |
| Initial package build | Clean ZIP extraction/offline checks; offline wheel build/install/import reported **PASS** | Historical environment only; not re-executed in this documentation change |
| Earlier documentation revision | `scripts/verify.py` **38/38 PASS**, local-link checks (32 links/3 fragments), CLI examples inspected | Results apply only to that prior revision |
| Issue #1 malformed PR response | Reproduced unhandled `AttributeError` on malformed nested PR fields; **40/40** after fix | Mocked GitHub responses, no live corrupted response |
| Docker mount-path regression | Negative tests reject actual newline, carriage return and comma in Docker mount paths before subprocess launch | Real Docker invocation not exercised |
| Reconciliation of duplicate PR results | Offline negative test rejects multiple matching PR records | No proof against remote races or pagination beyond returned page |
| Verification gate development | Offline tests cover Docker flags, commit-bound reports, PASS/FAIL gate and mock publication/recovery | No real Docker daemon or full live provider workflow |

Historic results are preserved as historical evidence, **not** as current measurements or independent proof of the latest SHA.

## Expanded engineering capabilities: observed scope

Merged PR #18 adds explicitly approved new files/directories and configuration/workflow edits (with workflow edits excluded from unreviewed `run`), expanded bounded changes, one model call per plan, a writable disposable verification workspace and opt-in review-ready PRs. Its offline checks are recorded above for the exact head and merged commit. Authenticated model/GitHub execution, a real Docker daemon, and generated-code security remain separately **unverified**.

## Remaining verification gaps

| Capability | Current evidence status | Required validation before relying on it |
| --- | --- | --- |
| Live OpenAI Responses Structured Outputs with a chosen model | **Not verified** | Authorized live request, refusal/incomplete cases, budget and API response compatibility |
| Authenticated GitHub issue, push and draft PR workflow | **Not verified end-to-end via CLI** | Controlled test repository, least-privilege credentials, actual remote reconciliation and permission/rate-limit behavior |
| Actual Docker `verify` invocation | **Not verified** | Trusted POSIX host and rootless/isolated daemon, pinned image, timeout/cleanup/failure checks |
| Generated code correctness and target project's test suite | **Not verified** | Independent code review, applicable target tests, CI and branch policies |
| Realistic secret/DLP and vulnerability detection coverage | **Not verified** | Threat assessment and negative tests in the intended operating environment |
| Branch protection, concurrency and adverse production races | **Not verified end-to-end** | Explicit scenarios against permitted test repos with current rules |
| Native Windows Docker verification | **Unsupported** | POSIX execution host required; Windows offline test suite is supported |
| Automatic PR approvals, merge, deployment | **Outside product scope** | Must be implemented and governed by a separate authorized system, if ever required |

## Interpretation and maintenance

- **Supported by current CI:** offline Python compilation, deterministic test fixtures, CLI help and the configured platform matrix for the stated SHA.
- **Supported by source review but not proven live:** limited side effects, draft publication checks, resource bounds and error reconciliation.
- **Not established:** production readiness, arbitrary-repository safety, authenticated vendor integration, semantic validity of model-generated changes or exhaustive security coverage.

When implementation or docs change, append a **commit-specific** evidence entry only after checking the actual workflow run. Record success, pending, failure or unavailable accurately. Do not replace historic observations or misstate test counts.

The operating contracts live in [Architecture](docs/ARCHITECTURE.md), [Security](SECURITY.md), and the [version history](CHANGELOG.md).
