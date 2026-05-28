# API Specification - Northwind Expense Reviewer

## Base URL
- Development: `http://localhost:8000`
- All endpoints prefixed with `/api`

## Authentication
- `ANTHROPIC_API_KEY` required as environment variable on server
- No client-side auth in MVP (add JWT for production)

---

## Endpoints

### 1. GET /api/health
**Description**: Health check

**Response 200**
```json
{ "status": "ok", "version": "1.0.0" }
```

---

### 2. GET /api/employees
**Description**: List all employees

**Response 200**
```json
[
  {
    "id": "NW-00001",
    "name": "Sarah Chen",
    "grade": "L5",
    "title": "Senior Account Executive",
    "department": "Sales",
    "manager_id": "NW-00004",
    "home_base": "San Francisco, CA"
  }
]
```

---

### 3. POST /api/submissions/new
**Description**: Create a new expense submission

**Request Body**
```json
{
  "employee_id": "NW-00001",
  "trip_purpose": "Client meeting in New York",
  "trip_start_date": "2025-01-10",
  "trip_end_date": "2025-01-12"
}
```

**Response 200**
```json
{
  "submission_id": "sub_abc12345",
  "status": "new",
  "created_at": "2025-01-10T09:00:00"
}
```

**Errors**

| Code | Message | Cause |
|------|---------|-------|
| 400 | employee_id required | Missing field |
| 404 | Employee not found | Invalid employee_id |

---

### 4. POST /api/submissions/{submission_id}/upload
**Description**: Upload a receipt file and trigger AI evaluation

**Request**: `multipart/form-data`
- Field: `file` (PDF, JPG, PNG, TXT — max 10 MB)

**Response 200**
```json
{
  "line_item_id": "receipt_abc12345",
  "vendor": "Marriott NYC",
  "amount": 320.00,
  "currency": "USD",
  "category": "lodging",
  "receipt_date": "2025-01-10",
  "verdict": "compliant",
  "confidence": 0.95,
  "reasoning": "Hotel rate of $320/night is within the $350 Tier 1 city limit for New York.",
  "cited_clauses": [
    {
      "policy_id": "POL-003",
      "section": "3.2",
      "quoted_text": "Lodging caps per night: Tier 1 cities $350"
    }
  ],
  "human_override_verdict": null,
  "human_override_comment": null
}
```

**Errors**

| Code | Message | Cause |
|------|---------|-------|
| 404 | Submission not found | Invalid submission_id |
| 413 | File too large | >10 MB |
| 415 | Unsupported file type | Not PDF/JPG/PNG/TXT |
| 422 | Unable to extract receipt data | Claude cannot parse file |
| 500 | AI evaluation failed | Anthropic API error |

---

### 5. GET /api/submissions/{submission_id}
**Description**: Get a submission with all line items

**Response 200**
```json
{
  "id": "sub_abc12345",
  "employee_id": "NW-00001",
  "employee_name": "Sarah Chen",
  "trip_purpose": "Client meeting in New York",
  "trip_start_date": "2025-01-10",
  "trip_end_date": "2025-01-12",
  "status": "flagged",
  "created_at": "2025-01-10T09:00:00",
  "reviewed_at": null,
  "line_items": [
    {
      "id": "receipt_abc12345",
      "vendor": "Marriott NYC",
      "amount": 320.00,
      "category": "lodging",
      "verdict": "compliant",
      "confidence": 0.95,
      "reasoning": "...",
      "cited_clauses": [...],
      "human_override_verdict": null,
      "human_override_comment": null
    }
  ]
}
```

**Errors**

| Code | Message |
|------|---------|
| 404 | Submission not found |

---

### 6. GET /api/submissions
**Description**: List all submissions with optional filters

**Query Parameters**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| status | string | all | Filter by status: new, flagged, approved, rejected |
| employee_id | string | all | Filter by employee |
| limit | int | 50 | Max results |
| offset | int | 0 | Pagination offset |

**Response 200**
```json
[
  {
    "id": "sub_abc12345",
    "employee_id": "NW-00001",
    "employee_name": "Sarah Chen",
    "trip_purpose": "Client meeting in New York",
    "trip_start_date": "2025-01-10",
    "trip_end_date": "2025-01-12",
    "status": "flagged",
    "created_at": "2025-01-10T09:00:00",
    "line_item_count": 3,
    "flagged_count": 1
  }
]
```

---

### 7. POST /api/submissions/{submission_id}/line_items/{line_item_id}/override
**Description**: Human reviewer overrides AI verdict

**Request Body**
```json
{
  "verdict": "compliant",
  "comment": "Manager approved exception for this client dinner.",
  "reviewer_id": "NW-00004"
}
```

**Verdict Values**: `compliant` | `flagged` | `rejected`

**Response 200**
```json
{
  "line_item_id": "receipt_abc12345",
  "original_verdict": "flagged",
  "human_override_verdict": "compliant",
  "human_override_comment": "Manager approved exception for this client dinner.",
  "override_at": "2025-01-10T14:30:00"
}
```

**Errors**

| Code | Message |
|------|---------|
| 404 | Submission or line item not found |
| 400 | Invalid verdict value |
| 400 | Comment required for rejected verdict |

---

### 8. POST /api/policy/ask
**Description**: Ask a natural language question about company policy

**Request Body**
```json
{
  "question": "Can I fly business class to London?",
  "context": "10-hour overnight flight"
}
```

**Response 200**
```json
{
  "answer": "Yes, business class is permitted for international flights of 10 or more hours with manager VP-level approval.",
  "cited_clauses": [
    {
      "policy_id": "POL-004",
      "section": "4.3",
      "quoted_text": "Business class permitted for international flights 10+ hours with VP approval"
    }
  ],
  "confidence": 0.92
}
```

**Errors**

| Code | Message |
|------|---------|
| 400 | Question required |
| 500 | Policy lookup failed |

---

## Error Response Format

All errors follow this format:
```json
{
  "detail": "Human-readable error message"
}
```

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| /api/submissions/*/upload | 10 req/min |
| /api/policy/ask | 30 req/min |
| All others | 100 req/min |
