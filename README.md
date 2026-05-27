# Northwind Expense Reviewer

AI-powered expense pre-review system built with **FastAPI + React + SQLite + Anthropic Claude**.

## Quick Start

### 1. Set API Key
```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"

# Windows CMD
set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 2. Install & Run Backend
```bash
cd "Case Study"
pip install -r requirements.txt
python main.py
# → API running at http://localhost:8000
# → Swagger docs at http://localhost:8000/docs
```

### 3. Install & Run Frontend
```bash
cd frontend
npm install
npm start
# → UI running at http://localhost:3000
```

### 4. Run Evaluation Harness
```bash
cd "Case Study"
python evaluation_harness.py --api http://localhost:8000
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│             React Frontend (port 3000)       │
│  HomeView | NewSubmission | History | Q&A   │
└──────────────────┬──────────────────────────┘
                   │ HTTP (proxied)
┌──────────────────▼──────────────────────────┐
│          FastAPI Backend (port 8000)         │
│                                             │
│  ┌─────────────┐   ┌─────────────────────┐  │
│  │ Policy      │   │ Receipt Extractor   │  │
│  │ Engine      │   │ (Claude Vision API) │  │
│  └──────┬──────┘   └──────────┬──────────┘  │
│         │                     │             │
│  ┌──────▼─────────────────────▼──────────┐  │
│  │        Anthropic Claude API           │  │
│  │   claude-3-5-sonnet-20241022          │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │          SQLite Database              │  │
│  │  employees | submissions | line_items │  │
│  │  audit_log                            │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## Features

| Requirement | Implementation |
|---|---|
| New submission for employee | `POST /api/submissions/new` + dropdown UI |
| Upload receipts (PDF/JPG/PNG/TXT) | `POST /api/submissions/{id}/upload` + drag-drop UI |
| Pre-review verdicts with reasoning & citations | Claude evaluates against 13 policies |
| Flagged items visually distinct | Color-coded cards (🟢🟡🔴⚪) |
| Override verdicts with audit trail | Override button + `audit_log` table |
| Browse submission history with filtering | History view with employee/status filters |
| Ad-hoc policy Q&A with cited answers | Policy Q&A tab with out-of-scope refusal |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/employees` | List employees |
| POST | `/api/submissions/new` | Create submission |
| POST | `/api/submissions/{id}/upload` | Upload & evaluate receipt |
| GET | `/api/submissions/{id}` | Get submission detail |
| GET | `/api/submissions` | List submissions (with filters) |
| POST | `/api/submissions/{id}/line_items/{lid}/override` | Override verdict |
| POST | `/api/policy/ask` | Policy Q&A |

## Design Decisions

**Why SQLite?** Zero-ops persistence, ACID-compliant, survives restarts. Upgradeable to PostgreSQL with minimal changes.

**Why Claude 3.5 Sonnet?** Best accuracy-to-cost ratio for structured JSON extraction and policy reasoning tasks.

**Why FastAPI?** Auto-generated OpenAPI docs, async support, Pydantic validation.

**Confidence thresholds:** compliant/rejected require ≥0.85 confidence, flagged 0.70–0.85, ambiguous <0.50. This prevents false-confident wrong verdicts.

**Citation faithfulness:** Every verdict must cite exact policy text. This makes AI reasoning verifiable and auditable.

## Cost Analysis

| Metric | Value |
|---|---|
| Model | claude-3-5-sonnet-20241022 |
| Cost per receipt evaluation | ~$0.03–0.06 |
| Cost per 5-receipt submission | ~$0.15–0.30 |
| At 1,000 submissions/day | ~$150–300/day |

## Database Schema

```sql
employees   (id, name, grade, title, department, manager_id, home_base)
submissions (id, employee_id, trip_purpose, trip_start_date, trip_end_date, status, created_at, reviewed_at)
line_items  (id, submission_id, vendor, amount, currency, category, receipt_date,
             verdict, confidence, reasoning, cited_clauses,
             human_override_verdict, human_override_comment, human_override_at, created_at)
audit_log   (id, submission_id, line_item_id, action, user_id, details, created_at)
```
