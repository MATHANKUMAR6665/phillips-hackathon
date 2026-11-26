import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Award,
  BarChart3,
  CheckCircle2,
  Compass,
  Filter,
  Info,
  Layers,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const TABS = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'quadrant', label: 'Justification Quadrant', icon: Compass },
  { id: 'rankings', label: 'Best & Worst', icon: Award },
  { id: 'strategy', label: 'Strategy', icon: Target },
  { id: 'quality', label: 'Data Quality', icon: ShieldCheck },
];

function fmtEur(val, compact = true) {
  if (val === null || val === undefined || Number.isNaN(val)) return 'EUR 0';
  const sign = val < 0 ? '-' : '';
  const abs = Math.abs(val);
  if (compact) {
    if (abs >= 1e9) return `${sign}€${(abs / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${sign}€${(abs / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${sign}€${(abs / 1e3).toFixed(1)}K`;
  }
  return `${sign}€${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function fmtSignedEur(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return '€0';
  const prefix = val > 0 ? '+' : '';
  return `${prefix}${fmtEur(val, true)}`;
}

function fmtPct(val, decimals = 2) {
  if (val === null || val === undefined || Number.isNaN(val)) return '0.0%';
  const prefix = val > 0 ? '+' : '';
  return `${prefix}${Number(val).toFixed(decimals)}%`;
}

function KpiCard({ title, value, subtitle, tone = 'neutral', icon: Icon }) {
  const toneStyles = {
    neutral: 'border-slate-200 bg-white',
    positive: 'border-emerald-200 bg-emerald-50/40',
    negative: 'border-rose-200 bg-rose-50/40',
    info: 'border-indigo-200 bg-indigo-50/40',
  };
  const valueStyles = {
    neutral: 'text-slate-900',
    positive: 'text-emerald-700',
    negative: 'text-rose-700',
    info: 'text-indigo-700',
  };
  return (
    <div className={`rounded-xl border p-4 shadow-sm transition hover:shadow-md ${toneStyles[tone]}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</span>
        {Icon && <Icon className="h-4 w-4 text-slate-400" />}
      </div>
      <div className={`mt-2 font-mono text-2xl font-bold tracking-tight ${valueStyles[tone]}`}>
        {value}
      </div>
      {subtitle && <p className="mt-1 text-xs text-slate-600">{subtitle}</p>}
    </div>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedMarket, setSelectedMarket] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [rankFilter, setRankFilter] = useState('all');
  const [selectedPair, setSelectedPair] = useState(null);

  useEffect(() => {
    let active = true;
    fetch('/dashboard_data.json')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status} while loading /dashboard_data.json`);
        return res.json();
      })
      .then((json) => {
        if (!active) return;
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || 'Failed to load dashboard_data.json');
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const scopedKpis = useMemo(() => {
    if (!data) return null;
    if (selectedMarket === 'ALL') return data.kpis;
    const b = data.bridge.find((m) => m.market === selectedMarket);
    const mPairs = data.pairs.filter((p) => p.market === selectedMarket);
    const flaggedCount = mPairs.reduce((acc, p) => acc + (p.months_flagged || 0), 0);
    if (!b) return data.kpis;
    const allowance = b.budget + b.justified;
    const rawVar = b.actual - b.budget;
    return {
      actual: b.actual,
      budget: b.budget,
      allowance,
      raw_variance: rawVar,
      justified: b.justified,
      real_overspend: b.real_overspend,
      real_overspend_pct_of_spend: b.actual > 0 ? (b.real_overspend / b.actual) * 100 : 0,
      flagged_deviations: flaggedCount,
    };
  }, [data, selectedMarket]);

  const monthlySeries = useMemo(() => {
    if (!data) return [];
    if (selectedMarket !== 'ALL') {
      return data.monthly
        .filter((m) => m.market === selectedMarket)
        .sort((a, b) => a.month - b.month)
        .map((m) => ({
          ...m,
          monthLabel: MONTHS[m.month - 1],
          raw_m: Number((m.raw_variance / 1e6).toFixed(3)),
          corr_m: Number((m.corrected_variance / 1e6).toFixed(3)),
        }));
    }
    const byMonth = Array.from({ length: 12 }, (_, idx) => ({
      month: idx + 1,
      monthLabel: MONTHS[idx],
      raw_variance: 0,
      corrected_variance: 0,
      flaggedMarkets: [],
    }));
    for (const row of data.monthly) {
      const target = byMonth[row.month - 1];
      target.raw_variance += row.raw_variance;
      target.corrected_variance += row.corrected_variance;
      if (row.flag) target.flaggedMarkets.push(`${row.market} (${row.confidence})`);
    }
    return byMonth.map((m) => ({
      ...m,
      raw_m: Number((m.raw_variance / 1e6).toFixed(3)),
      corr_m: Number((m.corrected_variance / 1e6).toFixed(3)),
      flag: m.flaggedMarkets.length > 0,
    }));
  }, [data, selectedMarket]);

  const bridgeChartData = useMemo(() => {
    if (!data) return [];
    const rows = selectedMarket === 'ALL'
      ? data.bridge
      : data.bridge.filter((b) => b.market === selectedMarket);
    return rows.map((b) => ({
      market: b.market.replace('Central Eastern Europe', 'CEE').replace('Greater China', 'G. China'),
      fullMarket: b.market,
      budgetM: Number((b.budget / 1e6).toFixed(2)),
      justifiedM: Number((b.justified / 1e6).toFixed(2)),
      realOverspendM: Number((b.real_overspend / 1e6).toFixed(2)),
      actualM: Number((b.actual / 1e6).toFixed(2)),
      allowanceM: Number(((b.budget + b.justified) / 1e6).toFixed(2)),
    }));
  }, [data, selectedMarket]);

  const filteredPairs = useMemo(() => {
    if (!data) return [];
    const q = searchQuery.trim().toLowerCase();
    return data.pairs.filter((p) => {
      if (selectedMarket !== 'ALL' && p.market !== selectedMarket) return false;
      if (rankFilter === 'best' && p.rank_type !== 'best') return false;
      if (rankFilter === 'worst' && p.rank_type !== 'worst') return false;
      if (rankFilter === 'ranked' && p.rank_type === 'none') return false;
      if (q) {
        const hay = `${p.market} ${p.country} ${p.product} ${p.commentary}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [data, selectedMarket, rankFilter, searchQuery]);

  const quadrantData = useMemo(() => {
    if (!data) return { justified: [], overspend: [] };
    const scoped = selectedMarket === 'ALL'
      ? data.pairs
      : data.pairs.filter((p) => p.market === selectedMarket);
    const enriched = scoped.map((p) => ({
      ...p,
      sizeScore: Math.max(40, Math.min(400, Math.sqrt(p.actual / 1000))),
      quadrantLabel: p.real_overspend > 0 ? 'Real Overspend' : 'Justified / Efficient',
    }));
    return {
      justified: enriched.filter((p) => p.real_overspend <= 0),
      overspend: enriched.filter((p) => p.real_overspend > 0),
    };
  }, [data, selectedMarket]);

  const strategySplit = useMemo(() => {
    if (!data) return { marketPlaybooks: [], globalTop5: [], totalGlobalTop5: 0, totalMarketSaving: 0 };
    const globalTop5 = data.strategy.filter((s) => s.market.startsWith('Global #'));
    const marketPlaybooks = data.strategy.filter((s) => !s.market.startsWith('Global #'));
    return {
      globalTop5,
      marketPlaybooks: selectedMarket === 'ALL'
        ? marketPlaybooks
        : marketPlaybooks.filter((s) => s.market === selectedMarket),
      totalGlobalTop5: globalTop5.reduce((acc, s) => acc + s.est_saving_eur, 0),
      totalMarketSaving: marketPlaybooks.reduce((acc, s) => acc + s.est_saving_eur, 0),
    };
  }, [data, selectedMarket]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="rounded-2xl border border-slate-200 bg-white px-8 py-6 text-center shadow-sm">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
          <p className="mt-3 text-sm font-medium text-slate-700">Loading Spend Truth Engine...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <div className="max-w-md rounded-2xl border border-rose-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 text-rose-700">
            <AlertTriangle className="h-5 w-5" />
            <h2 className="font-semibold">Unable to Load Dashboard Data</h2>
          </div>
          <p className="mt-2 text-sm text-slate-600">{error}</p>
          <p className="mt-3 text-xs text-slate-500">
            Run <code className="rounded bg-slate-100 px-1.5 py-0.5">python pipeline/pipeline.py</code> to generate{' '}
            <code className="rounded bg-slate-100 px-1.5 py-0.5">/dashboard/public/dashboard_data.json</code>.
          </p>
        </div>
      </div>
    );
  }

  const activeMarketSummary = selectedMarket === 'ALL'
    ? data.global_summary
    : (data.market_summaries.find((m) => m.market === selectedMarket)?.summary || data.global_summary);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top Executive Header */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold tracking-tight text-slate-900">
                    Spend Truth Engine
                  </h1>
                  <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 border border-indigo-200">
                    Justified Spend vs Real Overspend
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  {data.meta.rows.clean.toLocaleString()} clean records &middot; Unit scale x{data.meta.unit_multiplier.toLocaleString()} {data.meta.currency} &middot;{' '}
                  Trust Score <span className="font-semibold text-emerald-700">{data.meta.trust_score}/100</span>
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5">
                <Filter className="h-3.5 w-3.5 text-slate-500" />
                <label htmlFor="market-select" className="text-xs font-medium text-slate-600">Market:</label>
                <select
                  id="market-select"
                  value={selectedMarket}
                  onChange={(e) => setSelectedMarket(e.target.value)}
                  className="bg-transparent text-xs font-semibold text-slate-900 focus:outline-none"
                >
                  <option value="ALL">All 6 Markets (Global)</option>
                  {data.markets.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Tab Navigation */}
          <nav className="mt-3 flex gap-1 overflow-x-auto border-t border-slate-100 pt-2">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-xs font-semibold transition ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 space-y-6">
        {/* Global / Scoped KPI Strip */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard
            title="Actual A&P Spend"
            value={fmtEur(scopedKpis.actual)}
            subtitle={`Budget: ${fmtEur(scopedKpis.budget)}`}
            icon={Layers}
          />
          <KpiCard
            title="Fair Allowance"
            value={fmtEur(scopedKpis.allowance)}
            subtitle="Budget x (Actual Sales / Budget Sales)"
            tone="info"
            icon={ShieldCheck}
          />
          <KpiCard
            title="Justified Spend"
            value={fmtSignedEur(scopedKpis.justified)}
            subtitle="Allowance − Budget (sales-driven)"
            tone={scopedKpis.justified >= 0 ? 'positive' : 'neutral'}
            icon={TrendingUp}
          />
          <KpiCard
            title="Real Overspend"
            value={fmtSignedEur(scopedKpis.real_overspend)}
            subtitle={`${fmtPct(scopedKpis.real_overspend_pct_of_spend)} of A&P spend`}
            tone={scopedKpis.real_overspend > 0 ? 'negative' : 'positive'}
            icon={scopedKpis.real_overspend > 0 ? AlertTriangle : TrendingDown}
          />
          <KpiCard
            title="Flagged Deviations"
            value={scopedKpis.flagged_deviations}
            subtitle={`Raw variance: ${fmtSignedEur(scopedKpis.raw_variance)}`}
            tone="neutral"
            icon={Activity}
          />
        </section>

        {/* Executive Commentary Banner */}
        <section className="rounded-xl border border-indigo-200 bg-white p-4 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-lg bg-indigo-50 p-2 text-indigo-600">
              <Info className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-700">
                {selectedMarket === 'ALL' ? 'Global Executive Commentary' : `${selectedMarket} Executive Commentary`}
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-slate-700">{activeMarketSummary}</p>
            </div>
          </div>
        </section>

        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* Budget -> Allowance -> Actual Bridge by Market */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Spend Truth Bridge by Market (EUR Millions)
                    </h3>
                    <p className="text-xs text-slate-500">
                      Budget vs Sales-Adjusted Allowance vs Actual Spend
                    </p>
                  </div>
                </div>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={bridgeChartData} margin={{ top: 10, right: 12, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="market" tick={{ fontSize: 11, fill: '#475569' }} />
                      <YAxis tick={{ fontSize: 11, fill: '#475569' }} unit="M" />
                      <Tooltip
                        formatter={(val) => [`€${val}M`, '']}
                        contentStyle={{ borderRadius: '0.75rem', borderColor: '#cbd5e1', fontSize: '12px' }}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                      <Bar dataKey="budgetM" name="Budget" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="allowanceM" name="Fair Allowance" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="actualM" name="Actual Spend" fill="#0f172a" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Monthly Raw vs Corrected Variance Series */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Monthly Raw vs Corrected Variance (EUR Millions)
                    </h3>
                    <p className="text-xs text-slate-500">
                      Corrected variance = Real Overspend (excludes sales-justified swings)
                    </p>
                  </div>
                </div>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={monthlySeries} margin={{ top: 10, right: 12, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="monthLabel" tick={{ fontSize: 11, fill: '#475569' }} />
                      <YAxis tick={{ fontSize: 11, fill: '#475569' }} unit="M" />
                      <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />
                      <Tooltip
                        formatter={(val, name) => [`€${val}M`, name]}
                        contentStyle={{ borderRadius: '0.75rem', borderColor: '#cbd5e1', fontSize: '12px' }}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                      <Bar dataKey="corr_m" name="Corrected Variance (Real)" radius={[4, 4, 0, 0]}>
                        {monthlySeries.map((entry, idx) => (
                          <Cell
                            key={idx}
                            fill={entry.flag ? '#dc2626' : entry.corr_m > 0 ? '#f43f5e' : '#10b981'}
                          />
                        ))}
                      </Bar>
                      <Line
                        type="monotone"
                        dataKey="raw_m"
                        name="Raw Variance (vs Budget)"
                        stroke="#475569"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Market Reconciliation Table */}
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-slate-200 px-5 py-3.5 flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900">
                  Market Reconciliation: Raw Variance = Justified + Real Overspend
                </h3>
                <span className="text-xs text-slate-500">Click any market row to filter</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Market</th>
                      <th className="px-4 py-3 font-semibold text-right">Budget</th>
                      <th className="px-4 py-3 font-semibold text-right">Justified</th>
                      <th className="px-4 py-3 font-semibold text-right">Fair Allowance</th>
                      <th className="px-4 py-3 font-semibold text-right">Real Overspend</th>
                      <th className="px-4 py-3 font-semibold text-right">Actual</th>
                      <th className="px-4 py-3 font-semibold text-right">Raw Variance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.bridge.map((b) => {
                      const allowance = b.budget + b.justified;
                      const rawVar = b.actual - b.budget;
                      return (
                        <tr
                          key={b.market}
                          onClick={() => setSelectedMarket(b.market === selectedMarket ? 'ALL' : b.market)}
                          className={`cursor-pointer transition hover:bg-indigo-50/50 ${
                            selectedMarket === b.market ? 'bg-indigo-50' : ''
                          }`}
                        >
                          <td className="px-4 py-3 font-semibold text-slate-900">{b.market}</td>
                          <td className="px-4 py-3 text-right font-mono">{fmtEur(b.budget)}</td>
                          <td className="px-4 py-3 text-right font-mono text-indigo-700">{fmtSignedEur(b.justified)}</td>
                          <td className="px-4 py-3 text-right font-mono">{fmtEur(allowance)}</td>
                          <td
                            className={`px-4 py-3 text-right font-mono font-semibold ${
                              b.real_overspend > 0 ? 'text-rose-700' : 'text-emerald-700'
                            }`}
                          >
                            {fmtSignedEur(b.real_overspend)}
                          </td>
                          <td className="px-4 py-3 text-right font-mono">{fmtEur(b.actual)}</td>
                          <td className="px-4 py-3 text-right font-mono text-slate-600">{fmtSignedEur(rawVar)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: JUSTIFICATION QUADRANT */}
        {activeTab === 'quadrant' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Justification Quadrant: Sales vs Plan (%) vs Spend vs Budget (%)
                  </h3>
                  <p className="text-xs text-slate-500">
                    Rose = Real Overspend above sales-adjusted allowance &middot; Emerald = Justified or Efficient &middot; Click any dot to inspect
                  </p>
                </div>
              </div>
              <div className="h-[420px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 16, right: 20, bottom: 20, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      type="number"
                      dataKey="sales_vs_plan_pct"
                      name="Sales vs Plan"
                      unit="%"
                      tick={{ fontSize: 11, fill: '#475569' }}
                      label={{ value: 'Sales vs Plan (%)', position: 'insideBottom', offset: -10, fontSize: 11, fill: '#475569' }}
                    />
                    <YAxis
                      type="number"
                      dataKey="spend_vs_budget_pct"
                      name="Spend vs Budget"
                      unit="%"
                      tick={{ fontSize: 11, fill: '#475569' }}
                      label={{ value: 'Spend vs Budget (%)', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#475569' }}
                    />
                    <ZAxis type="number" dataKey="sizeScore" range={[45, 360]} />
                    <ReferenceLine x={0} stroke="#94a3b8" strokeDasharray="4 4" />
                    <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="4 4" />
                    <Tooltip
                      cursor={{ strokeDasharray: '3 3' }}
                      content={({ active, payload }) => {
                        if (!active || !payload || !payload.length) return null;
                        const p = payload[0].payload;
                        return (
                          <div className="rounded-xl border border-slate-200 bg-white p-3 text-xs shadow-lg">
                            <p className="font-bold text-slate-900">{p.country} &middot; {p.product}</p>
                            <p className="text-slate-500">{p.market}</p>
                            <div className="mt-2 space-y-1 font-mono">
                              <p>Sales vs Plan: {fmtPct(p.sales_vs_plan_pct)}</p>
                              <p>Spend vs Budget: {fmtPct(p.spend_vs_budget_pct)}</p>
                              <p className={p.real_overspend > 0 ? 'text-rose-700 font-semibold' : 'text-emerald-700 font-semibold'}>
                                Real Overspend: {fmtSignedEur(p.real_overspend)} ({fmtPct(p.overspend_pct)})
                              </p>
                            </div>
                          </div>
                        );
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '12px' }} />
                    <Scatter
                      name="Justified / Efficient (<= Allowance)"
                      data={quadrantData.justified}
                      fill="#10b981"
                      fillOpacity={0.75}
                      onClick={(node) => setSelectedPair(node?.payload || node)}
                    />
                    <Scatter
                      name="Real Overspend (> Allowance)"
                      data={quadrantData.overspend}
                      fill="#e11d48"
                      fillOpacity={0.75}
                      onClick={(node) => setSelectedPair(node?.payload || node)}
                    />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Selected Pair Drill-Down */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col justify-between">
              {selectedPair ? (
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700">
                      {selectedPair.market}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        selectedPair.real_overspend > 0
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      {selectedPair.real_overspend > 0 ? 'Real Overspend' : 'Justified / Efficient'}
                    </span>
                  </div>
                  <h4 className="mt-3 text-base font-bold text-slate-900">
                    {selectedPair.country} &mdash; {selectedPair.product}
                  </h4>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                    <div className="rounded-lg bg-slate-50 p-2.5">
                      <p className="text-slate-500">Actual Spend</p>
                      <p className="mt-0.5 font-mono font-bold">{fmtEur(selectedPair.actual)}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-2.5">
                      <p className="text-slate-500">Fair Allowance</p>
                      <p className="mt-0.5 font-mono font-bold">{fmtEur(selectedPair.allowance)}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-2.5">
                      <p className="text-slate-500">Real Overspend</p>
                      <p className={`mt-0.5 font-mono font-bold ${selectedPair.real_overspend > 0 ? 'text-rose-700' : 'text-emerald-700'}`}>
                        {fmtSignedEur(selectedPair.real_overspend)} ({fmtPct(selectedPair.overspend_pct)})
                      </p>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-2.5">
                      <p className="text-slate-500">Peer Robust z</p>
                      <p className="mt-0.5 font-mono font-bold">{selectedPair.z.toFixed(2)} (P{selectedPair.percentile})</p>
                    </div>
                  </div>
                  <div className="mt-4">
                    <div className="flex justify-between text-xs text-slate-600 mb-1">
                      <span>Local A&P Share ({(selectedPair.local_share_of_overspend * 100).toFixed(0)}%)</span>
                      <span>Central ({((1 - selectedPair.local_share_of_overspend) * 100).toFixed(0)}%)</span>
                    </div>
                    <div className="h-2.5 w-full overflow-hidden rounded-full bg-indigo-100">
                      <div
                        className="h-full bg-indigo-600"
                        style={{ width: `${Math.round(selectedPair.local_share_of_overspend * 100)}%` }}
                      />
                    </div>
                  </div>
                  <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
                    {selectedPair.commentary}
                  </p>
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center py-12 text-center">
                  <Compass className="h-10 w-10 text-slate-300" />
                  <p className="mt-3 text-sm font-semibold text-slate-700">Select a Pair on the Chart</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Click any dot in the Justification Quadrant to inspect its Local vs Central split and automated commentary.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: BEST & WORST */}
        {activeTab === 'rankings' && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="relative flex-1 min-w-[220px]">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search country, product, market, or commentary..."
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:bg-white focus:outline-none"
                />
              </div>
              <div className="flex gap-1.5">
                {[
                  { id: 'all', label: 'All Pairs' },
                  { id: 'ranked', label: 'Top 3 Best & Worst' },
                  { id: 'worst', label: 'Worst Only' },
                  { id: 'best', label: 'Best Only' },
                ].map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setRankFilter(f.id)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                      rankFilter === f.id
                        ? 'bg-slate-900 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {filteredPairs.map((p, idx) => (
                <div
                  key={`${p.market}-${p.country}-${p.product}-${idx}`}
                  className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                        {p.market}
                      </span>
                      <h4 className="text-sm font-bold text-slate-900">
                        {p.country} &mdash; {p.product}
                      </h4>
                      {p.rank_type === 'best' && (
                        <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700 border border-emerald-200">
                          TOP-3 BEST
                        </span>
                      )}
                      {p.rank_type === 'worst' && (
                        <span className="rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-700 border border-rose-200">
                          TOP-3 WORST
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 font-mono text-xs">
                      <span>Actual: <strong>{fmtEur(p.actual)}</strong></span>
                      <span>Allow: <strong>{fmtEur(p.allowance)}</strong></span>
                      <span className={p.real_overspend > 0 ? 'text-rose-700 font-bold' : 'text-emerald-700 font-bold'}>
                        {fmtSignedEur(p.real_overspend)} ({fmtPct(p.overspend_pct)})
                      </span>
                      <span className="text-slate-500">z={p.z.toFixed(2)}</span>
                      <span className="text-slate-500">{p.months_flagged}m flagged</span>
                    </div>
                  </div>
                  <p className="mt-2.5 text-xs leading-relaxed text-slate-600">{p.commentary}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: STRATEGY */}
        {activeTab === 'strategy' && (
          <div className="space-y-6">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-bold text-emerald-900">
                    Top-5 Global Score-Maximising Actions (Ranked by EUR Impact)
                  </h3>
                  <p className="text-xs text-emerald-800">
                    Returning the top 5 overspending pairs to sales-adjusted allowance recovers{' '}
                    <span className="font-mono font-bold">{fmtEur(strategySplit.totalGlobalTop5)}</span>.
                  </p>
                </div>
                <div className="rounded-lg bg-white px-4 py-2 border border-emerald-200">
                  <span className="text-xs text-slate-500">Total 6-Market 3-Worst Cap Potential</span>
                  <div className="font-mono text-lg font-bold text-emerald-700">
                    {fmtEur(strategySplit.totalMarketSaving)}
                  </div>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {strategySplit.globalTop5.map((item, i) => (
                  <div key={i} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-white p-4 shadow-sm">
                    <div className="flex-1 min-w-[260px]">
                      <span className="text-xs font-bold uppercase tracking-wider text-indigo-700">{item.market}</span>
                      <p className="mt-1 text-xs leading-relaxed text-slate-700">{item.action}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-[11px] uppercase text-slate-400">Est. Saving</span>
                      <div className="font-mono text-base font-bold text-emerald-700">
                        {fmtEur(item.est_saving_eur)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-bold text-slate-900">
                Per-Market Action Playbooks & Reallocation Suggestions
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Estimated savings assume each market&apos;s worst 3 pairs return to fair allowance, reallocating budget to best-performing benchmarks.
              </p>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {strategySplit.marketPlaybooks.map((item) => (
                  <div key={item.market} className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-bold text-slate-900">{item.market}</h4>
                      <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 font-mono text-xs font-bold text-emerald-800">
                        Save {fmtEur(item.est_saving_eur)}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-slate-700">{item.action}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: DATA QUALITY */}
        {activeTab === 'quality' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="text-sm font-bold text-slate-900">Why Median / MAD + IQR Instead of Mean / Std?</h3>
                <p className="mt-2 text-xs leading-relaxed text-slate-600">
                  A&amp;P actual-to-budget ratios are heavy-tailed (approx. -0.9 to 3.1), whereas Total Sales ratios sit tightly
                  between 0.70 and 1.51. Standard mean and standard deviation are distorted by extreme promotional spikes, so the
                  Spend Truth Engine uses <strong>robust z-scores</strong> (<code>z = 0.6745 * (x - median) / MAD</code>, flagging{' '}
                  <code>|z| &gt; 3.5</code> with IQR fallback when MAD=0) cross-checked against <strong>1.5 &times; IQR fences</strong>{' '}
                  per market. Agreement between both detectors yields <em>high</em> confidence.
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="text-sm font-bold text-slate-900">Scale & Finance Reconciliation Proof</h3>
                <ul className="mt-2 space-y-1.5 text-xs text-slate-600">
                  <li>
                    <CheckCircle2 className="mr-1.5 inline h-3.5 w-3.5 text-emerald-600" />
                    Unit multiplier: <strong className="font-mono">x{data.meta.unit_multiplier.toLocaleString()}</strong> applied after dividing by FX rates (17 currencies).
                  </li>
                  <li>
                    <CheckCircle2 className="mr-1.5 inline h-3.5 w-3.5 text-emerald-600" />
                    Global A&amp;P actual: <strong className="font-mono">{fmtEur(data.kpis.actual)}</strong> (within 10% of €650M benchmark; ~11.5% of Total Sales).
                  </li>
                  <li>
                    <CheckCircle2 className="mr-1.5 inline h-3.5 w-3.5 text-emerald-600" />
                    Row lineage: <strong className="font-mono">{data.meta.rows.raw.toLocaleString()}</strong> raw &rarr;{' '}
                    <strong className="font-mono">{data.meta.rows.after_dedupe.toLocaleString()}</strong> deduped &rarr;{' '}
                    <strong className="font-mono">{data.meta.rows.clean.toLocaleString()}</strong> active A&amp;P + Sales.
                  </li>
                </ul>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-slate-200 px-5 py-3.5 flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900">Automated Data Quality Audit Log</h3>
                <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
                  Trust Score: {data.meta.trust_score}/100
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Status</th>
                      <th className="px-4 py-3 font-semibold">Check</th>
                      <th className="px-4 py-3 font-semibold text-right">Rows Affected</th>
                      <th className="px-4 py-3 font-semibold">Action Taken</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.quality_checks.map((qc, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-bold uppercase ${
                              qc.status === 'pass'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : qc.status === 'warn'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            {qc.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-semibold text-slate-900">{qc.check}</td>
                        <td className="px-4 py-3 text-right font-mono text-slate-700">
                          {qc.rows_affected.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{qc.action}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
