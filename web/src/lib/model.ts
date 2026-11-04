/**
 * Browser version of the Mosca exposure model, used by the interactive diagram.
 * The engine (core/src/mosca/risk.py) also integrates over migration-time uncertainty;
 * here Y is a point value so the diagram can respond instantly.
 */

export type Prior = { medianYear: number; earliestYear: number; spread: number };

export const DEFAULT_PRIOR: Prior = { medianYear: 2036, earliestYear: 2029, spread: 0.6 };

/** Abramowitz and Stegun 7.1.26, max error 1.5e-7. */
export function erf(x: number): number {
  const sign = x < 0 ? -1 : 1;
  const a = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * a);
  const y =
    1 -
    ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) *
      t *
      Math.exp(-a * a);
  return sign * y;
}

/** P(CRQC exists within `years` from `now`). */
export function crqcCdf(years: number, now: number, prior: Prior): number {
  const offset = Math.max(prior.earliestYear - now, 0);
  const t = years - offset;
  if (t <= 0) return 0;
  const mu = Math.log(Math.max(prior.medianYear - now - offset, 0.25));
  return 0.5 * (1 + erf((Math.log(t) - mu) / (prior.spread * Math.SQRT2)));
}

/** Mosca: P(X + Y > Z). */
export function exposure(x: number, y: number, now: number, prior: Prior): number {
  return crqcCdf(x + y, now, prior);
}

export function nowYear(d = new Date()): number {
  const start = Date.UTC(d.getUTCFullYear(), 0, 1);
  const end = Date.UTC(d.getUTCFullYear() + 1, 0, 1);
  return d.getUTCFullYear() + (d.getTime() - start) / (end - start);
}

export function pct(p: number): string {
  if (p >= 0.995) return "100%";
  if (p > 0 && p < 0.005) return "<1%";
  return `${Math.round(p * 100)}%`;
}
