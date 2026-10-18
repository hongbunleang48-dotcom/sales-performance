# SYSTEM CONTEXT & GUIDELINES: PROJECT CORE

## 1. Project Mission & Tech Stack
- Title: Project CORE (Coverage, Outlet & Route Excellence)
- Frontend: React + Vite in pure JavaScript (.jsx). Do NOT use TypeScript (.ts/.tsx).
- UI Framework: Tailwind CSS, Shadcn UI patterns, Lucide React icons.
- State & Tables: TanStack Query (React Query) for API calls, TanStack Table v8 for data tables, Recharts for charts.
- Backend: FastAPI, Motor (Async MongoDB), Pydantic v2 schemas.
- Database: MongoDB.

## 2. Master Data Schema
- salesman_id: String (e.g., 'W001406')
- salesman_name: String
- supervisor: String
- province: String (e.g., 'Phnom Penh')
- district: String (e.g., 'Pur SenChey')
- commune: String (e.g., 'Kakab 1', 'Chaom Chau 3')
- status: Enum ('Active', 'Inactive')
- target_achieved_pct: Float
- strike_rate_pct: Float
- coverage_execution_pct: Float
- route_discipline: Enum ('Compliant', 'Route Diverted')
- mom_growth: Enum ('Positive Growth', 'Flat', 'Declining')
- in_store_merchandising_score: Enum ('Excellent', 'Good', 'Fair', 'Poor')
- credit_health: Enum ('Healthy', 'Overdue Notice')
- achievement_status: Enum ('Achieved', 'On Track', 'Underperforming')
- performance_grade: Enum ('Tier 1 (High)', 'Tier 2 (Medium)', 'Tier 3 (Low)')
- action_status: Enum ('Top Incentive', 'Standard Bonus', 'Retraining', 'PIP Warning')

## 3. Decision Engine Logic
- Achievement & Tier Logic:
  - If target_achieved_pct >= 100 -> achievement_status = 'Achieved', performance_grade = 'Tier 1 (High)'
  - If target_achieved_pct >= 85 and < 100 -> achievement_status = 'On Track', performance_grade = 'Tier 2 (Medium)'
  - If target_achieved_pct < 85 -> achievement_status = 'Underperforming', performance_grade = 'Tier 3 (Low)'
- Action Status Logic:
  - If credit_health == 'Overdue Notice' OR target_achieved_pct < 85 -> action_status = 'PIP Warning'
  - Else If target_achieved_pct >= 100 AND credit_health == 'Healthy' -> action_status = 'Top Incentive'
  - Else If target_achieved_pct >= 90 AND credit_health == 'Healthy' -> action_status = 'Standard Bonus'
  - Else -> action_status = 'Retraining'

## 4. UI Color Mapping Rules
- Emerald (#10B981): Tier 1, Achieved, Compliant, Healthy, Top Incentive
- Amber (#F59E0B): Tier 2, On Track, Standard Bonus, Retraining, Fair
- Rose (#EF4444): Tier 3, Underperforming, PIP Warning, Route Diverted, Overdue Notice, Poor

## 5. Development Guardrails
- Keep all frontend files as .js and .jsx.
- Use '@/' path alias for frontend imports.
- Use async/await and Motor async patterns for FastAPI MongoDB queries.
- Optimize table updates using TanStack Query mutations.
