"use client";

import { useId, useMemo, useState } from "react";

import { DEFAULT_PRIOR, crqcCdf, exposure, nowYear, pct } from "@/lib/model";

const W = 760;
const H = 340;
const PAD = { top: 28, right: 16, bottom: 40, left: 16 };
const SPAN = 30; // years shown
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

const sx = (years: number) => PAD.left + (Math.min(years, SPAN) / SPAN) * PLOT_W;
const sy = (prob: number) => PAD.top + (1 - prob) * PLOT_H;

type Props = { initialX?: number; initialY?: number };

export function MoscaDiagram({ initialX = 10, initialY = 2 }: Props) {
  const [x, setX] = useState(initialX);
  const [y, setY] = useState(initialY);
  const [median, setMedian] = useState(DEFAULT_PRIOR.medianYear);
  const ids = { x: useId(), y: useId(), z: useId() };

  // Whole years keep the server render and the browser render identical.
  const now = useMemo(() => Math.floor(nowYear()), []);
  const prior = useMemo(
    () => ({ ...DEFAULT_PRIOR, medianYear: median, earliestYear: Math.min(DEFAULT_PRIOR.earliestYear, median - 1) }),
    [median],
  );
  const p = exposure(x, y, now, prior);
  const level = p > 0.25 ? "high" : p < 0.05 ? "low" : "mid";

  const curve = useMemo(() => {
    const pts: string[] = [];
    for (let i = 0; i <= 240; i++) {
      const t = (i / 240) * SPAN;
      pts.push(`${sx(t).toFixed(1)},${sy(crqcCdf(t, now, prior)).toFixed(1)}`);
    }
    return pts;
  }, [prior, now]);

  const area = `M${sx(0)},${sy(0)} L${curve.join(" L")} L${sx(SPAN)},${sy(0)} Z`;
  const startYear = Math.floor(now);
  const ticks = Array.from({ length: SPAN / 5 + 1 }, (_, i) => i * 5);
  const barY = sy(0) - 22;
  const hit = x + y;

  return (
    <div className="diagram">
      <div className="controls">
        <div className="readout">
          <div className="label">Probability this data is exposed</div>
          <div className="readout-value" data-level={level} aria-live="polite">
            {pct(p)}
          </div>
          <p className="muted" style={{ margin: "8px 0 0", fontSize: 14 }}>
            {p > 0.25
              ? "Traffic recorded today is likely to be read by someone else."
              : p < 0.05
                ? "Inside the 5% risk target. Keep migrating on schedule."
                : "Above the 5% target. Migration should be scheduled now."}
          </p>
        </div>

        <div className="control">
          <label htmlFor={ids.x}>
            <span className="label">X / data must stay secret</span>
            <output htmlFor={ids.x}>{x} yr</output>
          </label>
          <input id={ids.x} type="range" min={0} max={30} step={1} value={x}
            onChange={(e) => setX(Number(e.target.value))} />
        </div>
        <div className="control">
          <label htmlFor={ids.y}>
            <span className="label">Y / migration takes</span>
            <output htmlFor={ids.y}>{y} yr</output>
          </label>
          <input id={ids.y} type="range" min={0} max={10} step={0.5} value={y}
            onChange={(e) => setY(Number(e.target.value))} />
        </div>
        <div className="control">
          <label htmlFor={ids.z}>
            <span className="label">Z / median quantum year</span>
            <output htmlFor={ids.z}>{median}</output>
          </label>
          <input id={ids.z} type="range" min={2030} max={2050} step={1} value={median}
            onChange={(e) => setMedian(Number(e.target.value))} />
        </div>
      </div>

      <figure style={{ margin: 0 }}>
        <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img"
          aria-label={`Exposure chart. Data secret for ${x} years plus ${y} years of migration reaches ${startYear + Math.round(hit)}; probability of a quantum computer by then is ${pct(p)}.`}>
          <defs>
            <pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="5" fill="var(--paper)" />
              <line x1="0" y1="0" x2="0" y2="5" stroke="var(--ink)" strokeWidth="1.4" />
            </pattern>
          </defs>

          {[0.25, 0.5, 0.75, 1].map((g) => (
            <g key={g}>
              <line className="grid-line" x1={PAD.left} x2={W - PAD.right} y1={sy(g)} y2={sy(g)} />
              <text x={W - PAD.right} y={sy(g) - 6} textAnchor="end">{Math.round(g * 100)}%</text>
            </g>
          ))}

          <path d={area} fill="var(--signal-soft)" />
          <polyline className="cdf" points={curve.join(" ")} />
          <text x={sx(SPAN) - 4} y={sy(crqcCdf(SPAN, now, prior)) + 18} textAnchor="end" fill="var(--signal)">
            P(quantum computer exists)
          </text>

          <rect className="bar-x" x={sx(0)} y={barY} width={Math.max(sx(x) - sx(0), 0)} height={14} />
          <rect className="bar-y" x={sx(x)} y={barY} width={Math.max(sx(hit) - sx(x), 0)} height={14} />
          {x > 1.5 && (
            <text x={sx(0) + 6} y={barY - 6}>X</text>
          )}
          {y > 1 && hit < SPAN && (
            <text x={sx(x) + 6} y={barY - 6}>Y</text>
          )}

          {hit <= SPAN && (
            <>
              <line className="marker" x1={sx(hit)} x2={sx(hit)} y1={sy(0)} y2={sy(p)} />
              <line className="marker" x1={sx(hit)} x2={W - PAD.right} y1={sy(p)} y2={sy(p)} />
              <circle cx={sx(hit)} cy={sy(p)} r={4.5} fill="var(--signal)" />
            </>
          )}

          <line className="axis" x1={PAD.left} x2={W - PAD.right} y1={sy(0)} y2={sy(0)} />
          {ticks.map((t) => (
            <g key={t}>
              <line className="tick" x1={sx(t)} x2={sx(t)} y1={sy(0)} y2={sy(0) + 6} />
              <text x={sx(t)} y={sy(0) + 22} textAnchor={t === 0 ? "start" : t === SPAN ? "end" : "middle"}>
                {startYear + t}
              </text>
            </g>
          ))}
        </svg>
        <figcaption className="label" style={{ marginTop: 12 }}>
          Fig. 1. The red curve is the chance a code-breaking quantum computer exists by each year. The bar is
          how long your data must stay secret (X) plus how long migration takes (Y). Where the bar ends, read
          the curve.
        </figcaption>
      </figure>
    </div>
  );
}
