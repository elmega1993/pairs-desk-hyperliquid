# Cuenta and Risk KPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose summed core/XYZ account value from the backend and replace separate exposure/margin cards with a combined Account and Risk KPI card.

**Architecture:** Add `account_value_total` to the existing read-only summary using already fetched margin summaries. Derive free margin in the React KPI component and render four top-level cards in the requested order. Keep the change isolated to read-only summary data, the KPI component, CSS, and focused tests.

**Tech Stack:** Python/FastAPI data assembly, React/TypeScript, CSS, pytest, Vite.

**Spec:** `docs/superpowers/specs/2026-10-29-cuenta-riesgo-kpi-design.md`

## Global Constraints

- Sum `marginSummary.accountValue` from core and XYZ when available.
- Free margin is total account value minus aggregated margin used.
- Preserve the official Hyperliquid PNL source and existing cost breakdown.
- Do not modify `secure_trade_routes.py`.

## Review Focus

- One account missing `accountValue` must not invalidate a valid account value from the other account.
- No valid account values must render `N/D`, not zero.
- Existing margin percentage remains based on core account equity, as currently defined.
- Four-card layout must remain readable at the existing responsive breakpoints.

### Task 1: Backend account total

**Files:** Modify `read_only_server.py`; test `tests/test_*` existing summary/API tests.

- [ ] Add a failing assertion for `summary.account_value_total` as the sum of available core/XYZ account values.
- [ ] Run the focused backend test and observe failure.
- [ ] Populate `account_value_total` from the already parsed `equity` list, preserving `None` when no values are available.
- [ ] Run focused backend tests and confirm pass.

### Task 2: Combined Account and Risk card

**Files:** Modify `react_frontend/src/components/PortfolioKpis.tsx`, `react_frontend/src/style.css`, `tests/test_visual_tweaks.py`.

- [ ] Add a failing structural test for card order and the four Account and Risk fields.
- [ ] Run it and observe failure.
- [ ] Render four cards in order: unrealized, official total, costs, Account and Risk; calculate free margin from `account_value_total - margin_used`.
- [ ] Add compact responsive styling and remove the standalone exposure/margin articles.
- [ ] Run focused tests and React build.

### Task 3: Final verification

- [ ] Run relevant structural/backend tests and `npm run build`.
- [ ] Review diff for accidental changes to trading routes.
