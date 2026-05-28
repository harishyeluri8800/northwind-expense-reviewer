"""
Northwind Logistics - AI Expense Reviewer
FastAPI backend with SQLite persistence and Anthropic Claude integration.
"""

import os
import json
import uuid
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "expense_reviewer.db"
POLICY_DB_PATH = BASE_DIR / "policy_rules_db.json"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Northwind Expense Reviewer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            grade       TEXT NOT NULL,
            title       TEXT,
            department  TEXT,
            manager_id  TEXT REFERENCES employees(id),
            home_base   TEXT
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id               TEXT PRIMARY KEY,
            employee_id      TEXT NOT NULL REFERENCES employees(id),
            trip_purpose     TEXT,
            trip_start_date  TEXT,
            trip_end_date    TEXT,
            status           TEXT DEFAULT 'new',
            created_at       TEXT NOT NULL,
            reviewed_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS line_items (
            id                      TEXT PRIMARY KEY,
            submission_id           TEXT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            vendor                  TEXT,
            amount                  REAL,
            currency                TEXT DEFAULT 'USD',
            category                TEXT,
            receipt_date            TEXT,
            raw_extracted_text      TEXT,
            verdict                 TEXT,
            confidence              REAL,
            reasoning               TEXT,
            cited_clauses           TEXT,
            human_override_verdict  TEXT,
            human_override_comment  TEXT,
            human_override_at       TEXT,
            human_override_by       TEXT REFERENCES employees(id),
            created_at              TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id TEXT REFERENCES submissions(id),
            line_item_id  TEXT REFERENCES line_items(id),
            action        TEXT NOT NULL,
            user_id       TEXT,
            details       TEXT,
            created_at    TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department);
        CREATE INDEX IF NOT EXISTS idx_employees_manager    ON employees(manager_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_employee ON submissions(employee_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_status   ON submissions(status);
        CREATE INDEX IF NOT EXISTS idx_submissions_created  ON submissions(created_at);
        CREATE INDEX IF NOT EXISTS idx_line_items_submission ON line_items(submission_id);
        CREATE INDEX IF NOT EXISTS idx_line_items_verdict    ON line_items(verdict);
        CREATE INDEX IF NOT EXISTS idx_line_items_category   ON line_items(category);
        CREATE INDEX IF NOT EXISTS idx_audit_submission      ON audit_log(submission_id);
        CREATE INDEX IF NOT EXISTS idx_audit_action          ON audit_log(action);
        CREATE INDEX IF NOT EXISTS idx_audit_created         ON audit_log(created_at);
        """)
        cur = conn.execute("SELECT COUNT(*) FROM employees")
        if cur.fetchone()[0] == 0:
            _seed_employees(conn)
        conn.commit()


def _seed_employees(conn: sqlite3.Connection) -> None:
    employees = [
        ("NW-00001", "Sarah Chen",       "L5", "Senior Account Executive",     "Sales",   "NW-00004", "San Francisco, CA"),
        ("NW-00002", "Marcus Johnson",   "L4", "Field Sales Representative",   "Sales",   "NW-00004", "Chicago, IL"),
        ("NW-00003", "Priya Patel",      "L6", "Regional Sales Director",      "Sales",   "NW-00004", "New York, NY"),
        ("NW-00004", "David Kim",        "VP", "VP of Sales",                  "Sales",   None,       "San Francisco, CA"),
        ("NW-00005", "Elena Rodriguez",  "L3", "Sales Development Representative", "Sales", "NW-00004", "Austin, TX"),
    ]
    conn.executemany(
        "INSERT INTO employees (id,name,grade,title,department,manager_id,home_base) VALUES (?,?,?,?,?,?,?)",
        employees
    )

# ---------------------------------------------------------------------------
# Policy loader
# ---------------------------------------------------------------------------

def load_policies() -> dict:
    if POLICY_DB_PATH.exists():
        with open(POLICY_DB_PATH, "r") as f:
            return json.load(f)
    return _default_policies()


def _default_policies() -> dict:
    return {
        "policies": [
            {
                "id": "POL-001",
                "title": "Meal Allowances",
                "section": "3.1",
                "text": "Breakfast max $31 (Tier 1), $25 (Tier 2), $20 (Tier 3). Lunch max $44 (Tier 1), $35 (Tier 2), $30 (Tier 3). Dinner max $94 (Tier 1), $75 (Tier 2), $60 (Tier 3). Tier 1 cities: NYC, SF, Boston, DC, LA, Seattle."
            },
            {
                "id": "POL-002",
                "title": "Lodging Limits",
                "section": "3.2",
                "text": "Lodging caps per night: Tier 1 cities $350, Tier 2 cities $250, all others $175. Tier 1: NYC, SF, Boston, DC, LA, Seattle, London, Zurich, Tokyo, Singapore."
            },
            {
                "id": "POL-003",
                "title": "Air Travel",
                "section": "3.3",
                "text": "Economy class required for all flights. Premium economy allowed for flights 6+ hours. Business class allowed for international flights 10+ hours with VP approval. First class never permitted."
            },
            {
                "id": "POL-004",
                "title": "Ground Transportation",
                "section": "3.4",
                "text": "Taxi/rideshare reimbursable. Personal vehicle at $0.655/mile IRS rate. Rental cars require manager pre-approval. Luxury vehicles not reimbursable."
            },
            {
                "id": "POL-005",
                "title": "Client Entertainment",
                "section": "4.1",
                "text": "Client entertainment meals: lunch max $80-100/person, dinner max $150-187/person. VP approval required if cost exceeds $100/person for lunch or $150/person for dinner. Must document attendees and business purpose."
            },
            {
                "id": "POL-006",
                "title": "Approval Thresholds",
                "section": "5.1",
                "text": "Expenses up to $500 require manager approval. $500-$2000 require director approval. $2000-$5000 require VP approval. Over $5000 require SVP approval."
            },
            {
                "id": "POL-007",
                "title": "Receipt Requirements",
                "section": "6.1",
                "text": "Itemized receipts required for all expenses over $25. Credit card statements alone are not sufficient. Receipts must show vendor name, date, amount, and items purchased."
            },
        ]
    }

# ---------------------------------------------------------------------------
# Anthropic helpers
# ---------------------------------------------------------------------------

def call_claude(prompt: str, max_tokens: int = 1024) -> str:
    """Call the Anthropic Messages API directly via httpx."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


def extract_receipt_data(file_content: bytes, filename: str, content_type: str) -> dict:
    """Use Claude to extract structured data from a receipt."""
    is_image = content_type.startswith("image/") or filename.lower().endswith((".jpg", ".jpeg", ".png"))

    if is_image:
        import base64
        b64 = base64.standard_b64encode(file_content).decode("utf-8")
        media_type = content_type if content_type.startswith("image/") else "image/jpeg"
        if not ANTHROPIC_API_KEY:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 512,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": (
                        "Extract the following fields from this receipt image and return ONLY valid JSON:\n"
                        '{"vendor": "string", "amount": number, "currency": "USD", "category": '
                        '"meal|lodging|air_travel|ground_transport|other", "receipt_date": "YYYY-MM-DD", '
                        '"description": "string"}'
                    )},
                ],
            }],
        }
        try:
            resp = httpx.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            raw = resp.json()["content"][0]["text"].strip()
        except Exception as exc:
            log.warning("Image receipt extraction failed: %s", exc)
            return {"vendor": "Unknown", "amount": 0.0, "currency": "USD",
                    "category": "other", "receipt_date": datetime.utcnow().date().isoformat(),
                    "description": "Extraction failed"}
    else:
        text = file_content.decode("utf-8", errors="replace")
        prompt = (
            "Extract the following fields from this receipt text and return ONLY valid JSON:\n"
            '{"vendor": "string", "amount": number, "currency": "USD", "category": '
            '"meal|lodging|air_travel|ground_transport|other", "receipt_date": "YYYY-MM-DD", '
            f'"description": "string"}}\n\nReceipt text:\n{text}'
        )
        try:
            raw = call_claude(prompt, max_tokens=512)
        except Exception as exc:
            log.warning("Receipt extraction failed: %s", exc)
            return {"vendor": "Unknown", "amount": 0.0, "currency": "USD",
                    "category": "other", "receipt_date": datetime.utcnow().date().isoformat(),
                    "description": "Extraction failed"}

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        log.warning("JSON parse failed for receipt: %s", exc)
        return {"vendor": "Unknown", "amount": 0.0, "currency": "USD",
                "category": "other", "receipt_date": datetime.utcnow().date().isoformat(),
                "description": "Parse failed"}


def evaluate_line_item(item: dict, employee: dict, submission: dict) -> dict:
    """Use Claude to evaluate a line item against company policy."""
    policies = load_policies()
    policy_text = json.dumps(policies["policies"], indent=2)

    prompt = f"""You are a corporate expense compliance officer for Northwind Logistics.

COMPANY POLICIES:
{policy_text}

EMPLOYEE:
Name: {employee['name']}
Grade: {employee['grade']}
Title: {employee['title']}
Department: {employee['department']}
Home Base: {employee['home_base']}

SUBMISSION:
Trip Purpose: {submission.get('trip_purpose', 'N/A')}
Trip Dates: {submission.get('trip_start_date', 'N/A')} to {submission.get('trip_end_date', 'N/A')}

EXPENSE LINE ITEM:
Vendor: {item.get('vendor')}
Amount: ${item.get('amount')} {item.get('currency', 'USD')}
Category: {item.get('category')}
Date: {item.get('receipt_date')}
Description: {item.get('description', '')}

Evaluate this expense against company policy. Return ONLY valid JSON with this exact structure:
{{
  "verdict": "compliant|flagged|rejected|ambiguous",
  "confidence": 0.0-1.0,
  "reasoning": "Full explanation paragraph",
  "cited_clauses": [
    {{"policy_id": "POL-XXX", "section": "X.X", "quoted_text": "exact quoted text from policy"}}
  ]
}}

Rules:
- compliant: clearly within policy limits, confidence >= 0.85
- flagged: borderline or needs manual review, confidence 0.70-0.85
- rejected: clearly violates policy, confidence >= 0.85
- ambiguous: insufficient information, confidence < 0.50
- Always cite the specific policy clause(s) that apply."""

    try:
        raw = call_claude(prompt, max_tokens=1024)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        log.warning("Verdict evaluation failed: %s", exc)
        return {
            "verdict": "ambiguous",
            "confidence": 0.0,
            "reasoning": f"Evaluation failed: {exc}",
            "cited_clauses": [],
        }


def answer_policy_question(question: str) -> dict:
    """Answer a policy Q&A question using Claude."""
    policies = load_policies()
    policy_text = json.dumps(policies["policies"], indent=2)

    prompt = f"""You are a corporate policy advisor for Northwind Logistics. Answer questions ONLY about the company expense policies below. If a question is outside the scope of these policies, explicitly say so.

COMPANY POLICIES:
{policy_text}

QUESTION: {question}

Return ONLY valid JSON:
{{
  "answer": "string (full answer or explicit out-of-scope message)",
  "in_scope": true|false,
  "cited_clauses": [
    {{"policy_id": "POL-XXX", "section": "X.X", "quoted_text": "exact quoted text"}}
  ]
}}"""

    try:
        raw = call_claude(prompt, max_tokens=1024)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        if "confidence" not in result:
            result["confidence"] = 0.9 if result.get("in_scope") else 0.0
        return result
    except Exception as exc:
        log.warning("Policy Q&A failed: %s", exc)
        return {"answer": f"Error: {exc}", "in_scope": False, "cited_clauses": [], "confidence": 0.0}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class NewSubmissionRequest(BaseModel):
    employee_id: str
    trip_purpose: str
    trip_start_date: str
    trip_end_date: str


class OverrideRequest(BaseModel):
    verdict: str
    comment: str
    reviewer_id: Optional[str] = "reviewer"


class PolicyQuestionRequest(BaseModel):
    question: str

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/employees")
def list_employees():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM employees ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def _refresh_submission_status(conn: sqlite3.Connection, submission_id: str) -> str:
    """Recompute and persist submission status based on current line item verdicts."""
    rows = conn.execute(
        "SELECT verdict, human_override_verdict FROM line_items WHERE submission_id=?",
        (submission_id,)
    ).fetchall()
    if not rows:
        return "new"
    effective = [r["human_override_verdict"] or r["verdict"] for r in rows]
    if any(v == "rejected" for v in effective):
        status = "rejected"
    elif any(v in ("flagged", "ambiguous") for v in effective):
        status = "flagged"
    else:
        status = "approved"
    conn.execute("UPDATE submissions SET status=? WHERE id=?", (status, submission_id))
    return status


@app.post("/api/submissions/new")
def create_submission(req: NewSubmissionRequest):
    with get_db() as conn:
        emp = conn.execute("SELECT * FROM employees WHERE id=?", (req.employee_id,)).fetchone()
        if not emp:
            raise HTTPException(status_code=404, detail={"error": "EMPLOYEE_NOT_FOUND"})
        sub_id = "sub_" + uuid.uuid4().hex[:8]
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO submissions VALUES (?,?,?,?,?,?,?,?)",
            (sub_id, req.employee_id, req.trip_purpose,
             req.trip_start_date, req.trip_end_date, "new", now, None),
        )
        conn.execute(
            "INSERT INTO audit_log (submission_id,action,user_id,details,created_at) VALUES (?,?,?,?,?)",
            (sub_id, "submission_created", req.employee_id, json.dumps(req.dict()), now),
        )
        conn.commit()
    return {"submission_id": sub_id, "status": "new", "created_at": now}


@app.post("/api/submissions/{submission_id}/upload")
async def upload_receipt(
    submission_id: str,
    file: UploadFile = File(...),
):
    allowed = {"application/pdf", "image/jpeg", "image/png", "text/plain"}
    ct = file.content_type or ""
    if ct not in allowed and not file.filename.lower().endswith((".pdf", ".jpg", ".jpeg", ".png", ".txt")):
        raise HTTPException(status_code=400, detail={"error": "INVALID_FILE_TYPE"})

    with get_db() as conn:
        sub = conn.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail={"error": "SUBMISSION_NOT_FOUND"})
        emp = conn.execute("SELECT * FROM employees WHERE id=?", (sub["employee_id"],)).fetchone()

    raw_bytes = await file.read()
    raw_text = raw_bytes.decode("utf-8", errors="replace") if not ct.startswith("image/") else ""
    extracted = extract_receipt_data(raw_bytes, file.filename, ct)
    verdict_data = evaluate_line_item(extracted, dict(emp), dict(sub))

    item_id = "receipt_" + uuid.uuid4().hex[:8]
    now = datetime.utcnow().isoformat()
    cited_json = json.dumps(verdict_data.get("cited_clauses", []))

    with get_db() as conn:
        conn.execute(
            """INSERT INTO line_items
               (id,submission_id,vendor,amount,currency,category,receipt_date,
                raw_extracted_text,verdict,confidence,reasoning,cited_clauses,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item_id, submission_id,
                extracted.get("vendor"), extracted.get("amount"), extracted.get("currency", "USD"),
                extracted.get("category"), extracted.get("receipt_date"),
                raw_text,
                verdict_data.get("verdict"), verdict_data.get("confidence"),
                verdict_data.get("reasoning"),
                cited_json,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO audit_log (submission_id,line_item_id,action,details,created_at) VALUES (?,?,?,?,?)",
            (submission_id, item_id, "ai_evaluation_complete",
             json.dumps({**extracted, "verdict": verdict_data.get("verdict")}), now),
        )
        new_status = _refresh_submission_status(conn, submission_id)
        conn.commit()

    return {
        "line_item_id": item_id,
        "vendor": extracted.get("vendor"),
        "amount": extracted.get("amount"),
        "currency": extracted.get("currency", "USD"),
        "category": extracted.get("category"),
        "receipt_date": extracted.get("receipt_date"),
        "verdict": verdict_data.get("verdict"),
        "confidence": verdict_data.get("confidence"),
        "reasoning": verdict_data.get("reasoning"),
        "cited_clauses": verdict_data.get("cited_clauses", []),
        "human_override_verdict": None,
        "human_override_comment": None,
        "submission_status": new_status,
    }


@app.get("/api/submissions/{submission_id}")
def get_submission(submission_id: str):
    with get_db() as conn:
        sub = conn.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail={"error": "SUBMISSION_NOT_FOUND"})
        emp = conn.execute("SELECT * FROM employees WHERE id=?", (sub["employee_id"],)).fetchone()
        items = conn.execute(
            "SELECT * FROM line_items WHERE submission_id=? ORDER BY created_at", (submission_id,)
        ).fetchall()

    line_items = []
    for it in items:
        d = dict(it)
        d["cited_clauses"] = json.loads(d.get("cited_clauses") or "[]")
        line_items.append(d)

    sub_dict = dict(sub)
    return {
        "id": sub_dict["id"],
        "employee_id": sub_dict["employee_id"],
        "employee_name": emp["name"] if emp else None,
        "employee_grade": emp["grade"] if emp else None,
        "employee_title": emp["title"] if emp else None,
        "employee_department": emp["department"] if emp else None,
        "employee_home_base": emp["home_base"] if emp else None,
        "trip_purpose": sub_dict["trip_purpose"],
        "trip_start_date": sub_dict["trip_start_date"],
        "trip_end_date": sub_dict["trip_end_date"],
        "status": sub_dict["status"],
        "created_at": sub_dict["created_at"],
        "reviewed_at": sub_dict["reviewed_at"],
        "line_items": line_items,
    }


@app.get("/api/submissions")
def list_submissions(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = "SELECT s.*, e.name as employee_name FROM submissions s JOIN employees e ON s.employee_id=e.id WHERE 1=1"
    params = []
    if employee_id:
        query += " AND s.employee_id=?"
        params.append(employee_id)
    if status:
        query += " AND s.status=?"
        params.append(status)
    if from_date:
        query += " AND s.created_at>=?"
        params.append(from_date)
    if to_date:
        query += " AND s.created_at<=?"
        params.append(to_date)
    query += " ORDER BY s.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            counts = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN (COALESCE(human_override_verdict,verdict)) IN ('flagged','rejected','ambiguous') THEN 1 ELSE 0 END) as flagged "
                "FROM line_items WHERE submission_id=?",
                (d["id"],)
            ).fetchone()
            d["line_item_count"] = counts["total"] or 0
            d["flagged_count"] = counts["flagged"] or 0
            results.append(d)
    return results


@app.post("/api/submissions/{submission_id}/line_items/{line_item_id}/override")
def override_verdict(submission_id: str, line_item_id: str, req: OverrideRequest):
    valid_verdicts = {"compliant", "flagged", "rejected", "ambiguous"}
    if req.verdict not in valid_verdicts:
        raise HTTPException(status_code=400, detail={"error": "INVALID_VERDICT"})
    if req.verdict == "rejected" and not req.comment.strip():
        raise HTTPException(status_code=400, detail={"error": "COMMENT_REQUIRED_FOR_REJECTED"})

    with get_db() as conn:
        item = conn.execute(
            "SELECT * FROM line_items WHERE id=? AND submission_id=?",
            (line_item_id, submission_id)
        ).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail={"error": "LINE_ITEM_NOT_FOUND"})

        now = datetime.utcnow().isoformat()
        conn.execute(
            """UPDATE line_items SET
               human_override_verdict=?, human_override_comment=?, human_override_at=?, human_override_by=?
               WHERE id=?""",
            (req.verdict, req.comment, now, req.reviewer_id, line_item_id),
        )
        conn.execute(
            """INSERT INTO audit_log
               (submission_id,line_item_id,action,user_id,details,created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                submission_id, line_item_id, "verdict_overridden",
                req.reviewer_id,
                json.dumps({
                    "original_verdict": item["verdict"],
                    "new_verdict": req.verdict,
                    "comment": req.comment,
                }),
                now,
            ),
        )
        new_status = _refresh_submission_status(conn, submission_id)
        conn.commit()

    return {
        "line_item_id": line_item_id,
        "original_verdict": item["verdict"],
        "human_override_verdict": req.verdict,
        "human_override_comment": req.comment,
        "override_at": now,
        "submission_status": new_status,
    }


@app.post("/api/policy/ask")
def policy_ask(req: PolicyQuestionRequest):
    if not req.question or len(req.question.strip()) < 5:
        raise HTTPException(status_code=400, detail={"error": "MISSING_QUESTION"})
    result = answer_policy_question(req.question.strip())
    return result

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup():
    init_db()
    log.info("Database initialised at %s", DB_PATH)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
