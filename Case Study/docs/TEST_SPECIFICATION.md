# Test Specification - Northwind Expense Reviewer

## Testing Strategy

| Layer | Framework | Coverage Target |
|-------|-----------|----------------|
| Unit | pytest | 80%+ |
| Integration | pytest + httpx | All API endpoints |
| End-to-End | Manual / Playwright | Core user flows |
| Evaluation | evaluation_harness.py | AI accuracy >85% |

---

## Unit Tests

### Policy Engine Tests (`test_policy_engine.py`)

```python
import pytest
from main import evaluate_line_item

# TC-001: Compliant lodging - Tier 1 city within cap
def test_lodging_tier1_compliant():
    item = {"vendor": "Marriott NYC", "amount": 320.00, "category": "lodging", "city": "New York"}
    result = evaluate_line_item(item, trip_context={})
    assert result["verdict"] == "compliant"
    assert result["confidence"] >= 0.85
    assert any("POL-003" in c["policy_id"] for c in result["cited_clauses"])

# TC-002: Over-limit lodging - Tier 1 city exceeds cap
def test_lodging_tier1_over_limit():
    item = {"vendor": "Grand Hotel NYC", "amount": 420.00, "category": "lodging", "city": "New York"}
    result = evaluate_line_item(item, trip_context={})
    assert result["verdict"] == "rejected"
    assert result["confidence"] >= 0.85

# TC-003: Lodging - Tier 2 city within cap
def test_lodging_tier2_compliant():
    item = {"vendor": "Hilton Chicago", "amount": 240.00, "category": "lodging", "city": "Chicago"}
    result = evaluate_line_item(item, trip_context={})
    assert result["verdict"] == "compliant"

# TC-004: Lodging - Tier 3 city within cap
def test_lodging_tier3_compliant():
    item = {"vendor": "Hampton Inn", "amount": 160.00, "category": "lodging", "city": "Des Moines"}
    result = evaluate_line_item(item, trip_context={})
    assert result["verdict"] == "compliant"

# TC-005: Business class flight - under 10 hours → rejected
def test_flight_business_class_short_haul():
    item = {"vendor": "United Airlines", "amount": 1200.00, "category": "airfare",
            "description": "Business class, NYC to Chicago, 2.5 hours"}
    result = evaluate_line_item(item, trip_context={})
    assert result["verdict"] == "rejected"

# TC-006: Business class flight - 10+ hours international → compliant
def test_flight_business_class_long_haul():
    item = {"vendor": "British Airways", "amount": 4500.00, "category": "airfare",
            "description": "Business class, NYC to London, 11 hours"}
    result = evaluate_line_item(item, trip_context={"has_vp_approval": True})
    assert result["verdict"] == "compliant"

# TC-007: First class flight → always rejected
def test_flight_first_class_rejected():
    item = {"vendor": "Delta Airlines", "amount": 8000.00, "category": "airfare",
            "description": "First class, NYC to Los Angeles"}
    result = evaluate_line_item(item, trip_context={})
    assert result["verdict"] == "rejected"
    assert any("POL-004" in c["policy_id"] for c in result["cited_clauses"])

# TC-008: Meal within solo dinner cap
def test_meal_solo_dinner_compliant():
    item = {"vendor": "Restaurant", "amount": 85.00, "category": "meals",
            "description": "Solo dinner, New York"}
    result = evaluate_line_item(item, trip_context={"city": "New York", "meal_type": "dinner"})
    assert result["verdict"] == "compliant"

# TC-009: Meal over solo dinner cap
def test_meal_solo_dinner_over_cap():
    item = {"vendor": "Fancy Restaurant", "amount": 150.00, "category": "meals",
            "description": "Solo dinner, New York"}
    result = evaluate_line_item(item, trip_context={"city": "New York", "meal_type": "dinner"})
    assert result["verdict"] in ["rejected", "flagged"]

# TC-010: Alcohol on receipt - non-reimbursable
def test_alcohol_non_reimbursable():
    item = {"vendor": "Bar & Grill", "amount": 45.00, "category": "meals",
            "description": "Dinner and cocktails"}
    result = evaluate_line_item(item, trip_context={})
    assert result["verdict"] in ["flagged", "rejected"]
    assert any("POL-011" in c["policy_id"] for c in result["cited_clauses"])
```

### Database Tests (`test_database.py`)

```python
import pytest
import sqlite3
from main import init_db, app

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)
    yield conn
    conn.close()

# TC-011: Database initializes with correct tables
def test_db_tables_created(test_db):
    cursor = test_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert {"employees", "submissions", "line_items", "audit_log"}.issubset(tables)

# TC-012: Sample employees seeded
def test_employees_seeded(test_db):
    cursor = test_db.execute("SELECT COUNT(*) FROM employees")
    count = cursor.fetchone()[0]
    assert count >= 5

# TC-013: Submission cascade deletes line items
def test_submission_cascade_delete(test_db):
    test_db.execute("INSERT INTO submissions(id, employee_id, trip_purpose, status, created_at) "
                    "VALUES ('sub_test', 'NW-00001', 'Test', 'new', '2025-01-01')")
    test_db.execute("INSERT INTO line_items(id, submission_id, verdict, confidence, created_at) "
                    "VALUES ('item_test', 'sub_test', 'compliant', 0.95, '2025-01-01')")
    test_db.commit()
    test_db.execute("DELETE FROM submissions WHERE id = 'sub_test'")
    test_db.commit()
    cursor = test_db.execute("SELECT COUNT(*) FROM line_items WHERE submission_id = 'sub_test'")
    assert cursor.fetchone()[0] == 0
```

---

## Integration Tests

### API Tests (`test_api.py`)

```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# TC-020: Health check returns ok
def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# TC-021: Employees list returns 5 employees
def test_get_employees():
    response = client.get("/api/employees")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5
    assert all("id" in e and "name" in e for e in data)

# TC-022: Create submission with valid data
def test_create_submission():
    payload = {
        "employee_id": "NW-00001",
        "trip_purpose": "Test trip",
        "trip_start_date": "2025-01-10",
        "trip_end_date": "2025-01-12"
    }
    response = client.post("/api/submissions/new", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "submission_id" in data
    assert data["status"] == "new"

# TC-023: Create submission with invalid employee
def test_create_submission_invalid_employee():
    payload = {"employee_id": "NW-99999", "trip_purpose": "Test"}
    response = client.post("/api/submissions/new", json=payload)
    assert response.status_code == 404

# TC-024: Create submission missing required field
def test_create_submission_missing_field():
    response = client.post("/api/submissions/new", json={})
    assert response.status_code in [400, 422]

# TC-025: Get non-existent submission returns 404
def test_get_submission_not_found():
    response = client.get("/api/submissions/sub_nonexistent")
    assert response.status_code == 404

# TC-026: Upload receipt to valid submission
def test_upload_receipt(monkeypatch):
    # Mock Claude API call
    async def mock_evaluate(*args, **kwargs):
        return {
            "vendor": "Test Hotel", "amount": 200.00, "currency": "USD",
            "category": "lodging", "receipt_date": "2025-01-10",
            "verdict": "compliant", "confidence": 0.95,
            "reasoning": "Within policy limits",
            "cited_clauses": [{"policy_id": "POL-003", "section": "3.2", "quoted_text": "test"}]
        }
    monkeypatch.setattr("main.evaluate_line_item", mock_evaluate)

    # Create submission first
    sub = client.post("/api/submissions/new", json={
        "employee_id": "NW-00001", "trip_purpose": "Test"
    }).json()

    # Upload receipt
    response = client.post(
        f"/api/submissions/{sub['submission_id']}/upload",
        files={"file": ("receipt.txt", b"Hotel receipt: $200", "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "line_item_id" in data
    assert data["verdict"] == "compliant"

# TC-027: Override verdict
def test_override_verdict():
    # (assumes setup with existing submission and line_item)
    override = {
        "verdict": "compliant",
        "comment": "Exception approved by manager",
        "reviewer_id": "NW-00004"
    }
    response = client.post(
        "/api/submissions/sub_test/line_items/item_test/override",
        json=override
    )
    # 404 expected since test IDs don't exist in fresh DB
    assert response.status_code in [200, 404]

# TC-028: Policy Q&A returns answer with citations
def test_policy_qa(monkeypatch):
    async def mock_answer(*args, **kwargs):
        return {
            "answer": "Business class is allowed for 10+ hour international flights.",
            "cited_clauses": [{"policy_id": "POL-004", "section": "4.3", "quoted_text": "test"}],
            "confidence": 0.92
        }
    monkeypatch.setattr("main.answer_policy_question", mock_answer)

    response = client.post("/api/policy/ask", json={"question": "Can I fly business class?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "cited_clauses" in data
```

---

## Evaluation Harness Tests

Run `evaluation_harness.py` to measure AI quality:

```bash
cd "Case Study"
python evaluation_harness.py
```

### Expected Metrics

| Metric | Minimum | Target |
|--------|---------|--------|
| Verdict Accuracy | 85% | 92% |
| Citation Faithfulness | 90% | 97% |
| Refusal Rate (out-of-scope) | 80% | 95% |
| False Confident Rate | <10% | <5% |
| Calibration Error | <0.15 | <0.10 |

---

## End-to-End Test Scenarios

### Scenario 1: Full submission flow
1. Open `http://localhost:3000`
2. Click "New Submission" → Select employee "Sarah Chen"
3. Enter trip purpose and dates → Click "Create"
4. Upload a hotel receipt → Verify verdict appears
5. Upload a meal receipt → Verify verdict appears
6. Navigate to History → Verify submission listed
7. Open detail view → Verify all line items shown

### Scenario 2: Override flow
1. Submit a receipt that returns "flagged"
2. Click "Override" on the flagged item
3. Select "Compliant" + enter comment
4. Verify override reflected in UI
5. Verify audit log updated

### Scenario 3: Policy Q&A
1. Navigate to "Policy Q&A"
2. Ask "What is the lodging cap for New York?"
3. Verify answer references POL-003
4. Verify cited text matches policy document

### Scenario 4: Out-of-scope refusal
1. Navigate to "Policy Q&A"
2. Ask "What is the capital of France?"
3. Verify system declines and explains it only answers policy questions

---

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all unit + integration tests
pytest -v

# Run only unit tests
pytest -v -k "not api"

# Run with coverage
pip install pytest-cov
pytest --cov=main --cov-report=html

# Run evaluation harness
python evaluation_harness.py
```
