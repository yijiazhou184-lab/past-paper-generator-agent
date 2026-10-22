# Batch 2 — course analysis, editing and confirmation

> Execution addendum to the approved 2026-10-19 plan, Tasks 3–4. Follow the existing plan directly; no unavailable Superpowers runner is required. User authorised implementation on 2026-10-23.

## Task 3: durable analysis and evidence contracts

- Add `backend/app/courses/{schemas,context,analysis,clarifications}.py`, `ai/prompts/course_analysis.md`, course persistence models/migrations and the `analyse_course_one` worker command.
- First write semantic and snapshot tests in `backend/tests/test_course_analysis.py`: provenance, cross-course references, missing teaching evidence, scope vs coursework vs old mock, targeted gaps, refusal/incomplete/error, cancelled publication and manual edits during analysis.
- Use the existing official Responses adapter, fixed endpoint, strict schema, store:false, no tools, bounded calls, leases and unique publication. Freeze prompt, schema, materials, statements and context hash. A completed course draft is not a correctness certificate.
- The user authorised 36 physical pages of extracted text and the five existing page-review candidates on 2026-10-23. Store the exact content hash in an explicit analysis grant. Do not send new page images or arbitrary files. Profile actions show the proposed scope; a changed payload requires an explicit new grant.
- Build one bounded conceptual analysis call first; no automatic repair loops or silent context truncation. Preserve provider failures and unknown outcomes. A supported partial course can continue; irrelevant gaps are informational.
- Stable commit after Task 3 tests and migration checks.

## Task 4: profile and immutable versions

- Add `courses/{drafts,confirmation,api}.py`, generated OpenAPI contracts, `frontend/src/features/profile/{ProfilePage,useDraftSave,profile.css}` and typed profile contracts.
- Save only editable fields with expected revision and an idempotency key. Preserve provenance, machine base and manual overrides separately; reanalysis merges into the latest local draft rather than overwriting user edits. Changed machine text with an override is shown as a merge warning.
- Answers append user statements; answering cannot fill missing teaching evidence or turn a user claim into an official fact. Record reanalysis needs explicitly, without automatically paying for a model call.
- Confirmation checks saved revision, current input manifest, valid suggested template and selected-scope blockers; freezes payload, evidence and statements in an immutable version. Generate reads that version but planning remains batch 3.
- Profile UI: source drawer at exact evidence ID, 800ms serial autosave, explicit save/retry, retained local input, conflict comparison, confirmation preview, version history, latest task recovery. Keep batch-one materials/prototype intact.
- Tests: `test_course_drafts.py`, `useDraftSave.test.tsx`, `scripts/test_course_profile.py`; ownership, stale writes, lost response, edits while save in flight, unanswered blockers, old frozen version unchanged, keyboard/narrow screen and refresh.
- Stable commit after checks and real analysis evidence, then report the actual outcomes.

## Planned checks (not evidence of execution)

`python -m pytest -c backend/pytest.ini backend/tests -q`; `manage.py check`; `manage.py makemigrations --check --dry-run`; `manage.py spectacular --file contracts/openapi.yaml --validate`; `pnpm --dir frontend api:types`; `pnpm --dir frontend test --run`; `pnpm --dir frontend build`; Python Playwright profile checks; batch-one regression. Use `.venv/Scripts/python.exe` and the existing managed local PostgreSQL services. Results go in `docs/batch-2-validation.md` with actual task IDs, timestamps, failures and limitations.

AC: P0-04 / AC-04-01–03; P0-05 / AC-05-02–03; P0-06 / AC-06-01,03 and the analysis/answer merge portion of AC-06-02; P0-12 persistence/cancellation; P0-14 ownership. Full add/delete material invalidation, web augmentation, generation and PDFs are outside this batch.
