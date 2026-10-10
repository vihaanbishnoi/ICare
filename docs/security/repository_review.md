# Repository security review

## Current verification: 10 October 2026

A refreshed heuristic scan found no credential/private-key matches and no scan
errors in 130 local text/Office items and 253 historical text blobs across 26
locally reachable commits. It covered Git-eligible working files, root .env
variants and local Git remote configuration; output records locations/rule names,
never secret values. Binary models/media, remote-only/unreachable history and
dependency vulnerabilities are outside this credential check. A separate npm
audit of the frontend lockfile reported zero known vulnerabilities; Python/image
dependency review remains pending. Evidence is under ignored
artifacts/security_scan_summary.json. This is not proof that every possible
credential format is absent.

No tracked file matched the active ignore rules. .env variants, private keys,
runtime data, caches, generated reports and frontend node_modules/dist are
excluded. .env.example is non-secret. Local ONNX inference needs no API key.

The new API now implements random owned jobs, anonymous HttpOnly session cookies,
private/no-store results, upload/queue limits and periodic retention. Two-visitor
isolation and owned media/report access passed locally. Catalog media is confined
to its directory. Same-origin proxy handling and concurrent admission were fixed.
Public HTTPS, secure-cookie deployment, measured per-visitor/storage budgets,
container recovery and Python/image dependency review remain pending Deployment owner (Person 5)'s release work.

## Historical preparation review: 7 October 2026

Reviewed on 7 October 2026 against the local working tree and locally available
Git refs. This is a repository review, not a production security certification.

## Credential findings

No credential or private-key matches were found by a local heuristic scan of
62 text files / Office archives and 37 historical text blobs across seven
reachable commits. Notebook content and generated Office XML were included.
The local Git remote configuration was also checked for embedded credentials.
The scan printed only locations and rule names, never matched secret values.

Patterns covered private-key headers, common AWS, GitHub, OpenAI, Google, Slack,
Stripe, and Hugging Face credentials, JWTs, credentials embedded in service URLs,
and common literal password/token/key assignments. No scan read errors or
large-file skips were reported. The application currently needs no API key to
run its local model pipeline.

Limits: this scan cannot prove the repository is secret-free. It did not validate
credentials with providers, fetch remote-only branches, inspect unreachable Git
objects, inspect binary models/media, or audit dependency vulnerabilities.
Unknown credential formats can evade pattern matching. The reproducible local
scan script and detailed summary are under ignored `artifacts/`.

## Git exclusions

`.gitignore` already excluded `.env` variants, Python environments, caches,
reports, and training checkpoints. This review added generated chart folders,
local build/finalizer scratch folders, presentation output, package build output,
and common local credential/private-key paths. `.env.example` remains shareable;
it must contain only placeholders. The deployable ONNX model, source, tests,
tools, and docs remain eligible for version control.

Ignore rules prevent accidental additions; they do not remove files already
tracked or erase Git history. No tracked files matched the active ignore rules
in this review. If a real secret is ever discovered in a commit, revoke/rotate
it at the provider first and coordinate any necessary history cleanup.

## Deployment findings

For the new product, Development owns job/result isolation and Deployment owner (Person 5) coordinates
hosting, limits, retention, and secret management. The public example/upload
journey requires no account login; browser/job ownership must still protect
private uploads and reports. This is the target design, not an implemented fix.

The previous UI used a global webcam/shared backend and an unreliable upload
loop. That UI and launcher have now been removed. Retained report helpers still
use predictable paths and are field references, not a secure job-storage design.
The new API must implement owned results, quotas, retention, and cleanup before
public release; none of those features exists merely because it is documented.

Use host-managed secrets for any future hosting, TURN, or alert credentials;
grant teammates individual access instead of putting keys in the repository or
handoff document. Complete CI secret scanning and dependency review before
release. Credential scanning is now configured in `.github/workflows/security.yml`;
its first GitHub execution remains pending. The workflows use read-only repository
permissions and verified commit pins for third-party actions. Gitleaks PR comments
and scan-artifact uploads are disabled. The action currently targets this personal
account repository; moving to an organization requires reviewing its licence
requirements. See the [Gitleaks action documentation](https://github.com/gitleaks/gitleaks-action).

A follow-up local heuristic scan after restructuring inspected 58 local text
files/Office archives and 57 historical text blobs across seven reachable commits,
with no matches or scan errors. See [team handoff](../development.md)
for owners and acceptance criteria.
