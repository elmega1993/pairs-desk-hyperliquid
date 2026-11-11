# KPI Costs and Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the dashboard's redundant realized-PNL card with a compact 2×2 card showing historical funding, historical fees, and active floating PNL split by long and short legs.

**Architecture:** Keep the existing `PortfolioKpis` component as the owner of the dashboard card layout. Derive long/short aggregates from `data.pairs` in the frontend and consume the already reconciled account-level funding and fees from `data.summary`. Add focused structural tests and CSS for the compact grid without changing backend trading or accounting routes.

**Tech Stack:** React, TypeScript, existing CSS, pytest structural frontend tests, Vite build.

**Spec:** `docs/superpowers/specs/2026-10-29-kpi-costos-descomposicion-design.md`

## Global Constraints

- Keep the card in the same KPI row and do not alter the other KPI cards.
- `PNL Longs/Shorts` means active floating PNL aggregated from `long_pnl` and `short_pnl`.
- Funding uses reconciled historical `summary.account_funding`; fees use verified `summary.fees`.
- Missing or unverifiable values render as `N/D` through existing formatting conventions.
- Do not modify `secure_trade_routes.py`.

## Review Focus

- Missing `long_pnl`/`short_pnl` on one or more active pairs must not produce `NaN`; test frontend fallback behavior in `tests/test_visual_tweaks.py`.
- Missing account funding must remain visibly unavailable rather than being replaced by the current funding-rate estimate; test the exact source field.
- The 2×2 layout must remain compact on narrow screens; test the dedicated class and responsive CSS.
- Existing mini charts must remain only on unrealized and official-total cards; preserve the current structural assertions.

### Task 1: Replace realized-PNL card content

**Files:**
- Modify: `react_frontend/src/components/PortfolioKpis.tsx`
- Modify: `react_frontend/src/style.css`
- Test: `tests/test_visual_tweaks.py`

**Interfaces:**
- Consumes: `Data.pairs`, `Data.summary.account_funding`, `Data.summary.fees`.
- Produces: a KPI card labeled `COSTOS Y DESCOMPOSICIÓN` with four cells labeled `FUNDING HISTÓRICO`, `COMISIONES HISTÓRICAS`, `PNL LONGS`, and `PNL SHORTS`.

- [ ] Add a failing structural test asserting the four labels, `summary.account_funding`, active-pair long/short aggregation, and the compact-card class.
- [ ] Run the focused test and confirm it fails against the current realized-PNL card.
- [ ] Derive finite long/short totals from `data.pairs`, treating absent/non-numeric leg PNL as unavailable according to the existing `money()` behavior; render the four cells with `money()` and `tone()`.
- [ ] Replace only the realized-PNL KPI article with the new 2×2 content and add scoped CSS for the grid, preserving the existing KPI row and responsive behavior.
- [ ] Run the focused pytest test and the React build; confirm both pass.

### Task 2: Final verification

**Files:**
- Verify: `react_frontend/src/components/PortfolioKpis.tsx`
- Verify: `react_frontend/src/style.css`
- Verify: `tests/test_visual_tweaks.py`

- [ ] Run the complete relevant frontend structural tests.
- [ ] Run `npm run build` from `react_frontend`.
- [ ] Review the diff for accidental changes to other KPI cards or trading routes.
