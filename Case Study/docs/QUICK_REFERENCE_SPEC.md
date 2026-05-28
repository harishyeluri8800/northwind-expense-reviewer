# Quick Reference Specification - Northwind Expense Reviewer

## System Overview
- **What**: AI-powered expense pre-review system for Northwind Logistics
- **Why**: Reduce review time by 50%, ensure 100% policy compliance, maintain audit trail
- **Who**: Finance teams, expense reviewers
- **How**: Upload receipts → AI evaluation → Human override → Audit log

## Key Numbers

| Metric | Value |
|--------|-------|
| Technologies | Python FastAPI + React + SQLite |
| Employees | 5 sample (scalable to 1000+) |
| Policies | 13 company policies with 100+ rules |
| Supported Formats | PDF, JPG, PNG, TXT |
| Verdict Types | compliant, flagged, rejected, ambiguous |
| Response Time | <5 sec per submission |
| Throughput | 10,000 submissions/day |
| Confidence Scale | 0-1 (0-100%) |

## API Endpoints (8 total)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Health check |
| GET | /api/employees | List employees |
| POST | /api/submissions/new | Create submission |
| POST | /api/submissions/{id}/upload | Upload receipt |
| GET | /api/submissions/{id} | Get submission |
| GET | /api/submissions | List submissions |
| POST | /api/submissions/{id}/line_items/{id}/override | Override verdict |
| POST | /api/policy/ask | Policy Q&A |

## Data Models (4 tables)

### employees
`id` | `name` | `grade` | `title` | `department` | `manager_id` | `home_base`

### submissions
`id` | `employee_id` | `trip_purpose` | `trip_start_date` | `trip_end_date` | `status` | `created_at` | `reviewed_at`

### line_items
`id` | `submission_id` | `vendor` | `amount` | `category` | `verdict` | `confidence` | `reasoning` | `cited_clauses` | `human_override_verdict` | `human_override_comment`

### audit_log
`id` | `submission_id` | `line_item_id` | `action` | `user_id` | `details` | `created_at`

## Verdicts

| Verdict | Color | Action | Confidence |
|---------|-------|--------|------------|
| compliant | 🟢 Green | Auto-approve | 0.85+ |
| flagged | 🟡 Yellow | Manual review | 0.70-0.85 |
| rejected | 🔴 Red | Reject + comment | 0.85+ |
| ambiguous | ⚪ Gray | Request clarification | <0.50 |

## Policy Tiers

### Lodging (per night)
| Tier | Cap | Cities |
|------|-----|--------|
| 1 | $350 | NYC, SF, Boston, DC, LA, Seattle, London, Zurich, Tokyo, Singapore |
| 2 | $250 | Chicago, Denver, Austin, Dallas, Miami, Phoenix, Atlanta |
| 3 | $175 | All others |

### Meals (solo)
| Meal | Tier 1 | Tier 2 | Tier 3 |
|------|--------|--------|--------|
| Breakfast | $31 | $25 | $20 |
| Lunch | $44 | $35 | $30 |
| Dinner | $94 | $75 | $60 |

### Flights
- Economy: Default ✅
- Premium Economy: 6+ hours ✅
- Business: International 10+ hours + VP approval ✅
- First Class: ❌ NEVER

## Technology Stack

### Backend
- FastAPI + Uvicorn
- Python 3.9+
- SQLite 3
- httpx (Anthropic API calls)

### Frontend
- React 18
- Node.js 16+
- Fetch API

## Cost Analysis

| Item | Cost |
|------|------|
| Per receipt evaluation | ~$0.03-0.06 |
| Per 5-receipt submission | ~$0.15-0.30 |
| At 1,000 submissions/day | ~$150-300/day |
