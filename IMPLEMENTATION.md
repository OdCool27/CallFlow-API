# Implementation report

Completed October 26, 2026 (America/Jamaica).

This section records the original implementation run. Current setup and commands are maintained in [README.md](README.md); the October 27 documentation/readiness review is recorded below. Statements about a running process describe the earlier run, not current process state. The maintainer subsequently reports successful normal SIP hangup after troubleshooting; the earlier stale-channel observation remains part of the historical test record.

## Changes

Preserved FastAPI routers, Pydantic, SQLAlchemy, SQLite, customer management, and educational T-SQL. Replaced simulated REST-driven calls with AMI event-driven persistence. Added an async authenticated client with heartbeats, bounded reconnection, lifecycle cleanup, and an OS listener lock. The ordered reducer correlates channel identifiers, measures observed bridge intervals, handles duplicates and dispositions, and reconciles incomplete calls after a connection gap.

The API exposes independent application/PBX health, endpoint availability, active calls, filtered history, call metadata editing, and persisted reports. It deliberately rejects manufactured calls and manual PBX state changes. Origination is omitted because this local observer has no API authentication.

## Files created

- `.gitignore`, `.env.example`
- `app/config.py`, `app/ami.py`, `app/telephony.py`, `app/migrations.py`
- `app/routers/asterisk.py`
- `tests/conftest.py`, `tests/test_ami_client.py`, `tests/test_migrations.py`, `tests/test_telephony.py`
- `IMPLEMENTATION.md`

## Files modified

- `README.md`: full setup, configuration, API, demo, troubleshooting, limitations, validation record.
- `app/database.py`, `app/models.py`: configurable SQLite, enforced foreign keys, new call/channel/endpoint fields and relationships.
- `app/main.py`: startup/shutdown integration and real database health check.
- `app/schemas.py`: typed call timing, AMI and endpoint responses; validated metadata changes.
- `app/routers/agent.py`: optional department compatibility and duplicate-extension race handling.
- `app/routers/call.py`, `app/routers/report.py`: authoritative AMI calls, filtering, connected-time reports.
- `requirements.txt`: adds `python-dotenv==1.2.4` to the existing dependencies.
- `tests/test_main.py`: replaces database-polluting tests with isolated API/database tests.
- `test_ami.py`: existing untracked user file refactored into an explicit configuration-based login probe, removing its embedded password and import-time network operation.

`sql/procedures.sql` and the existing customer router were retained unchanged. A local `.env`, `.venv`, and `callflow.db` were prepared; all are ignored by Git. Nothing was committed or pushed.

## Database

The repository initially had no runtime database file in this workspace. Startup created schema version 1. Calls allow optional customer/agent associations and persist Linkedid, timing, disposition, and tracking completeness. `call_channels` records Uniqueid and bridge membership; `endpoints` caches contact/device states. Indexes support reporting and correlation.

An original-schema upgrade is supplied and tested: it takes a SQLite backup, preserves old rows/IDs/notes as LEGACY, adds nullable associations and AMI fields, and creates the new tables. Legacy/incomplete conversation durations are excluded from averages. No SQL Server stored procedures execute at runtime.

## Verification executed

- `python -m pytest -q`: **31 passed**, two deprecation warnings from the existing FastAPI/Starlette test dependencies.
- `python -m compileall -q app tests test_ami.py`: passed.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed (Git also reports LF-to-CRLF notices).
- Real AMI authentication, channel/contact/device snapshots, clean shutdown, restart, and persistence: verified.
- Real MicroSIP 102-to-103 call: one call, two channel records, observed ringing/answer/bridge events; final COMPLETED record and report verified after targeted user-approved AMI cleanup.
- Final running API: healthy, AMI connected/synchronized, no active calls, 102 and 103 reachable/idle, one completed persisted call.

## Important live finding

Both clients appeared idle while an independent Asterisk channel snapshot still reported both demo channels Up in a bridge. The API correctly retained that PBX state. With explicit approval, only those two stale channels were ended through AMI. The observer then persisted their hangups and finalized the call.

Connected time was approximately 405.354 seconds and elapsed time 408.405 seconds. These include the interval retained by the PBX, not verified conversation time. The cause of normal SIP teardown failure is unconfirmed. No Ubuntu configuration was changed. Live busy/no-answer and network-outage tests were not performed; synthetic offline tests cover their software behavior.

## Ubuntu follow-up and demo

No Ubuntu change is required for the AMI connectivity already verified. For the teardown issue, use the Asterisk console to compare `core show channels verbose` with the clients. Enable `pjsip set logger on` for a short new test and look for BYE and its response, then run `pjsip set logger off`. Inspect host-only routing, SIP transport/contact addresses, and client firewall settings if BYE does not arrive. Handle SIP traces as private lab data. Do not change the working PBX configuration blindly.

At the end of the original run, the API was running at http://127.0.0.1:8000/docs. This is historical, not a current availability check. For subsequent launches and the complete demonstration, follow README Stages 11 and 12.

## Limits

Single PBX/worker and direct two-party lab calls. No production API authentication, AMI TLS, origination, queue-login tracking, transfer/conference participation model, external-trunk direction inference, or CDR/CEL historical backfill. AMI cannot recover calls that occurred entirely during downtime; incomplete observations are flagged. Timing uses event receive time and PBX bridge membership, not speech detection. Normal SIP teardown was unresolved at the end of this original run; subsequent maintainer-reported success is distinguished from that historical observation above.

## Documentation and GitHub readiness review — October 27, 2026

This review preserved the working implementation. Only `README.md`, this report, `.gitignore`, and comments in `.env.example` were changed during this task. Existing uncommitted application/test changes from the integration task remain in place; they were neither reverted nor staged. Dependencies and runtime configuration values were not changed. The user's local `.env` was inspected without printing its secret and was left unchanged.

### Documentation delivered

README is the single setup/reference guide. Its structure is:

- Project overview, tested Windows/Ubuntu split, architecture diagram, stack, and repository structure.
- Twelve numbered stages: prerequisites; Ubuntu VM and NAT/host-only networking; SSH; Asterisk installation; configuration backups; PJSIP 101/102/103; internal dialplan; isolated portable MicroSIP 102/103 with distinct local ports; SIP call/normal hangup; AMI; Git/Python/FastAPI/database startup; end-to-end persistence/reporting verification.
- Environment variable reference, database upgrade/restore behavior, call tracking/recovery and duration definitions, actual API routes, offline tests, practical troubleshooting, GitHub preparation, limitations, and official references.

The instructions distinguish Windows PowerShell, Ubuntu shell, and Asterisk CLI. IPs are labelled lab examples; new installations substitute their actual host-only addresses. Asterisk and Python versions are reported as tested versions rather than guarantees about what current package repositories install. Startup performs the actual database migration automatically; no nonexistent migration CLI is documented. The application has no call-control endpoints.

The maintainer reports that normal SIP hangup was subsequently demonstrated after troubleshooting. README records that report, while this file preserves the earlier controlled cleanup as history. No fresh VM installation, real SIP call, AMI connectivity test, or audio/hangup test was performed during this documentation review. No Ubuntu settings were changed.

### Git and secret hygiene

- Inspected `git status`, `git ls-files`, publishable untracked files, the local configuration, source/tests/docs, and all nine locally available commits.
- No sensitive local artifact is currently tracked. No tracked file needed removal from the index; local files were preserved.
- No match for the locally configured AMI secret was found in publishable working-tree files or those nine commits. A separate credential-assignment pattern scan found only placeholders, configuration references, and synthetic test credentials in the working tree, and no credential-assignment candidates in committed history. This is a targeted review, not an exhaustive secret-scanner certification.
- Expanded `.gitignore` for `.env.*` while explicitly allowing `.env.example`, both virtual-environment names, Python/tool caches, coverage output, SQLite formats/sidecars/backups, AMI locks, IDE/OS artifacts, logs, and packet captures.
- Verified 25 representative local-artifact paths are ignored and seven representative required project paths (including migrations, tests, SQL, and the template) remain publishable. There are no required database/capture fixtures hidden by these rules in the current repository.
- `.env.example` has exactly the 11 settings used by `app/config.py`, with no missing/extra keys. Its secret is a placeholder; its host address is explicitly labelled a lab example. The local `.env` also contains all 11 keys. Only explanatory comments were added to the template.
- No credentials were rotated, no Git history was rewritten, and no commit or push was performed.

### Validation executed in this review

| Check | Result |
|---|---|
| `python -m pytest -q` | 31 passed; two existing FastAPI/Starlette dependency deprecation warnings |
| `python -m compileall -q app tests test_ami.py` | Passed |
| `python -m pip check` | No broken requirements |
| Installed versions versus requirements.txt | All 25 pins match |
| Template/local configuration keys versus source | 11/11 match; no secret values printed |
| Fresh temporary directory with copied app and untouched template as .env | Settings loaded correctly; then AMI was explicitly disabled for an offline startup; database schema creation, health, empty history, and disabled-PBX status passed |
| Markdown | Twelve stages, balanced code fences, existing local link targets; commands/routes checked against source |
| `git diff --check` | Passed; Git reports line-ending conversion notices |
| Official links | Asterisk, MicroSIP, Ubuntu, Python, Git, and Oracle networking references checked through browsing; the VirtualBox download site could not be fetched by that tool (402), so the official download pointer remains for manual checking |

The clean-directory check used the already installed pinned packages; it was not a new package download, a remote GitHub clone test, or a complete Windows/VM reinstall. Dependency installation had been verified in the earlier integration run.

### Readiness and remaining manual work

The working tree is prepared for a reviewed commit, not automatically published. New integration modules, tests, `.env.example`, `.gitignore`, and this report are still untracked until the maintainer intentionally stages them. Include the complete implementation when publishing: cloning the current remote alone may not yet reproduce these uncommitted changes. Keep secrets, databases, caches, portable SIP client settings, and traces out of the commit.

On a second computer, follow the twelve stages: install the free tools, create/configure the VM, use actual host-only addresses, configure three endpoints and the dialplan, choose private local SIP/AMI passwords, register 102/103 in independent portable instances, create the local `.env`, and start the single-worker API. Normal hangup, channel closure, audio, persistence, agent attribution, and reports still need to be demonstrated on that new environment.

No new implementation defect was found in this review. The existing single-PBX/worker, local unauthenticated API, plain-TCP AMI, and missed-event/backfill limits remain documented. Normal hangup resolution is maintainer-reported rather than independently re-tested here. A repository license has not been selected; choose one separately if open-source redistribution is intended. The official VirtualBox download link is the remaining manual link check. No Git commit or push was made.
