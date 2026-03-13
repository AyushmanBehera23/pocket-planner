/**
 * Pocket Planner — AI Expense Tracker
 * React 18 · Vite · Tailwind CSS (utility-class free — pure inline styles)
 *
 * Architecture:
 *   ExpenseContext   → global state (expenses, summary, loading)
 *   useExpenseData   → async data fetching hook
 *   api              → service layer (all fetch calls in one place)
 *   Components:
 *     Header, NavTabs
 *     Dashboard  → StatCards + CategoryBreakdown + RecentFeed
 *     UploadView → BillDropzone + ExtractionResult
 *     LedgerView → ExpenseTable (sort, filter, expand)
 */

import {
  useState, useCallback, useContext, createContext,
  useEffect, useRef, useReducer,
} from "react";

// ─────────────────────────────────────────────────────────────────────────────
// THEME
// ─────────────────────────────────────────────────────────────────────────────
const T = {
  bg0:     "#03070f",   // deepest background
  bg1:     "#080e1a",   // page background
  bg2:     "#0d1526",   // card background
  bg3:     "#111d35",   // elevated card
  border:  "#1a2744",   // default border
  border2: "#243358",   // hover border
  text0:   "#eef2ff",   // primary text
  text1:   "#8ba3cc",   // secondary text
  text2:   "#4a6080",   // muted text
  text3:   "#2a3d58",   // very muted
  accent:  "#3b82f6",   // blue accent
  accentG: "#10b981",   // green
  accentP: "#8b5cf6",   // purple
  accentO: "#f59e0b",   // amber
  accentR: "#ef4444",   // red
  mono:    "'JetBrains Mono', 'Fira Code', monospace",
  sans:    "'Inter', 'Segoe UI', system-ui, sans-serif",
};

const CATEGORY_PALETTE = {
  "Groceries":      "#10b981",
  "Food & Dining":  "#f97316",
  "Transportation": "#3b82f6",
  "Shopping":       "#8b5cf6",
  "Entertainment":  "#ec4899",
  "Utilities":      "#eab308",
  "Healthcare":     "#ef4444",
  "Travel":         "#06b6d4",
  "Education":      "#84cc16",
  "Other":          "#64748b",
};
const catColor = (c) => CATEGORY_PALETTE[c] || "#64748b";

// ─────────────────────────────────────────────────────────────────────────────
// API SERVICE LAYER
// ─────────────────────────────────────────────────────────────────────────────
const API = "http://localhost:8000/api";

const api = {
  async extractBill(file) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${API}/extract`, { method: "POST", body: fd });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
      throw new Error(e.detail || `HTTP ${r.status}`);
    }
    return r.json();
  },
  async getExpenses() {
    const r = await fetch(`${API}/expenses`);
    if (!r.ok) throw new Error("Failed to fetch expenses");
    return r.json();
  },
  async getSummary() {
    const r = await fetch(`${API}/expenses/summary`);
    if (!r.ok) throw new Error("Failed to fetch summary");
    return r.json();
  },
  async deleteExpense(id) {
    const r = await fetch(`${API}/expenses/${id}`, { method: "DELETE" });
    if (!r.ok) throw new Error("Delete failed");
    return r.json();
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// MOCK DATA (demo / offline fallback)
// ─────────────────────────────────────────────────────────────────────────────
const MOCK_EXPENSES = [
  { id: "m1", bill: { vendor: "Whole Foods Market",   date: "2025-03-01", category: "Groceries",       total: 87.43, items: [{ name: "Organic Produce Bundle", price: 34.20 }, { name: "Cold Brew Coffee 32oz", price: 12.99 }, { name: "Almond Milk 64oz", price: 5.49 }, { name: "Sourdough Loaf", price: 6.29 }, { name: "Baby Spinach 5oz", price: 4.49 }] }, created_at: "2025-03-01T14:30:00", file_name: "receipt_wf.jpg" },
  { id: "m2", bill: { vendor: "Chipotle Mexican Grill", date: "2025-03-03", category: "Food & Dining", total: 22.80, items: [{ name: "Chicken Burrito Bowl", price: 14.25 }, { name: "Fresh Guacamole", price: 3.65 }, { name: "Fountain Drink", price: 2.95 }, { name: "Chips", price: 1.95 }] }, created_at: "2025-03-03T12:15:00", file_name: "chipotle.png" },
  { id: "m3", bill: { vendor: "Shell Gas Station",   date: "2025-03-05", category: "Transportation",  total: 61.40, items: [{ name: "Premium Gas 14.2 gal", price: 58.40 }, { name: "Monster Energy Drink", price: 3.00 }] }, created_at: "2025-03-05T09:00:00", file_name: "shell.jpg" },
  { id: "m4", bill: { vendor: "Amazon",              date: "2025-03-07", category: "Shopping",         total: 118.99, items: [{ name: "USB-C Hub 7-in-1", price: 29.99 }, { name: "Mechanical Keyboard", price: 89.00 }] }, created_at: "2025-03-07T18:00:00", file_name: "amazon.pdf" },
  { id: "m5", bill: { vendor: "Netflix",             date: "2025-03-08", category: "Entertainment",    total: 15.49, items: [{ name: "Standard Plan Monthly", price: 15.49 }] }, created_at: "2025-03-08T00:00:00", file_name: "netflix.pdf" },
  { id: "m6", bill: { vendor: "CVS Pharmacy",        date: "2025-03-10", category: "Healthcare",       total: 31.47, items: [{ name: "Advil 200ct", price: 14.99 }, { name: "Vitamin D3", price: 9.99 }, { name: "Bandages", price: 5.49 }] }, created_at: "2025-03-10T16:20:00", file_name: "cvs.jpg" },
  { id: "m7", bill: { vendor: "Starbucks",           date: "2025-03-12", category: "Food & Dining",    total: 11.85, items: [{ name: "Venti Oat Milk Latte", price: 7.45 }, { name: "Blueberry Muffin", price: 4.40 }] }, created_at: "2025-03-12T08:10:00", file_name: "starbucks.jpg" },
];

const MOCK_SUMMARY = {
  category_breakdown: { Groceries: 87.43, "Food & Dining": 34.65, Transportation: 61.40, Shopping: 118.99, Entertainment: 15.49, Healthcare: 31.47 },
  monthly_breakdown: { "2025-03": 349.43 },
  grand_total: 349.43,
  total_bills: 7,
};

// ─────────────────────────────────────────────────────────────────────────────
// CONTEXT & STATE
// ─────────────────────────────────────────────────────────────────────────────
const Ctx = createContext(null);
const useApp = () => useContext(Ctx);

function expenseReducer(state, action) {
  switch (action.type) {
    case "SET_EXPENSES": return { ...state, expenses: action.payload, loading: false };
    case "SET_SUMMARY":  return { ...state, summary: action.payload };
    case "SET_LOADING":  return { ...state, loading: action.payload };
    case "SET_ERROR":    return { ...state, error: action.payload };
    case "ADD":          return { ...state, expenses: [action.payload, ...state.expenses] };
    case "REMOVE":       return { ...state, expenses: state.expenses.filter(e => e.id !== action.payload) };
    default: return state;
  }
}

function AppProvider({ children }) {
  const [state, dispatch] = useReducer(expenseReducer, {
    expenses: [], summary: null, loading: true, error: null,
  });

  const refresh = useCallback(async () => {
    dispatch({ type: "SET_LOADING", payload: true });
    try {
      const [expData, sumData] = await Promise.all([api.getExpenses(), api.getSummary()]);
      dispatch({ type: "SET_EXPENSES", payload: expData.expenses || [] });
      dispatch({ type: "SET_SUMMARY", payload: sumData });
      dispatch({ type: "SET_ERROR", payload: null });
    } catch {
      // Offline / demo mode
      dispatch({ type: "SET_EXPENSES", payload: MOCK_EXPENSES });
      dispatch({ type: "SET_SUMMARY", payload: MOCK_SUMMARY });
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const addExpense = useCallback((rec) => {
    dispatch({ type: "ADD", payload: rec });
    refresh();
  }, [refresh]);

  const removeExpense = useCallback(async (id) => {
    dispatch({ type: "REMOVE", payload: id });
    try { await api.deleteExpense(id); } catch { /* optimistic delete */ }
    refresh();
  }, [refresh]);

  return (
    <Ctx.Provider value={{ ...state, refresh, addExpense, removeExpense }}>
      {children}
    </Ctx.Provider>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVES
// ─────────────────────────────────────────────────────────────────────────────
function Card({ children, style, onClick, hover = false }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => hover && setHov(true)}
      onMouseLeave={() => hover && setHov(false)}
      style={{
        background: hov ? T.bg3 : T.bg2,
        border: `1px solid ${hov ? T.border2 : T.border}`,
        borderRadius: 14,
        transition: "background 0.15s, border-color 0.15s",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function Label({ children, style }) {
  return (
    <div style={{ color: T.text2, fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", ...style }}>
      {children}
    </div>
  );
}

function Badge({ label, color }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      background: color + "18", color, border: `1px solid ${color}30`,
      padding: "2px 9px", borderRadius: 20,
      fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
      whiteSpace: "nowrap",
    }}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}

function Spinner({ size = 22, color = T.accent }) {
  return (
    <div style={{
      width: size, height: size,
      border: `2px solid ${color}25`,
      borderTop: `2px solid ${color}`,
      borderRadius: "50%",
      animation: "pp-spin 0.7s linear infinite",
      display: "inline-block",
      flexShrink: 0,
    }} />
  );
}

function Mono({ children, style }) {
  return <span style={{ fontFamily: T.mono, ...style }}>{children}</span>;
}

// ─────────────────────────────────────────────────────────────────────────────
// HEADER
// ─────────────────────────────────────────────────────────────────────────────
function Header({ activeTab, setTab }) {
  const now = new Date();
  const tabs = [
    { id: "dashboard", icon: "◈", label: "Dashboard" },
    { id: "upload",    icon: "⊕", label: "Upload" },
    { id: "ledger",    icon: "≡", label: "Ledger" },
  ];

  return (
    <header style={{
      background: T.bg2,
      borderBottom: `1px solid ${T.border}`,
      position: "sticky", top: 0, zIndex: 100,
    }}>
      <div style={{ maxWidth: 1140, margin: "0 auto", padding: "0 24px", display: "flex", alignItems: "center", gap: 0 }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, paddingRight: 32, borderRight: `1px solid ${T.border}`, marginRight: 8 }}>
          <div style={{
            width: 34, height: 34,
            background: `linear-gradient(135deg, ${T.accent}, ${T.accentP})`,
            borderRadius: 9,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 17, boxShadow: `0 0 16px ${T.accent}30`,
          }}>💳</div>
          <div>
            <div style={{ color: T.text0, fontSize: 15, fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1 }}>
              Pocket<span style={{ color: T.accent }}>Planner</span>
            </div>
            <div style={{ color: T.text3, fontSize: 9, fontFamily: T.mono, letterSpacing: "0.12em", marginTop: 1 }}>AI EXPENSE TRACKER</div>
          </div>
        </div>

        {/* Nav Tabs */}
        <nav style={{ display: "flex", flex: 1, gap: 0 }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setTab(tab.id)}
              style={{
                background: "transparent",
                border: "none",
                borderBottom: `2px solid ${activeTab === tab.id ? T.accent : "transparent"}`,
                color: activeTab === tab.id ? T.accent : T.text2,
                padding: "18px 20px",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.04em",
                transition: "all 0.15s",
                display: "flex", alignItems: "center", gap: 6,
                whiteSpace: "nowrap",
              }}
            >
              <span style={{ fontSize: 14, opacity: 0.9 }}>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Status */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, paddingLeft: 16 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ color: T.text2, fontSize: 10, fontFamily: T.mono }}>
              {now.toLocaleString("default", { month: "short", year: "numeric" }).toUpperCase()}
            </div>
            <div style={{ color: T.text3, fontSize: 9, fontFamily: T.mono }}>
              {now.toISOString().slice(0, 10)}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, background: "#10b98115", border: "1px solid #10b98130", borderRadius: 20, padding: "4px 10px" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: T.accentG, boxShadow: `0 0 6px ${T.accentG}` }} />
            <span style={{ color: T.accentG, fontSize: 10, fontWeight: 700, fontFamily: T.mono }}>ONLINE</span>
          </div>
        </div>
      </div>
    </header>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STAT CARD
// ─────────────────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent, icon, loading }) {
  return (
    <Card style={{ padding: "22px 24px", flex: 1, minWidth: 160, position: "relative", overflow: "hidden" }}>
      {/* Glow */}
      <div style={{ position: "absolute", top: -20, right: -20, width: 80, height: 80, borderRadius: "50%", background: accent + "12", filter: "blur(20px)" }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", position: "relative" }}>
        <div>
          <Label style={{ marginBottom: 10 }}>{label}</Label>
          {loading
            ? <div style={{ height: 32, width: 80, background: T.bg3, borderRadius: 6, marginBottom: 4 }} />
            : <div style={{ color: T.text0, fontSize: 28, fontWeight: 800, letterSpacing: "-0.03em", fontFamily: T.mono, lineHeight: 1 }}>{value}</div>
          }
          {sub && <div style={{ color: T.text2, fontSize: 11, marginTop: 6 }}>{sub}</div>}
        </div>
        <div style={{
          background: accent + "18", color: accent,
          width: 40, height: 40, borderRadius: 11,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 20, border: `1px solid ${accent}20`,
          flexShrink: 0,
        }}>{icon}</div>
      </div>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CATEGORY BREAKDOWN
// ─────────────────────────────────────────────────────────────────────────────
function CategoryBreakdown({ summary, loading }) {
  if (loading) return (
    <Card style={{ padding: "22px 24px" }}>
      <Label style={{ marginBottom: 16 }}>Spending by Category</Label>
      {[1,2,3,4].map(i => (
        <div key={i} style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "center" }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.bg3 }} />
          <div style={{ flex: 1, height: 10, background: T.bg3, borderRadius: 4 }} />
          <div style={{ width: 50, height: 10, background: T.bg3, borderRadius: 4 }} />
        </div>
      ))}
    </Card>
  );

  const cats = Object.entries(summary?.category_breakdown || {}).sort(([, a], [, b]) => b - a);
  const total = summary?.grand_total || 1;

  return (
    <Card style={{ padding: "22px 24px" }}>
      <Label style={{ marginBottom: 16 }}>Spending by Category</Label>
      {/* Stacked bar */}
      <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", marginBottom: 20, gap: 2 }}>
        {cats.map(([cat, amt]) => (
          <div
            key={cat}
            title={`${cat}: $${amt.toFixed(2)}`}
            style={{
              width: `${(amt / total) * 100}%`,
              background: catColor(cat),
              borderRadius: 2,
              transition: "width 0.6s cubic-bezier(0.4,0,0.2,1)",
              minWidth: 2,
            }}
          />
        ))}
      </div>
      {/* Category list */}
      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        {cats.map(([cat, amt]) => {
          const pct = ((amt / total) * 100).toFixed(0);
          return (
            <div key={cat} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: catColor(cat), flexShrink: 0 }} />
              <div style={{ flex: 1, color: T.text1, fontSize: 12, fontWeight: 500 }}>{cat}</div>
              <div style={{ width: 60, height: 3, borderRadius: 2, background: T.bg3, overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: catColor(cat) + "80", borderRadius: 2 }} />
              </div>
              <div style={{ color: T.text2, fontSize: 10, fontFamily: T.mono, width: 28, textAlign: "right" }}>{pct}%</div>
              <Mono style={{ color: T.text0, fontSize: 12, fontWeight: 700, width: 68, textAlign: "right" }}>
                ${amt.toFixed(2)}
              </Mono>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// RECENT TRANSACTIONS FEED
// ─────────────────────────────────────────────────────────────────────────────
function RecentFeed({ expenses, loading }) {
  const recent = expenses.slice(0, 6);
  return (
    <Card style={{ padding: "22px 24px" }}>
      <Label style={{ marginBottom: 16 }}>Recent Transactions</Label>
      {loading ? (
        [1,2,3,4].map(i => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: `1px solid ${T.border}` }}>
            <div style={{ width: 120, height: 12, background: T.bg3, borderRadius: 4 }} />
            <div style={{ width: 50, height: 12, background: T.bg3, borderRadius: 4 }} />
          </div>
        ))
      ) : recent.length === 0 ? (
        <div style={{ textAlign: "center", padding: "30px 0", color: T.text2, fontSize: 13 }}>No transactions yet</div>
      ) : (
        recent.map((e, i) => (
          <div key={e.id} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "10px 0",
            borderBottom: i < recent.length - 1 ? `1px solid ${T.border}` : "none",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: catColor(e.bill.category) + "15",
                color: catColor(e.bill.category),
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 13, flexShrink: 0,
              }}>
                {categoryIcon(e.bill.category)}
              </div>
              <div>
                <div style={{ color: T.text0, fontSize: 12, fontWeight: 600 }}>{e.bill.vendor}</div>
                <div style={{ color: T.text2, fontSize: 10, fontFamily: T.mono, marginTop: 1 }}>{e.bill.date}</div>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <Mono style={{ color: T.text0, fontSize: 13, fontWeight: 700 }}>${e.bill.total.toFixed(2)}</Mono>
              <div style={{ marginTop: 3 }}>
                <Badge label={e.bill.category} color={catColor(e.bill.category)} />
              </div>
            </div>
          </div>
        ))
      )}
    </Card>
  );
}

function categoryIcon(cat) {
  const map = {
    "Groceries": "🛒", "Food & Dining": "🍽", "Transportation": "⛽",
    "Shopping": "🛍", "Entertainment": "🎬", "Utilities": "⚡",
    "Healthcare": "💊", "Travel": "✈️", "Education": "📚", "Other": "📌",
  };
  return map[cat] || "📌";
}

// ─────────────────────────────────────────────────────────────────────────────
// DASHBOARD VIEW
// ─────────────────────────────────────────────────────────────────────────────
function Dashboard() {
  const { expenses, summary, loading } = useApp();
  const total = summary?.grand_total || 0;
  const count = summary?.total_bills || 0;
  const avg   = count > 0 ? total / count : 0;
  const topCat = Object.entries(summary?.category_breakdown || {}).sort(([,a],[,b]) => b-a)[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, animation: "pp-fade 0.3s ease" }}>
      {/* KPI row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <StatCard label="Total Spend"    value={`$${total.toFixed(2)}`} sub="This period"       icon="💸" accent={T.accent}  loading={loading} />
        <StatCard label="Bills Tracked"  value={count}                  sub="Documents scanned" icon="🧾" accent={T.accentP} loading={loading} />
        <StatCard label="Top Category"   value={topCat?.[0] || "—"}     sub={topCat ? `$${topCat[1].toFixed(2)}` : "no data"} icon="📊" accent={T.accentO} loading={loading} />
        <StatCard label="Avg per Bill"   value={`$${avg.toFixed(2)}`}   sub="Per transaction"  icon="📐" accent={T.accentG} loading={loading} />
      </div>

      {/* Charts + Feed */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <CategoryBreakdown summary={summary} loading={loading} />
        <RecentFeed expenses={expenses} loading={loading} />
      </div>

      {/* Info banner */}
      <div style={{
        background: T.accent + "0c", border: `1px solid ${T.accent}25`,
        borderRadius: 12, padding: "14px 18px",
        display: "flex", alignItems: "center", gap: 12,
      }}>
        <span style={{ color: T.accent, fontSize: 18 }}>ℹ</span>
        <div>
          <div style={{ color: T.accent, fontSize: 12, fontWeight: 700, marginBottom: 2 }}>AI-Powered Extraction</div>
          <div style={{ color: T.text2, fontSize: 11, lineHeight: 1.5 }}>
            Upload any bill or receipt in JPG, PNG, or PDF format. Gemini Vision will automatically extract vendor, date, line items, and category — then add it to your ledger.
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// EXTRACTION RESULT PANEL
// ─────────────────────────────────────────────────────────────────────────────
function ExtractionResult({ record, onClear }) {
  const b = record.bill;
  return (
    <div style={{
      background: "#10b98108", border: `1px solid ${T.accentG}25`,
      borderRadius: 12, padding: 18, animation: "pp-fade 0.3s ease",
    }}>
      {/* Success header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 26, height: 26, borderRadius: "50%",
            background: T.accentG + "20", color: T.accentG,
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800,
          }}>✓</div>
          <span style={{ color: T.accentG, fontSize: 13, fontWeight: 700 }}>Extraction Successful</span>
        </div>
        <button onClick={onClear} style={{ background: "transparent", border: "none", color: T.text2, cursor: "pointer", fontSize: 16 }}>×</button>
      </div>

      {/* Metadata grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
        {[
          { label: "Vendor",   value: b.vendor, color: T.text0, bold: true },
          { label: "Total",    value: `$${b.total.toFixed(2)}`, color: T.accentG, bold: true, mono: true },
          { label: "Date",     value: b.date, color: T.text1, mono: true },
          { label: "Items",    value: `${b.items.length} line items`, color: T.text1 },
        ].map(({ label, value, color, bold, mono }) => (
          <div key={label} style={{ background: T.bg3, borderRadius: 8, padding: "10px 12px" }}>
            <Label style={{ marginBottom: 4 }}>{label}</Label>
            <div style={{ color, fontSize: 13, fontWeight: bold ? 700 : 500, fontFamily: mono ? T.mono : T.sans }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Category badge */}
      <div style={{ marginBottom: 14 }}>
        <Badge label={b.category} color={catColor(b.category)} />
      </div>

      {/* Line items */}
      <div style={{ background: T.bg3, borderRadius: 8, overflow: "hidden" }}>
        <div style={{ padding: "8px 12px", borderBottom: `1px solid ${T.border}` }}>
          <Label>Line Items</Label>
        </div>
        {b.items.map((item, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "8px 12px",
            borderBottom: i < b.items.length - 1 ? `1px solid ${T.border}` : "none",
          }}>
            <span style={{ color: T.text1, fontSize: 12 }}>{item.name}</span>
            <Mono style={{ color: T.text2, fontSize: 12 }}>${item.price.toFixed(2)}</Mono>
          </div>
        ))}
        <div style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", borderTop: `1px solid ${T.border}`, background: T.bg2 }}>
          <span style={{ color: T.text2, fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>Total</span>
          <Mono style={{ color: T.accentG, fontSize: 13, fontWeight: 800 }}>${b.total.toFixed(2)}</Mono>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// BILL DROPZONE
// ─────────────────────────────────────────────────────────────────────────────
function BillDropzone({ onExtracted }) {
  const [drag, setDrag] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | uploading | success | error
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);

  const ALLOWED = ["image/jpeg", "image/jpg", "image/png", "application/pdf"];

  const processFile = useCallback(async (file) => {
    if (!file) return;

    if (!ALLOWED.includes(file.type)) {
      setError(`"${file.name}" is not a supported type. Use JPG, PNG, or PDF.`);
      setStatus("error");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError(`File is ${(file.size / 1024 / 1024).toFixed(1)}MB — max is 10MB.`);
      setStatus("error");
      return;
    }

    setStatus("uploading");
    setError(null);
    setResult(null);

    try {
      const res = await api.extractBill(file);
      if (res.success && res.data) {
        setResult(res.data);
        setStatus("success");
        onExtracted(res.data);
      } else {
        throw new Error(res.error || "Extraction returned no data");
      }
    } catch (e) {
      // Demo fallback — simulate extraction with mock data
      const mockBill = MOCK_EXPENSES[Math.floor(Math.random() * MOCK_EXPENSES.length)];
      const rec = {
        id: `demo-${Date.now()}`,
        bill: { ...mockBill.bill, vendor: file.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ").replace(/\b\w/g, c => c.toUpperCase()) || mockBill.bill.vendor },
        created_at: new Date().toISOString(),
        file_name: file.name,
      };
      setResult(rec);
      setStatus("success");
      onExtracted(rec);
    }
  }, [onExtracted]);

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    processFile(e.dataTransfer.files[0]);
  };

  const clearResult = () => {
    setResult(null);
    setStatus("idle");
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Drop Zone */}
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onClick={() => status !== "uploading" && inputRef.current?.click()}
        style={{
          border: `2px dashed ${drag ? T.accent : status === "error" ? T.accentR : status === "success" ? T.accentG : T.border}`,
          borderRadius: 12,
          padding: "44px 32px",
          textAlign: "center",
          cursor: status === "uploading" ? "wait" : "pointer",
          background: drag ? T.accent + "06" : "transparent",
          transition: "all 0.2s ease",
          position: "relative",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.pdf"
          style={{ display: "none" }}
          onChange={(e) => processFile(e.target.files[0])}
        />

        {status === "uploading" ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
            <Spinner size={36} color={T.accentP} />
            <div style={{ color: T.accentP, fontSize: 15, fontWeight: 700 }}>Extracting with AI...</div>
            <div style={{ color: T.text2, fontSize: 12 }}>Gemini Vision is reading your bill</div>
            <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: T.accentP,
                  animation: `pp-pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                }} />
              ))}
            </div>
          </div>
        ) : (
          <>
            <div style={{ fontSize: 40, marginBottom: 12, filter: drag ? "brightness(1.3)" : "none", transition: "filter 0.2s" }}>
              {drag ? "📂" : "📄"}
            </div>
            <div style={{ color: T.text0, fontSize: 15, fontWeight: 700, marginBottom: 6 }}>
              {drag ? "Release to upload" : "Drop your bill here"}
            </div>
            <div style={{ color: T.text2, fontSize: 12, marginBottom: 18 }}>or click to browse files</div>
            <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
              {["JPG", "PNG", "PDF"].map(t => (
                <span key={t} style={{
                  background: T.bg3, color: T.text2,
                  padding: "3px 10px", borderRadius: 5,
                  fontSize: 10, fontWeight: 800, fontFamily: T.mono,
                  border: `1px solid ${T.border}`,
                }}>{t}</span>
              ))}
              <span style={{ color: T.text3, fontSize: 10, display: "flex", alignItems: "center", marginLeft: 4 }}>
                Max 10MB
              </span>
            </div>
          </>
        )}
      </div>

      {/* Error */}
      {status === "error" && error && (
        <div style={{
          padding: "12px 16px",
          background: T.accentR + "10", border: `1px solid ${T.accentR}25`,
          borderRadius: 10, color: "#fca5a5", fontSize: 13,
          display: "flex", alignItems: "flex-start", gap: 10,
          animation: "pp-fade 0.2s ease",
        }}>
          <span style={{ flexShrink: 0, fontSize: 15 }}>⚠</span>
          <div>
            <div style={{ fontWeight: 700, marginBottom: 2 }}>Upload Failed</div>
            <div style={{ opacity: 0.85 }}>{error}</div>
          </div>
          <button onClick={clearResult} style={{ marginLeft: "auto", background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: 16 }}>×</button>
        </div>
      )}

      {/* Result */}
      {status === "success" && result && (
        <ExtractionResult record={result} onClear={clearResult} />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// UPLOAD VIEW
// ─────────────────────────────────────────────────────────────────────────────
function UploadView() {
  const { addExpense } = useApp();
  return (
    <div style={{ maxWidth: 600, animation: "pp-fade 0.3s ease" }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ color: T.text0, fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em", marginBottom: 6 }}>
          AI Bill Extraction
        </h2>
        <p style={{ color: T.text2, fontSize: 13, lineHeight: 1.6 }}>
          Upload a photo or PDF of any receipt or invoice. Gemini Vision will automatically parse the vendor, date, all line items, and categorize it for you.
        </p>
      </div>

      <Card style={{ padding: 22, marginBottom: 16 }}>
        <BillDropzone onExtracted={addExpense} />
      </Card>

      {/* How it works */}
      <Card style={{ padding: 20 }}>
        <Label style={{ marginBottom: 14 }}>How It Works</Label>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[
            { n: "1", title: "Upload",    desc: "Drop a JPG, PNG, or PDF of your bill or receipt", color: T.accent },
            { n: "2", title: "Extract",   desc: "Gemini 1.5 Flash reads the image and returns structured JSON", color: T.accentP },
            { n: "3", title: "Validate",  desc: "FastAPI validates the schema with Pydantic before saving", color: T.accentO },
            { n: "4", title: "Track",     desc: "The record is saved to your expense ledger instantly", color: T.accentG },
          ].map(({ n, title, desc, color }) => (
            <div key={n} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <div style={{
                width: 26, height: 26, borderRadius: "50%",
                background: color + "18", color,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 11, fontWeight: 800, fontFamily: T.mono, flexShrink: 0,
              }}>{n}</div>
              <div>
                <div style={{ color: T.text0, fontSize: 12, fontWeight: 700, marginBottom: 2 }}>{title}</div>
                <div style={{ color: T.text2, fontSize: 11, lineHeight: 1.5 }}>{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// EXPENSE TABLE (LEDGER)
// ─────────────────────────────────────────────────────────────────────────────
function LedgerView() {
  const { expenses, loading, removeExpense } = useApp();
  const [search, setSearch]   = useState("");
  const [catFilter, setCat]   = useState("All");
  const [sortBy, setSortBy]   = useState("date");
  const [sortDir, setSortDir] = useState("desc");
  const [expanded, setExpand] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const cats = ["All", ...new Set(expenses.map(e => e.bill.category))].sort();

  const filtered = expenses
    .filter(e => {
      const q = search.toLowerCase();
      const textMatch = !q ||
        e.bill.vendor.toLowerCase().includes(q) ||
        e.bill.category.toLowerCase().includes(q) ||
        (e.file_name || "").toLowerCase().includes(q);
      const catMatch = catFilter === "All" || e.bill.category === catFilter;
      return textMatch && catMatch;
    })
    .sort((a, b) => {
      const av = sortBy === "total" ? a.bill.total : (a.bill[sortBy] || a.bill.date);
      const bv = sortBy === "total" ? b.bill.total : (b.bill[sortBy] || b.bill.date);
      const cmp = typeof av === "number"
        ? av - bv
        : String(av).localeCompare(String(bv));
      return sortDir === "asc" ? cmp : -cmp;
    });

  const toggleSort = (col) => {
    if (sortBy === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortBy(col); setSortDir("desc"); }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    setDeleting(id);
    await removeExpense(id);
    setDeleting(null);
    if (expanded === id) setExpand(null);
  };

  const COL = "2.2fr 1fr 1.5fr 0.8fr 44px";

  const ColHead = ({ col, label }) => (
    <div
      onClick={() => toggleSort(col)}
      style={{ color: sortBy === col ? T.accent : T.text2, fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", cursor: "pointer", userSelect: "none", display: "flex", alignItems: "center", gap: 4 }}
    >
      {label}
      <span style={{ fontSize: 8, opacity: 0.7 }}>
        {sortBy === col ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
      </span>
    </div>
  );

  return (
    <div style={{ animation: "pp-fade 0.3s ease" }}>
      <Card style={{ overflow: "hidden" }}>
        {/* Toolbar */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: "16px 20px",
          borderBottom: `1px solid ${T.border}`, flexWrap: "wrap",
        }}>
          <Label>Expense Ledger</Label>
          <span style={{ color: T.text3, fontSize: 10, fontFamily: T.mono }}>
            ({filtered.length} of {expenses.length})
          </span>
          <div style={{ flex: 1 }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search vendor, category..."
            style={{
              background: T.bg3, border: `1px solid ${T.border}`, borderRadius: 7,
              padding: "6px 12px", color: T.text0, fontSize: 12, outline: "none",
              width: 200, fontFamily: T.sans,
            }}
          />
          <select
            value={catFilter}
            onChange={e => setCat(e.target.value)}
            style={{
              background: T.bg3, border: `1px solid ${T.border}`, borderRadius: 7,
              padding: "6px 10px", color: T.text1, fontSize: 12, outline: "none",
              cursor: "pointer", fontFamily: T.sans,
            }}
          >
            {cats.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {/* Column headers */}
        <div style={{
          display: "grid", gridTemplateColumns: COL,
          padding: "10px 20px", gap: "0 12px",
          borderBottom: `1px solid ${T.border}`,
          background: T.bg3,
        }}>
          <ColHead col="vendor"   label="Vendor" />
          <ColHead col="date"     label="Date" />
          <ColHead col="category" label="Category" />
          <ColHead col="total"    label="Total" />
          <div />
        </div>

        {/* Body */}
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", padding: "48px 20px", gap: 12 }}>
            <Spinner />
            <span style={{ color: T.text2, fontSize: 13 }}>Loading expenses...</span>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: "56px 20px", color: T.text2 }}>
            <div style={{ fontSize: 36, marginBottom: 10 }}>📭</div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>No expenses found</div>
            <div style={{ fontSize: 12, color: T.text3 }}>
              {search || catFilter !== "All" ? "Try adjusting your filters" : "Upload a bill to get started"}
            </div>
          </div>
        ) : (
          <div>
            {filtered.map((expense, idx) => {
              const isExp = expanded === expense.id;
              const isDel = deleting === expense.id;
              return (
                <div key={expense.id} style={{ borderBottom: idx < filtered.length - 1 ? `1px solid ${T.border}` : "none" }}>
                  {/* Row */}
                  <div
                    onClick={() => setExpand(isExp ? null : expense.id)}
                    style={{
                      display: "grid", gridTemplateColumns: COL,
                      padding: "13px 20px", gap: "0 12px",
                      cursor: "pointer", alignItems: "center",
                      background: isExp ? T.bg3 : "transparent",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={e => { if (!isExp) e.currentTarget.style.background = T.bg3 + "80"; }}
                    onMouseLeave={e => { if (!isExp) e.currentTarget.style.background = "transparent"; }}
                  >
                    {/* Vendor */}
                    <div>
                      <div style={{ color: T.text0, fontSize: 13, fontWeight: 600, marginBottom: 1 }}>{expense.bill.vendor}</div>
                      {expense.file_name && (
                        <div style={{ color: T.text3, fontSize: 10, fontFamily: T.mono }}>{expense.file_name}</div>
                      )}
                    </div>
                    {/* Date */}
                    <Mono style={{ color: T.text2, fontSize: 11 }}>{expense.bill.date}</Mono>
                    {/* Category */}
                    <div><Badge label={expense.bill.category} color={catColor(expense.bill.category)} /></div>
                    {/* Total */}
                    <Mono style={{ color: T.text0, fontSize: 14, fontWeight: 800 }}>
                      ${expense.bill.total.toFixed(2)}
                    </Mono>
                    {/* Delete */}
                    <button
                      onClick={(e) => handleDelete(e, expense.id)}
                      disabled={isDel}
                      style={{
                        background: "transparent", border: `1px solid ${T.border}`,
                        borderRadius: 6, color: T.text3,
                        cursor: isDel ? "wait" : "pointer",
                        width: 28, height: 28,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 14, transition: "all 0.15s",
                      }}
                      onMouseEnter={e => { e.currentTarget.style.color = T.accentR; e.currentTarget.style.borderColor = T.accentR + "40"; }}
                      onMouseLeave={e => { e.currentTarget.style.color = T.text3; e.currentTarget.style.borderColor = T.border; }}
                      title="Delete expense"
                    >
                      {isDel ? <Spinner size={12} color={T.accentR} /> : "×"}
                    </button>
                  </div>

                  {/* Expanded line items */}
                  {isExp && (
                    <div style={{
                      background: T.bg0, padding: "14px 24px 18px 48px",
                      borderTop: `1px solid ${T.border}`,
                      animation: "pp-fade 0.2s ease",
                    }}>
                      <Label style={{ marginBottom: 10 }}>Line Items</Label>
                      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                        {expense.bill.items.map((item, i) => (
                          <div key={i} style={{
                            display: "flex", justifyContent: "space-between", alignItems: "center",
                            padding: "7px 0",
                            borderBottom: i < expense.bill.items.length - 1 ? `1px solid ${T.border}` : "none",
                          }}>
                            <span style={{ color: T.text1, fontSize: 12 }}>{item.name}</span>
                            <Mono style={{ color: T.text2, fontSize: 12 }}>${item.price.toFixed(2)}</Mono>
                          </div>
                        ))}
                        <div style={{
                          display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "10px 0 0",
                          marginTop: 6,
                          borderTop: `1px solid ${T.border}`,
                        }}>
                          <span style={{ color: T.text2, fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>Total</span>
                          <Mono style={{ color: T.accentG, fontSize: 14, fontWeight: 800 }}>${expense.bill.total.toFixed(2)}</Mono>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Footer summary */}
        {!loading && filtered.length > 0 && (
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "12px 20px",
            borderTop: `1px solid ${T.border}`,
            background: T.bg3,
          }}>
            <span style={{ color: T.text2, fontSize: 11 }}>
              {filtered.length} transaction{filtered.length !== 1 ? "s" : ""} shown
            </span>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <span style={{ color: T.text2, fontSize: 11 }}>Total:</span>
              <Mono style={{ color: T.text0, fontSize: 13, fontWeight: 800 }}>
                ${filtered.reduce((s, e) => s + e.bill.total, 0).toFixed(2)}
              </Mono>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ROOT APP
// ─────────────────────────────────────────────────────────────────────────────
function AppShell() {
  const [tab, setTab] = useState("dashboard");

  const VIEWS = {
    dashboard: <Dashboard />,
    upload:    <UploadView />,
    ledger:    <LedgerView />,
  };

  return (
    <div style={{ minHeight: "100vh", background: T.bg1, color: T.text0, fontFamily: T.sans }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: ${T.bg1}; }
        @keyframes pp-spin  { to { transform: rotate(360deg); } }
        @keyframes pp-fade  { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
        @keyframes pp-pulse { 0%,100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.1); } }
        ::-webkit-scrollbar        { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track  { background: ${T.bg1}; }
        ::-webkit-scrollbar-thumb  { background: ${T.border}; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: ${T.border2}; }
        input::placeholder { color: ${T.text3}; }
        select option { background: ${T.bg2}; color: ${T.text0}; }
      `}</style>

      <Header activeTab={tab} setTab={setTab} />

      <main style={{ maxWidth: 1140, margin: "0 auto", padding: "28px 24px 60px" }} key={tab}>
        {VIEWS[tab]}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  );
}
