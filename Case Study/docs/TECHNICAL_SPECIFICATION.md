# Technical Specification - Northwind Expense Reviewer

## 1. Executive Summary

The Northwind Expense Reviewer is an AI-powered expense pre-review system that automates the evaluation of employee expense submissions against company policies. It uses Anthropic Claude AI to extract data from receipts, evaluate compliance, and provide cited verdicts with full audit trails.

## 2. System Architecture

```
┌─────────────────────────────────────────────┐
│           React Frontend (port 3000)         │
│  HomeView | NewSubmission | History | Q&A   │
└──────────────────┬──────────────────────────┘
                   │ HTTP (proxied)
┌──────────────────▼──────────────────────────┐
│         FastAPI Backend (port 8000)          │
│                                             │
│  ┌─────────────┐   ┌─────────────────────┐  │
│  │ Policy      │   │ Receipt Extractor   │  │
│  │ Engine      │   │ (Claude Vision API) │  │
│  └──────┬──────┘   └──────────┬──────────┘  │
│         └──────────┬──────────┘             │
│  ┌────────────────▼──────────────────────┐  │
│  │       Anthropic Claude API            │  │
│  │   claude-3-5-sonnet-20241022          │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │         SQLite Database               │  │
│  │  employees | submissions | line_items │  │
│  │  audit_log                            │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## 3. Functional Requirements

| ID | Requirement | Implementation |
|----|-------------|----------------|
| FR-1 | Submission management | POST /api/submissions/new |
| FR-2 | Receipt upload & processing | POST /api/submissions/{id}/upload |
| FR-3 | Policy evaluation with verdicts | Claude AI + policy_rules_db.json |
| FR-4 | Human override with audit | POST /line_items/{id}/override |
| FR-5 | Audit & compliance log | audit_log table |
| FR-6 | Policy Q&A | POST /api/policy/ask |
| FR-7 | Data persistence | SQLite with WAL mode |

## 4. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | Performance | <5 sec/submission, <200ms API |
| NFR-2 | Availability | 99.9% uptime |
| NFR-3 | Security | API key protection, CORS, input validation |
| NFR-4 | Usability | Responsive, accessible UI |
| NFR-5 | Scalability | 10K submissions/day |

## 5. Data Models

### Submission
```json
{
  "id": "sub_abc12345",
  "employee_id": "NW-00001",
  "trip_purpose": "Client meeting in New York",
  "trip_start_date": "2025-01-10",
  "trip_end_date": "2025-01-12",
  "status": "new",
  "created_at": "2025-01-10T09:00:00"
}
```

### Line Item
```json
{
  "id": "receipt_abc12345",
  "submission_id": "sub_abc12345",
  "vendor": "Marriott NYC",
  "amount": 320.00,
  "currency": "USD",
  "category": "lodging",
  "receipt_date": "2025-01-10",
  "verdict": "compliant",
  "confidence": 0.95,
  "reasoning": "Hotel rate of $320/night is within the $350 Tier 1 city limit.",
  "cited_clauses": [
    {
      "policy_id": "POL-003",
      "section": "3.2",
      "quoted_text": "Lodging caps per night: Tier 1 cities $350"
    }
  ]
}
```

## 6. Policy Engine

### Verdict Logic
```
IF confidence >= 0.85 AND within_policy → compliant
IF confidence >= 0.85 AND violates_policy → rejected
IF confidence 0.70-0.85 → flagged (manual review)
IF confidence < 0.50 → ambiguous (clarification needed)
```

### Policy Categories
1. Meal Allowances (POL-001)
2. City Tier Classification (POL-002)
3. Lodging Limits (POL-003)
4. Air Travel (POL-004)
5. Ground Transportation (POL-005)
6. Client Entertainment (POL-006)
7. Team Meals (POL-007)
8. Approval Thresholds (POL-008)
9. Receipt Requirements (POL-009)
10. Submission Timeline (POL-010)
11. Non-Reimbursable Expenses (POL-011)
12. International Travel (POL-012)
13. Conference and Training (POL-013)

## 7. Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend Framework | FastAPI | 0.104+ |
| ASGI Server | Uvicorn | 0.24.0 |
| AI Model | Claude 3.5 Sonnet | 20241022 |
| HTTP Client | httpx | 0.27.0 |
| Database | SQLite | 3 |
| Frontend | React | 18.2.0 |
| Language | Python | 3.9+ |

## 8. Deployment Options

| Option | Cost | Time |
|--------|------|------|
| Local | $0 | 5 min |
| Docker | $0 | 10 min |
| Railway + Vercel | $20-100/month | 15 min |
| AWS ECS | $100-300/month | 30 min |

## 9. Future Enhancements

- [ ] Multi-tenant support
- [ ] Email notifications
- [ ] PDF report generation
- [ ] SSO/SAML authentication
- [ ] PostgreSQL migration
- [ ] Bulk receipt upload
- [ ] Mobile app
