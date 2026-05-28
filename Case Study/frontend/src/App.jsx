import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

const API = '';  // uses CRA proxy to http://localhost:8000

// ─── Helpers ────────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail?.error || data?.detail || 'Request failed');
  return data;
}

function VerdictBadge({ verdict }) {
  const labels = { compliant: '✅ Compliant', flagged: '⚠️ Flagged', rejected: '❌ Rejected', ambiguous: '❓ Ambiguous' };
  return <span className={`verdict-badge verdict-${verdict}`}>{labels[verdict] || verdict}</span>;
}

function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  const cls = pct >= 85 ? 'conf-high' : pct >= 70 ? 'conf-medium' : 'conf-low';
  return (
    <div className="confidence-bar-wrap">
      <div className="confidence-bar-bg">
        <div className="confidence-bar-fill" style={{ width: pct + '%' }} />
      </div>
      <span className={`confidence-label ${cls}`}>{pct}%</span>
    </div>
  );
}

// ─── Line Item Card ──────────────────────────────────────────────────────────

function LineItemCard({ item, submissionId, onOverride }) {
  const [showOverride, setShowOverride] = useState(false);
  const [newVerdict, setNewVerdict] = useState(item.human_override_verdict || item.verdict);
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const effectiveVerdict = item.human_override_verdict || item.verdict;

  async function handleSave() {
    if (!comment.trim()) { setErr('Comment is required'); return; }
    setSaving(true); setErr('');
    try {
      await apiFetch(`/api/submissions/${submissionId}/line_items/${item.id}/override`, {
        method: 'POST',
        body: JSON.stringify({ verdict: newVerdict, comment, reviewer_id: 'reviewer' }),
      });
      setShowOverride(false);
      onOverride();
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className={`line-item-card ${effectiveVerdict}`}>
      <div className="line-item-header">
        <span className="line-item-vendor">{item.vendor || 'Unknown Vendor'}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
          <span className="line-item-amount">${(item.amount || 0).toFixed(2)}</span>
          <VerdictBadge verdict={effectiveVerdict} />
        </div>
      </div>

      <div className="line-item-meta">
        {item.category} · {item.receipt_date} · Confidence:
        <ConfidenceBar value={item.confidence} />
      </div>

      <div className="line-item-reasoning">{item.reasoning}</div>

      {(item.cited_clauses || []).map((c, i) => (
        <div key={i} className="cited-clause">
          <span className="cited-clause-id">{c.policy_id} §{c.section}</span>
          <div className="cited-clause-text">"{c.quoted_text}"</div>
        </div>
      ))}

      <div className="override-section">
        {item.human_override_verdict ? (
          <div className="override-applied">
            <strong>Override applied:</strong> {item.human_override_verdict} — "{item.human_override_comment}"
            <div style={{ fontSize: '.75rem', marginTop: '.2rem', color: '#0c5460' }}>{item.human_override_at}</div>
          </div>
        ) : null}

        {!showOverride ? (
          <button className="btn btn-secondary btn-sm" onClick={() => setShowOverride(true)} style={{ marginTop: '.5rem' }}>
            Override Verdict
          </button>
        ) : (
          <div className="override-form">
            {err && <div className="alert alert-error">{err}</div>}
            <div className="override-row">
              <select className="form-control" value={newVerdict} onChange={e => setNewVerdict(e.target.value)} style={{ maxWidth: 180 }}>
                <option value="compliant">Compliant</option>
                <option value="flagged">Flagged</option>
                <option value="rejected">Rejected</option>
                <option value="ambiguous">Ambiguous</option>
              </select>
            </div>
            <textarea
              className="form-control"
              rows={2}
              placeholder="Reason for override (required)"
              value={comment}
              onChange={e => setComment(e.target.value)}
            />
            <div style={{ display: 'flex', gap: '.5rem' }}>
              <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save Override'}
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => { setShowOverride(false); setErr(''); }}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Home View ───────────────────────────────────────────────────────────────

function HomeView({ setView }) {
  return (
    <div>
      <div className="page-header">
        <h2>Northwind Logistics — Expense Reviewer</h2>
        <p>AI-powered expense pre-review with full audit trail</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px,1fr))', gap: '1rem' }}>
        {[
          { icon: '📝', title: 'New Submission', desc: 'Start a new expense submission for an employee trip.', action: 'new', btn: 'Create Submission' },
          { icon: '📂', title: 'Submission History', desc: 'Browse past submissions with filtering by employee, status, or date.', action: 'history', btn: 'View History' },
          { icon: '💬', title: 'Policy Q&A', desc: 'Ask ad-hoc questions about company expense policies.', action: 'qa', btn: 'Ask a Question' },
        ].map(c => (
          <div key={c.action} className="card" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '.5rem' }}>{c.icon}</div>
            <div className="card-title">{c.title}</div>
            <p style={{ fontSize: '.85rem', color: '#666', marginBottom: '1rem' }}>{c.desc}</p>
            <button className="btn btn-primary" onClick={() => setView(c.action)}>{c.btn}</button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── New Submission View ─────────────────────────────────────────────────────

function NewSubmissionView({ setView }) {
  const [employees, setEmployees] = useState([]);
  const [form, setForm] = useState({ employee_id: '', trip_purpose: '', trip_start_date: '', trip_end_date: '' });
  const [submissionId, setSubmissionId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState([]);
  const [err, setErr] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    apiFetch('/api/employees').then(setEmployees).catch(() => {});
  }, []);

  async function handleCreateSubmission(e) {
    e.preventDefault();
    if (!form.employee_id || !form.trip_purpose || !form.trip_start_date || !form.trip_end_date) {
      setErr('All fields are required'); return;
    }
    setSubmitting(true); setErr('');
    try {
      const res = await apiFetch('/api/submissions/new', { method: 'POST', body: JSON.stringify(form) });
      setSubmissionId(res.submission_id);
    } catch (e) { setErr(e.message); }
    finally { setSubmitting(false); }
  }

  async function handleFiles(files) {
    for (const file of files) {
      setUploading(true);
      const fd = new FormData();
      fd.append('file', file);
      try {
        const res = await fetch(`/api/submissions/${submissionId}/upload`, { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.detail?.error || 'Upload failed');
        setUploadResults(prev => [...prev, { file: file.name, ...data }]);
      } catch (e) {
        setUploadResults(prev => [...prev, { file: file.name, error: e.message }]);
      }
      setUploading(false);
    }
  }

  function onDrop(e) {
    e.preventDefault(); setDragOver(false);
    handleFiles([...e.dataTransfer.files]);
  }

  return (
    <div>
      <button className="back-btn" onClick={() => setView('home')}>← Back</button>
      <div className="page-header"><h2>New Expense Submission</h2></div>

      {!submissionId ? (
        <div className="card">
          <div className="card-title">Trip Details</div>
          {err && <div className="alert alert-error">{err}</div>}
          <form onSubmit={handleCreateSubmission}>
            <div className="form-group">
              <label className="form-label">Employee</label>
              <select className="form-control" value={form.employee_id} onChange={e => setForm({ ...form, employee_id: e.target.value })}>
                <option value="">— Select employee —</option>
                {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.name} ({emp.title})</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Trip Purpose</label>
              <input className="form-control" placeholder="e.g. Client visit, conference, training" value={form.trip_purpose} onChange={e => setForm({ ...form, trip_purpose: e.target.value })} />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Start Date</label>
                <input type="date" className="form-control" value={form.trip_start_date} onChange={e => setForm({ ...form, trip_start_date: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">End Date</label>
                <input type="date" className="form-control" value={form.trip_end_date} onChange={e => setForm({ ...form, trip_end_date: e.target.value })} />
              </div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create Submission'}
            </button>
          </form>
        </div>
      ) : (
        <div>
          <div className="alert alert-success">Submission <strong>{submissionId}</strong> created. Upload receipts below.</div>

          <div className="card">
            <div className="card-title">Upload Receipts</div>
            <label>
              <div
                className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                onClick={() => document.getElementById('file-input').click()}
              >
                <div className="upload-icon">📎</div>
                <div className="upload-text">
                  {uploading ? <span className="spinner" /> : 'Drag & drop receipts here or click to browse'}
                </div>
                <div style={{ fontSize: '.75rem', color: '#bbb', marginTop: '.3rem' }}>PDF, JPG, PNG, TXT supported</div>
              </div>
              <input id="file-input" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.txt" onChange={e => handleFiles([...e.target.files])} />
            </label>
          </div>

          {uploadResults.length > 0 && (
            <div className="card">
              <div className="card-title">Receipt Evaluations ({uploadResults.length})</div>
              {uploadResults.map((r, i) => (
                r.error
                    ? <div key={i} className="alert alert-error">❌ {r.file}: {r.error}</div>
                    : <LineItemCard
                        key={i}
                        item={{
                          id: r.line_item_id,
                          vendor: r.vendor,
                          amount: r.amount,
                          currency: r.currency,
                          category: r.category,
                          receipt_date: r.receipt_date,
                          verdict: r.verdict,
                          confidence: r.confidence,
                          reasoning: r.reasoning,
                          cited_clauses: r.cited_clauses || [],
                          human_override_verdict: r.human_override_verdict,
                          human_override_comment: r.human_override_comment,
                        }}
                        submissionId={submissionId}
                        onOverride={() => {}}
                      />
              ))}
              <button className="btn btn-secondary" style={{ marginTop: '.5rem' }} onClick={() => setView('history')}>
                View Full History →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── History View ────────────────────────────────────────────────────────────

function HistoryView({ setView, setDetailId }) {
  const [submissions, setSubmissions] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [filters, setFilters] = useState({ employee_id: '', status: '' });
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.employee_id) params.set('employee_id', filters.employee_id);
    if (filters.status) params.set('status', filters.status);
    apiFetch('/api/submissions?' + params.toString())
      .then(setSubmissions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { apiFetch('/api/employees').then(setEmployees).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <button className="back-btn" onClick={() => setView('home')}>← Back</button>
      <div className="page-header"><h2>Submission History</h2></div>

      <div className="filters-bar">
        <div className="form-group">
          <label className="form-label">Employee</label>
          <select className="form-control" value={filters.employee_id} onChange={e => setFilters({ ...filters, employee_id: e.target.value })}>
            <option value="">All employees</option>
            {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Status</label>
          <select className="form-control" value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}>
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="review">Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div className="empty-state"><span className="spinner" /></div>
        ) : submissions.length === 0 ? (
          <div className="empty-state">No submissions found.</div>
        ) : (
          submissions.map(s => (
            <div key={s.id} className="submission-row" onClick={() => { setDetailId(s.id); setView('detail'); }}>
              <div>
                <div className="sub-employee">{s.employee_name}</div>
                <div className="sub-purpose">{s.trip_purpose}</div>
                <div className="sub-date">{s.trip_start_date} → {s.trip_end_date}</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '.3rem' }}>
                <span className={`sub-status status-${s.status}`}>{s.status}</span>
                <span className="sub-date">{s.id}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Detail View ─────────────────────────────────────────────────────────────

function DetailView({ submissionId, setView }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch(`/api/submissions/${submissionId}`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [submissionId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="empty-state"><span className="spinner" /></div>;
  if (!data) return <div className="empty-state">Submission not found.</div>;

  const { line_items } = data;
  const submission = data;
  const employee = {
    name: data.employee_name,
    grade: data.employee_grade,
    title: data.employee_title,
    department: data.employee_department,
    home_base: data.employee_home_base,
  };

  return (
    <div>
      <button className="back-btn" onClick={() => setView('history')}>← Back to History</button>
      <div className="page-header">
        <h2>{employee?.name} — {submission.trip_purpose}</h2>
        <p>{submission.trip_start_date} → {submission.trip_end_date} · {submission.id}</p>
      </div>

      <div className="card">
        <div className="card-title">Employee Details</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px,1fr))', gap: '.5rem', fontSize: '.85rem' }}>
          <div><strong>Grade:</strong> {employee?.grade}</div>
          <div><strong>Title:</strong> {employee?.title}</div>
          <div><strong>Department:</strong> {employee?.department}</div>
          <div><strong>Home Base:</strong> {employee?.home_base}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Line Items ({line_items.length})</div>
        {line_items.length === 0
          ? <div className="empty-state">No receipts uploaded yet.</div>
          : line_items
              .sort((a, b) => {
                const order = { rejected: 0, flagged: 1, ambiguous: 2, compliant: 3 };
                return (order[a.human_override_verdict || a.verdict] || 4) - (order[b.human_override_verdict || b.verdict] || 4);
              })
              .map(item => (
                <LineItemCard key={item.id} item={item} submissionId={submissionId} onOverride={load} />
              ))
        }
      </div>
    </div>
  );
}

// ─── Policy Q&A View ─────────────────────────────────────────────────────────

function PolicyQAView({ setView }) {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  async function handleAsk(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true); setErr(''); setResult(null);
    try {
      const res = await apiFetch('/api/policy/ask', { method: 'POST', body: JSON.stringify({ question }) });
      setResult(res);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  const SAMPLE_QUESTIONS = [
    'What is the maximum lodging rate in New York?',
    'Can I fly business class on a 12-hour international flight?',
    'What receipts do I need to keep?',
    'How much can I spend on a client dinner per person?',
  ];

  return (
    <div>
      <button className="back-btn" onClick={() => setView('home')}>← Back</button>
      <div className="page-header">
        <h2>Policy Q&A</h2>
        <p>Ask questions about Northwind expense policies — get cited answers instantly.</p>
      </div>

      <div className="card">
        {err && <div className="alert alert-error">{err}</div>}
        <form onSubmit={handleAsk}>
          <div className="form-group">
            <label className="form-label">Your Question</label>
            <input
              className="form-control"
              placeholder="e.g. What is the meal per diem for Chicago?"
              value={question}
              onChange={e => setQuestion(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading || !question.trim()}>
            {loading ? 'Thinking…' : 'Ask Question'}
          </button>
        </form>

        <div style={{ marginTop: '1rem' }}>
          <div className="form-label">Sample questions:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.4rem', marginTop: '.4rem' }}>
            {SAMPLE_QUESTIONS.map(q => (
              <button key={q} className="btn btn-secondary btn-sm" onClick={() => setQuestion(q)}>{q}</button>
            ))}
          </div>
        </div>
      </div>

      {result && (
        <div className="card">
          <div className="card-title">Answer</div>
          <div className={`qa-answer ${!result.in_scope ? 'qa-out-of-scope' : ''}`}>
            {!result.in_scope && <div style={{ fontWeight: 700, marginBottom: '.5rem' }}>⚠️ Out of scope</div>}
            {result.answer}
          </div>
          {(result.cited_clauses || []).length > 0 && (
            <div style={{ marginTop: '.8rem' }}>
              <div className="form-label">Policy Citations:</div>
              {result.cited_clauses.map((c, i) => (
                <div key={i} className="cited-clause">
                  <span className="cited-clause-id">{c.policy_id} §{c.section}</span>
                  <div className="cited-clause-text">"{c.quoted_text}"</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── App Root ────────────────────────────────────────────────────────────────

export default function App() {
  const [view, setView] = useState('home');
  const [detailId, setDetailId] = useState(null);

  const navItems = [
    { id: 'home', label: '🏠 Home' },
    { id: 'new', label: '📝 New Submission' },
    { id: 'history', label: '📂 History' },
    { id: 'qa', label: '💬 Policy Q&A' },
  ];

  return (
    <div className="app">
      <nav className="navbar">
        <div className="navbar-brand">Northwind <span>Expense Reviewer</span></div>
        <div className="navbar-tabs">
          {navItems.map(n => (
            <button key={n.id} className={`nav-tab ${view === n.id ? 'active' : ''}`} onClick={() => setView(n.id)}>
              {n.label}
            </button>
          ))}
        </div>
      </nav>

      <div className="main-content">
        {view === 'home'    && <HomeView setView={setView} />}
        {view === 'new'     && <NewSubmissionView setView={setView} />}
        {view === 'history' && <HistoryView setView={setView} setDetailId={setDetailId} />}
        {view === 'detail'  && <DetailView submissionId={detailId} setView={setView} />}
        {view === 'qa'      && <PolicyQAView setView={setView} />}
      </div>
    </div>
  );
}
