import type { Metadata } from "next";

import { Colophon } from "@/components/Colophon";
import { Masthead } from "@/components/Masthead";
import { type Asset, type HistoryPoint, loadLedger } from "@/lib/ledger";
import { pct } from "@/lib/model";

export const metadata: Metadata = { title: "Ledger" };
export const dynamic = "force-dynamic";

const STATUS_LABEL: Record<string, string> = {
  "quantum-broken": "Quantum-broken",
  "classically-broken": "Broken today",
  "quantum-weakened": "Weakened",
  hybrid: "Hybrid",
  "quantum-safe": "Safe",
};

const STATUS_SWATCH: Record<string, string> = {
  "quantum-broken": "swatch-broken",
  "classically-broken": "swatch-classical",
  "quantum-weakened": "swatch-weak",
  hybrid: "swatch-safe",
  "quantum-safe": "swatch-safe",
};

function startBy(a: Asset): string {
  if (a.status === "classically-broken") return "now";
  if (a.status !== "quantum-broken" || a.deadline_year === null) return "—";
  return a.years_late > 0 ? `overdue ${a.years_late.toFixed(1)} yr` : String(Math.floor(a.deadline_year));
}

function Trend({ points }: { points: HistoryPoint[] }) {
  if (points.length < 2) {
    return <p className="muted" style={{ margin: 0 }}>The trend starts after the second recorded scan.</p>;
  }
  const W = 720;
  const H = 140;
  const PAD_X = 28;
  const max = Math.max(...points.map((p) => p.to_migrate), 1);
  const x = (i: number) => PAD_X + (i / (points.length - 1)) * (W - 2 * PAD_X);
  const y = (v: number) => H - (v / max) * (H - 30) - 4;
  const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.to_migrate).toFixed(1)}`).join(" ");
  const first = points[0]!;
  const last = points[points.length - 1]!;
  const sameDay = first.at.slice(0, 10) === last.at.slice(0, 10);
  const stamp = (at: string) => (sameDay ? at.slice(11, 16) + " UTC" : at.slice(0, 10));
  const change = last.to_migrate - first.to_migrate;
  return (
    <div style={{ maxWidth: W }}>
      <p style={{ margin: "0 0 12px" }}>
        Assets needing migration, across {points.length} scans:{" "}
        <strong>
          {first.to_migrate} to {last.to_migrate}
        </strong>{" "}
        <span className="muted">({change === 0 ? "no change" : change < 0 ? `${-change} fewer` : `${change} more`})</span>
      </p>
      <svg className="chart" viewBox={`0 0 ${W} ${H + 26}`} role="img"
        aria-label={`Assets needing migration over ${points.length} scans, from ${first.to_migrate} to ${last.to_migrate}.`}>
        <line className="grid-line" x1={PAD_X} x2={W - PAD_X} y1={y(max)} y2={y(max)} />
        <line className="axis" x1={PAD_X} x2={W - PAD_X} y1={H} y2={H} />
        <text x={0} y={H + 4}>0</text>
        <polyline points={line} fill="none" stroke="var(--ink)" strokeWidth={1.5} />
        {points.map((p, i) => (
          <g key={p.seq}>
            <circle cx={x(i)} cy={y(p.to_migrate)} r={3.5} fill={i === points.length - 1 ? "var(--signal)" : "var(--ink)"} />
            {(i === 0 || i === points.length - 1) && (
              <text x={x(i)} y={y(p.to_migrate) - 10} textAnchor={i === 0 ? "start" : "end"}>
                {p.to_migrate}
              </text>
            )}
          </g>
        ))}
        <text x={PAD_X} y={H + 20}>{stamp(first.at)}</text>
        <text x={W - PAD_X} y={H + 20} textAnchor="end">{stamp(last.at)}</text>
      </svg>
    </div>
  );
}

export default async function LedgerPage({ searchParams }: { searchParams: Promise<{ repo?: string }> }) {
  const { repo } = await searchParams;
  const view = await loadLedger(repo);
  const a = view.assessment;
  const ranked = [...a.assets].sort((p, q) => q.priority - p.priority);

  const figures: [string, string, boolean?][] = [
    ["Readiness", pct(a.readiness)],
    ["Need migration", String(a.summary.to_migrate)],
    ["Above risk target", String(a.summary.exposed), true],
    ["Broken today", String(a.summary.classically_broken), true],
    ["Quantum-safe", String(a.summary.quantum_safe)],
  ];

  return (
    <>
      <Masthead />
      <main>
        <section className="ledger-head">
          <div className="wrap">
            <div className="hero-meta" style={{ marginBottom: 0 }}>
              <span className="label">Ledger / {view.repo}</span>
              <span className="label">
                {view.source === "sample" ? "Sample data from the bundled acme-payments repository" : `Updated ${view.updatedAt?.replace("T", " ").slice(0, 16)} UTC`}
              </span>
            </div>
            <h1 className="ledger-title">{view.repo}</h1>
            <p className="muted" style={{ maxWidth: "42em", marginTop: 16 }}>
              Risk target {pct(a.target_exposure)}. Threat prior: median {Math.round(a.crqc_median_year)}, 5% chance
              by {Math.round(a.crqc_p05_year)}.{a.ref ? ` Scanned ref ${a.ref}.` : ""}
            </p>
          </div>
        </section>

        <div className="wrap">
          <div className="figures">
            {figures.map(([label, value, alert]) => (
              <div className="figure" key={label}>
                <div className="label">{label}</div>
                <div className={`figure-value${alert && value !== "0" ? " signal" : ""}`}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        <section className="section" style={{ borderTop: 0 }}>
          <div className="wrap">
            <div className="label" style={{ marginBottom: 14 }}>Assets by priority</div>
            <div className="table-scroll">
              <table className="assets">
                <thead>
                  <tr>
                    <th>Algorithm</th>
                    <th>System</th>
                    <th>Status</th>
                    <th>Protects</th>
                    <th>X / Y</th>
                    <th>P(exposed)</th>
                    <th>Start by</th>
                    <th>Replace with</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((asset) => (
                    <tr key={asset.id}>
                      <td>
                        <div className="alg">
                          {asset.algorithm_name}
                          {asset.parameter ? ` ${asset.parameter}` : ""}
                        </div>
                        <div className="where">
                          {asset.occurrences[0]?.path}:{asset.occurrences[0]?.line}
                          {asset.occurrences.length > 1 ? ` +${asset.occurrences.length - 1}` : ""}
                        </div>
                      </td>
                      <td>
                        {asset.system}
                        {asset.owner ? <div className="where">@{asset.owner}</div> : null}
                      </td>
                      <td>
                        <span className="status">
                          <span className={`swatch ${STATUS_SWATCH[asset.status] ?? ""}`} aria-hidden="true" />
                          {STATUS_LABEL[asset.status] ?? asset.status}
                        </span>
                      </td>
                      <td>{asset.usage}</td>
                      <td className="num">
                        {asset.status === "quantum-broken" ? `${asset.x_years} / ${asset.y_years}` : "—"}
                        {asset.needs_owner_input ? <div className="where">X not yet answered</div> : null}
                      </td>
                      <td className="num">
                        {asset.status === "quantum-broken" || asset.status === "classically-broken" ? (
                          <>
                            {pct(asset.exposure)}
                            <div className="bar" aria-hidden="true">
                              <span style={{ width: `${Math.round(asset.exposure * 100)}%` }} />
                            </div>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="num">{startBy(asset)}</td>
                      <td style={{ minWidth: 200 }}>{asset.replacement}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="section">
          <div className="wrap grid">
            <div style={{ gridColumn: "1 / -1" }} className="section-head">
              <div className="label">Waiting on owners</div>
              <div>
                {a.pending_questions.length === 0 ? (
                  <p className="muted" style={{ margin: 0 }}>Every owner has answered. All exposure figures use their numbers.</p>
                ) : (
                  <ul className="questions">
                    {a.pending_questions.map((q) => (
                      <li key={`${q.system}-${q.kind}`}>
                        <span className="label">{q.owner ? `@${q.owner}` : "owner unknown"}</span>
                        <span>{q.text.replace(/`/g, "")}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            <div style={{ gridColumn: "1 / -1" }} className="section-head">
              <div className="label">Trend</div>
              <Trend points={view.history} />
            </div>
          </div>
        </section>
      </main>
      <Colophon />
    </>
  );
}
