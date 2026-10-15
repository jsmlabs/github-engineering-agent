# Local verification record

Date: 2026-10-15
Release: 0.2.0 (standalone reference package)

## Environment

- Python 3.13.5
- Git 2.47.3
- Linux build/test environment
- No live OpenAI request, real GitHub push, or live GitHub pull request

## Checks exercised

| Check | Evidence/result |
| --- | --- |
| `python -m compileall -q gh_agent tests` | PASS |
| `python -m unittest discover -s tests -v` | 38/38 PASS, deterministic offline tests |
| `python -m gh_agent --help` | PASS |
| `python -m gh_agent apply --help` | PASS, SHA-256 approval required |
| Temporary local bare-Git create-only lease test | PASS, a competing update is rejected |
| Mocked GitHub draft PR publication/retry | PASS under simulated service responses |
| Full CLI `run` path with model/GitHub stubs | PASS under simulated service responses |
| Clean archive extraction and re-execution | PASS: executed from clean ZIP extraction on 2026-10-15 |
| Offline wheel build and import smoke test | PASS: wheel built without network, installed locally and import smoke-tested on 2026-10-15 |

## Exclusions / residual uncertainties

- Real GitHub REST authentication, repository rules, draft PR creation, race timing, remote push permissions and rate limits are NOT VERIFIED.
- Real OpenAI Responses Structured Outputs requests and provider/model compatibility are NOT VERIFIED.
- Target repository tests, code quality, security review, CI, merge and deployment are NOT VERIFIED. No target code was changed.
- Local Git push to a temporary bare repository is not an end-to-end GitHub integration test.
- Linux verification does not establish native Windows/macOS compatibility.
- The tool is a bounded reference implementation, not a general-purpose unattended production software engineer.

## Acceptance interpretation

The release satisfies the checked local CLI, validation, packaging and simulated side-effect contracts. Real external integration and target-specific correctness remain outside observed evidence. A test pass is not a security certification or a claim of production readiness.
