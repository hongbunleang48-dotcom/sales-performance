# PROJECT GOAL & EXECUTION ROADMAP: PROJECT CORE
> **Title**: Project CORE (Coverage, Outlet & Route Excellence)  
> **Mission**: Build an executive sales intelligence platform with real-time route discipline tracking, multi-field filtering, automated incentive engine, and sub-second MongoDB aggregations.

---

## 🎯 Global System Constraints
- **Backend**: FastAPI, Async Motor MongoDB (`project_core` database on `localhost:27017`), Pydantic v2.
- **Frontend**: React + Vite in pure JavaScript (`.jsx`), Tailwind CSS, Shadcn UI primitives, TanStack Table v8, Recharts, TanStack Query.
- **Strict Guardrail**: NO TypeScript (`.ts/.tsx`). Use `@/` path alias for frontend imports.
- **Database Status**: MongoDB container is active and seeded with initial Pur SenChey sales reps.

---

## 📌 Phase Checklist & Current Targets

### [x] Phase 1: Business Logic Engine & Pydantic Schemas
- **Target Files**:
  - `backend/app/core/rules.py`
  - `backend/app/models/salesman.py`
  - `backend/app/services/salesman_service.py`
- **Criteria**:
  - Automatically evaluate Achievement Status and Performance Grade:
    - $\ge 100\%$ -> Achieved / Tier 1 (High)
    - $85\% \le \text{Target} < 100\%$ -> On Track / Tier 2 (Medium)
    - $< 85\%$ -> Underperforming / Tier 3 (Low)
  - Evaluate Action Status:
    - `credit_health == "Overdue Notice"` or `target < 85%` -> PIP Warning
    - `target >= 100%` and `credit_health == "Healthy"` -> Top Incentive
    - `target >= 90%` and `credit_health == "Healthy"` -> Standard Bonus
    - Otherwise -> Retraining

---

### [x] Phase 2: CRUD Endpoints & Cascading Geography
- **Target Files**:
  - `backend/app/api/v1/salesmen.py`
  - `backend/app/api/v1/territories.py`
  - `backend/app/main.py`
- **Criteria**:
  - GET `/api/v1/salesmen`: Paginated with query debouncing, multi-field search, and range filters.
  - POST `/api/v1/salesmen`: Create and map new reps to unassigned communes.
  - PATCH `/api/v1/salesmen/{salesman_id}`: Inline cell update (`route_discipline`, `merchandising_score`, etc.) with audit logging.
  - DELETE `/api/v1/salesmen/{salesman_id}`: Soft delete (toggle status between Active and Inactive).
  - Cascading endpoints: `/provinces`, `/districts?province=...`, `/communes?district=...`.

---

### [x] Phase 3: Analytics & MongoDB Aggregation Pipelines
- **Target Files**:
  - `backend/app/services/analytics_service.py`
  - `backend/app/api/v1/analytics.py`
- **Criteria**:
  - Pipeline for Executive Summary: Average Fleet Realization %, Strike Rate %, Coverage Saturation % (Compliant ratio), and Field Risk Count.
  - Pipeline for Route Fidelity Scatter: Points mapped to quadrants (X = Coverage Execution %, Y = Strike Rate %).
  - Pipeline for Supervisor Leaderboard: Ranking supervisors by Tier 1 rep ratio.
  - Pipeline for Tier Distribution: Count split for Tier 1, Tier 2, and Tier 3.

---

### [ ] Phase 4: Frontend API Client & Global State
- **Target Files**:
  - `frontend/src/api/client.js`
  - `frontend/src/api/salesmenApi.js`
  - `frontend/src/api/analyticsApi.js`
  - `frontend/src/api/territoryApi.js`
  - `frontend/src/context/FilterContext.jsx`
- **Criteria**:
  - Axios configured to `http://localhost:8000/api/v1`.
  - FilterContext holding search string, cascade geography, badge pills, and target range slider states.

---

### [ ] Phase 5: TanStack Data Table & Inline Editing
- **Target Files**:
  - `frontend/src/components/common/StatusBadge.jsx`
  - `frontend/src/components/table/InlineSelectCell.jsx`
  - `frontend/src/components/table/TableColumns.jsx`
  - `frontend/src/components/table/SalesmenTable.jsx`
  - `frontend/src/components/table/RepSheetDrawer.jsx`
- **Criteria**:
  - Visual badges matching palette: Emerald (Tier 1/Achieved/Compliant/Healthy), Amber (Tier 2/On Track/Retraining), Rose (Tier 3/PIP Warning/Diverted/Overdue).
  - Inline dropdown update for `route_discipline` with optimistic TanStack Query cache invalidation.
  - Slide-over sheet drawer displaying supervisor details and audit checklist on row click.

---

### [ ] Phase 6: Executive Dashboard & Charts
- **Target Files**:
  - `frontend/src/components/dashboard/MetricCard.jsx`
  - `frontend/src/components/dashboard/RouteScatterPlot.jsx`
  - `frontend/src/components/dashboard/SupervisorRank.jsx`
  - `frontend/src/components/dashboard/TierDonutChart.jsx`
  - `frontend/src/views/ExecutiveOverview.jsx`
  - `frontend/src/views/FieldRoster.jsx`
  - `frontend/src/App.jsx`
- **Criteria**:
  - Recharts scatter plot with quadrant reference lines ($X = 90\%$, $Y = 85\%$).
  - Metric cards showing Fleet Realization, Strike Efficiency, Coverage Saturation, and Field Risk.
  - Navigation sidebar switching between Executive Overview and Field Roster.
