# Database Specification - Northwind Expense Reviewer

## Engine
- **Database**: SQLite 3
- **Mode**: WAL (Write-Ahead Logging) for concurrent reads
- **File**: `expense_reviewer.db`
- **Encoding**: UTF-8

## Schema

### Table: employees

```sql
CREATE TABLE employees (
    id          TEXT PRIMARY KEY,        -- "NW-00001"
    name        TEXT NOT NULL,
    grade       TEXT NOT NULL,           -- "L1"-"L7", "VP", "SVP", "C-Level"
    title       TEXT NOT NULL,
    department  TEXT NOT NULL,
    manager_id  TEXT REFERENCES employees(id),
    home_base   TEXT NOT NULL
);
```

**Indexes**
```sql
CREATE INDEX idx_employees_department ON employees(department);
CREATE INDEX idx_employees_manager ON employees(manager_id);
```

**Sample data**
| id | name | grade | title | department | home_base |
|----|------|-------|-------|------------|-----------|
| NW-00001 | Sarah Chen | L5 | Senior Account Executive | Sales | San Francisco, CA |
| NW-00002 | Marcus Johnson | L4 | Field Sales Representative | Sales | Chicago, IL |
| NW-00003 | Priya Patel | L6 | Regional Sales Director | Sales | New York, NY |
| NW-00004 | David Kim | VP | VP of Sales | Sales | San Francisco, CA |
| NW-00005 | Elena Rodriguez | L3 | Sales Development Representative | Sales | Austin, TX |

---

### Table: submissions

```sql
CREATE TABLE submissions (
    id               TEXT PRIMARY KEY,   -- "sub_" + 8 random hex chars
    employee_id      TEXT NOT NULL REFERENCES employees(id),
    trip_purpose     TEXT NOT NULL,
    trip_start_date  TEXT,               -- ISO 8601 date "YYYY-MM-DD"
    trip_end_date    TEXT,               -- ISO 8601 date "YYYY-MM-DD"
    status           TEXT NOT NULL DEFAULT 'new',
    created_at       TEXT NOT NULL,      -- ISO 8601 datetime
    reviewed_at      TEXT                -- ISO 8601 datetime, null until reviewed
);
```

**Status Values**

| Status | Description |
|--------|-------------|
| new | Just created, receipts not yet uploaded |
| processing | Receipt upload in progress |
| flagged | One or more line items need review |
| approved | All line items approved (auto or manual) |
| rejected | One or more line items rejected |

**Indexes**
```sql
CREATE INDEX idx_submissions_employee ON submissions(employee_id);
CREATE INDEX idx_submissions_status ON submissions(status);
CREATE INDEX idx_submissions_created ON submissions(created_at DESC);
```

---

### Table: line_items

```sql
CREATE TABLE line_items (
    id                      TEXT PRIMARY KEY,  -- "receipt_" + 8 random hex chars
    submission_id           TEXT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    vendor                  TEXT,
    amount                  REAL,
    currency                TEXT DEFAULT 'USD',
    category                TEXT,              -- see Category Values below
    receipt_date            TEXT,
    raw_extracted_text      TEXT,              -- full text from Claude extraction
    verdict                 TEXT,              -- see Verdict Values below
    confidence              REAL,              -- 0.0 - 1.0
    reasoning               TEXT,
    cited_clauses           TEXT,              -- JSON array of {policy_id, section, quoted_text}
    human_override_verdict  TEXT,              -- null until reviewer acts
    human_override_comment  TEXT,
    human_override_at       TEXT,
    human_override_by       TEXT REFERENCES employees(id),
    created_at              TEXT NOT NULL
);
```

**Category Values**
`lodging` | `meals` | `transportation` | `airfare` | `entertainment` | `conference` | `other`

**Verdict Values**
`compliant` | `flagged` | `rejected` | `ambiguous`

**Indexes**
```sql
CREATE INDEX idx_line_items_submission ON line_items(submission_id);
CREATE INDEX idx_line_items_verdict ON line_items(verdict);
CREATE INDEX idx_line_items_category ON line_items(category);
```

---

### Table: audit_log

```sql
CREATE TABLE audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT REFERENCES submissions(id),
    line_item_id  TEXT REFERENCES line_items(id),
    action        TEXT NOT NULL,    -- see Action Values below
    user_id       TEXT,
    details       TEXT,             -- JSON object with action-specific data
    created_at    TEXT NOT NULL
);
```

**Action Values**

| Action | Trigger |
|--------|---------|
| submission_created | POST /submissions/new |
| receipt_uploaded | POST /submissions/{id}/upload |
| ai_evaluation_complete | After Claude evaluation |
| verdict_overridden | POST /line_items/{id}/override |
| submission_approved | All items compliant |
| submission_rejected | Item rejected by reviewer |

**Indexes**
```sql
CREATE INDEX idx_audit_submission ON audit_log(submission_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
```

---

## Common Queries

### Get submission with line items
```sql
SELECT s.*, e.name as employee_name
FROM submissions s
JOIN employees e ON s.employee_id = e.id
WHERE s.id = ?;

SELECT * FROM line_items WHERE submission_id = ? ORDER BY created_at;
```

### Count verdicts per submission
```sql
SELECT
    verdict,
    COUNT(*) as count
FROM line_items
WHERE submission_id = ?
GROUP BY verdict;
```

### Recent flagged submissions
```sql
SELECT s.id, e.name, s.trip_purpose, s.created_at,
       COUNT(li.id) as flagged_count
FROM submissions s
JOIN employees e ON s.employee_id = e.id
JOIN line_items li ON s.id = li.submission_id
WHERE li.verdict IN ('flagged', 'rejected')
GROUP BY s.id
ORDER BY s.created_at DESC
LIMIT 20;
```

### Audit trail for a submission
```sql
SELECT al.*, e.name as user_name
FROM audit_log al
LEFT JOIN employees e ON al.user_id = e.id
WHERE al.submission_id = ?
ORDER BY al.created_at ASC;
```

---

## Migration Notes

### To PostgreSQL (Production)
Replace:
- `TEXT PRIMARY KEY` → `VARCHAR(50) PRIMARY KEY`  
- `REAL` → `NUMERIC(10,2)`
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- SQLite WAL mode → PG default MVCC
- `expense_reviewer.db` file → Connection string env var

### Backup (SQLite)
```bash
# Live backup (safe with WAL mode)
sqlite3 expense_reviewer.db ".backup expense_reviewer_backup.db"

# Or using Python
import sqlite3
src = sqlite3.connect('expense_reviewer.db')
dst = sqlite3.connect('expense_reviewer_backup.db')
src.backup(dst)
```
