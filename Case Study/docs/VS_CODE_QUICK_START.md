# VS Code Quick Start - Northwind Expense Reviewer

## Prerequisites

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Python | 3.9+ | `python --version` |
| Node.js | 16+ | `node --version` |
| npm | 8+ | `npm --version` |
| Git | any | `git --version` |

---

## Step 1: Clone / Open the Project

```bash
git clone https://github.com/harishyeluri8800/northwind-expense-reviewer.git
cd northwind-expense-reviewer
```

Or open the folder directly in VS Code:
```
File → Open Folder → select "Case Study"
```

---

## Step 2: Backend Setup

### 2a. Create virtual environment
```bash
cd "Case Study"
python -m venv venv
```

### 2b. Activate it
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2c. Install dependencies
```bash
pip install "fastapi>=0.104.1" "uvicorn==0.24.0" "pydantic>=2.5" "python-multipart==0.0.6" "httpx==0.27.0"
```

### 2d. Set your Anthropic API key
```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# macOS/Linux
export ANTHROPIC_API_KEY="sk-ant-..."
```

> Get your key at https://console.anthropic.com

### 2e. Start the backend
```bash
python -m uvicorn main:app --reload --port 8000
```

✅ Verify: open `http://localhost:8000/api/health` → should return `{"status": "ok"}`

---

## Step 3: Frontend Setup

Open a **new terminal** in VS Code (`Ctrl+Shift+\`):

```bash
cd "Case Study/frontend"
npm install
npm start
```

✅ Verify: browser opens to `http://localhost:3000`

---

## Step 4: VS Code Extensions (Recommended)

| Extension | ID | Purpose |
|-----------|-----|---------|
| Python | ms-python.python | Linting, IntelliSense |
| Pylance | ms-python.vscode-pylance | Type checking |
| ES7+ React Snippets | dsznajder.es7-react-js-snippets | React shortcuts |
| REST Client | humao.rest-client | Test API endpoints |
| SQLite Viewer | qwtel.sqlite-viewer | Browse database |

Install all at once:
```bash
code --install-extension ms-python.python ms-python.vscode-pylance dsznajder.es7-react-js-snippets humao.rest-client qwtel.sqlite-viewer
```

---

## Step 5: VS Code Workspace Configuration

Create `.vscode/settings.json` in the project root:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true,
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.python"
  },
  "[javascript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

---

## Step 6: Run Evaluation Harness

With the backend running:
```bash
cd "Case Study"
python evaluation_harness.py
```

Expected output:
```
=== Northwind Expense Reviewer Evaluation ===
Verdict accuracy:     91.3%  ✅
Citation faithfulness: 96.2% ✅
Refusal rate:         93.3%  ✅
False confident rate:  4.2%  ✅
Calibration error:    0.09   ✅
=== PASS ===
```

---

## Troubleshooting

### Backend won't start
```bash
# Check port 8000 is free
netstat -ano | findstr :8000    # Windows
lsof -i :8000                   # macOS/Linux

# Kill existing process
taskkill /PID <pid> /F          # Windows
kill -9 <pid>                   # macOS/Linux
```

### Frontend can't reach backend (CORS error)
Verify backend is running on port 8000 and `main.py` has:
```python
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], ...)
```

### `pydantic` / `fastapi` import errors
```bash
pip install --upgrade "fastapi>=0.104.1" "pydantic>=2.5"
```

### Anthropic API errors
- Verify `ANTHROPIC_API_KEY` is set in the **same terminal** as uvicorn
- Check balance at https://console.anthropic.com
- Confirm model name is `claude-3-5-sonnet-20241022`

### Database locked error
```bash
# Delete WAL files and restart
del expense_reviewer.db-shm expense_reviewer.db-wal    # Windows
rm expense_reviewer.db-shm expense_reviewer.db-wal     # macOS/Linux
```

---

## Project Structure

```
Case Study/
├── main.py                    ← FastAPI backend
├── policy_rules_db.json       ← Policy knowledge base
├── evaluation_harness.py      ← AI evaluation script
├── expense_reviewer.db        ← SQLite (auto-created, gitignored)
├── requirements.txt           ← Python dependencies
├── README.md                  ← Full documentation
├── docs/
│   ├── SPECIFICATION_INDEX.md
│   ├── QUICK_REFERENCE_SPEC.md
│   ├── TECHNICAL_SPECIFICATION.md
│   ├── API_SPECIFICATION.md
│   ├── DATABASE_SPECIFICATION.md
│   ├── TEST_SPECIFICATION.md
│   └── VS_CODE_QUICK_START.md  ← (this file)
└── frontend/
    ├── package.json
    ├── public/
    └── src/
        ├── App.jsx             ← Main React app
        ├── App.css             ← Styling
        └── index.js
```
