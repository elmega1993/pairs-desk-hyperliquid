# Desk Memory Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent store/UI tasks; controller integrates orchestration and API. Work in the active checkout: essential advisor sources and preceding changes are uncommitted; preserve them. No bulk commits/reset/worktree migration.

**Goal:** Desk remembers relevant preferences/rules across backend restart and independent conversations, with verified current data and no orders.
**Architecture:** Extend existing Advisor, scope-bound MemoryStore, budgeted ContextBuilder, strict registry and same-origin API; reuse React streaming.
**Tech Stack:** Python/FastAPI/Pydantic, SQLite FTS5, React/TypeScript, existing Ollama.
**Spec:** docs/superpowers/specs/2026-11-10-desk-memory-design.md (implements user's full specification).

## Global constraints
No trading changes, no new Hyperliquid polling or model downloads. Existing sources are uncommitted; preserve all unrelated changes. Durable memory belongs in private local data directory. All list endpoints paginate. Inferential memory is pending review. Account context always checked for freshness. No external providers without explicit configuration.

## Review focus
- Disconnect/failure must leave user message and incomplete response, not success.
- Switching conversations/scopes must not leak previous context.
- Expired/inactive/conflicting memories must not enter retrieval.
- A memory containing instructions cannot escalate tool access.
- Delete removes content from search/revision/vector state; backups explicitly separate.

## Tasks
- [x] 1. MemoryStore (`pairs_desk/ai/memory.py`, `embeddings.py`, tests/test_desk_memory.py): migration/version schema, all required memory fields, scope isolation, revisions, FTS5, optional vectors, ranked bounded retrieval, dedup/conflicts/expiry, CRUD/import/export/backup, conversations/messages/summary/settings. Red then green.
- [x] 2. Identity/context/acquisition (`pairs_desk/ai/identity/*`, context.py, acquisition.py, tests/test_desk_context.py): files loaded at init, budgets, relevant data as untrusted, deterministic explicit candidates, pending inference, source and corrections. Red then green.
- [x] 3. Advisor/API integration (`local_advisor.py`, advisor_routes.py, desk_routes.py, read_only_server.py, tests/test_desk_integration.py): server-derived scope, persistence, modes, enforced tool prefetch, strict registry extended with memory/rules/exposure/current ratio. Maintain legacy input and streaming. Red then green.
- [x] 4. React (`Advisor.tsx`, Desk panels, advisorApi.ts, style.css, JS tests): history pagination, independent chats, modes, memory/rules/settings/import/export, evidence. No trading UI changes. Red then green.
- [x] 5. Regression and real verification: focused pytest + JS, full suite compare baseline, Vite build, local Ollama persistence/GPU scenario. Independent review, fix important issues, document limitations and technical decisions.

## Shared contracts
MemoryStore methods accept scope first. scope is server-derived, never browser-provided. Conversations rows `{id,title,summary,created_at,updated_at}`; messages `{id,role,content,status,metadata,created_at}`. Lists envelopes `{items,total,offset,limit}`. Memory fields match user spec plus retrieval explanation if returned.
API prefix `/api/advisor`: GET/POST conversations; GET/DELETE conversations/{id}; GET conversations/{id}/messages; GET/POST memories; PATCH/DELETE memories/{id}; GET/PATCH settings; GET export; POST import; POST backup; DELETE data (confirmation DESK). Chat adds optional conversation_id and mode auto/chat/analyze/research; start/done carry conversation_id and mode; done carries memories_used and sources. Legacy history accepted; persistent calls use stored history only. Mutations require same Origin. Settings includes personal_rules, temperature, max_tokens, memory_budget, history_budget and enabled acquisition. POST memories creates explicit user entry, pending inferred proposals editable/approvable. Export response JSON; import bounded format validated. Frontend default uses these endpoints.

## Progress
- Audit complete; full baseline 376 passed, 2 prior failures, 1 skipped.

- Tasks 1–4 complete: TDD store/context/API/UI, independent reviewer findings fixed (atomic scope/account, unrelated vs contradictory preferences, mixed intent freshness, aggregate budgets, recent summary preservation). Additional regression: real checksum addresses, full 17-pair/34-position portfolio without loss, timeout/failed-persistence slot release.
- Ruling: preserve active checkout because the entire existing advisor and preceding changes are uncommitted; no reset/cleanup/bulk commit. Cost if wrong: changes need later selection for version control.
- Ruling: semantic similarity proposes duplicates; explicit consolidation preserves originals/provenance instead of merging opposite preferences automatically. Cost: user reviews ambiguous duplicates.
- Ruling: no installed embedding model selected; FTS5 defaults to working without downloads. Optional adapter explicitly configured, cloud blocked before transmitting text. Cost: lexical recall until configured.
- Ruling: local app does not gain fictitious multiuser authentication; scope is OS-user+account and request origins/hosts use existing trust boundary. Any multiuser deployment requires real auth. Cost: trusted local/private access remains essential.
- Independent review completed; important findings fixed by regression tests. No commits because mixed pre-existing changes must remain reviewable.

- Final: 445 passed, 2 prior failures, 1 skipped; 84 advisor/Desk focused tests pass, three JS suites pass, Vite/compileall/diff check pass. Real Qwen memory across app reconstruction and another process, funding and whole-portfolio evidence verified. Browser desktop/mobile no overflow/JS exceptions. Residual generative risk documented (sample currency label, strengthened identity).
- Deferred minor: retrieval is lexical until optional local embedding model is configured; external Research providers are not configured (intentional scope/availability limits, not simulated capabilities).
