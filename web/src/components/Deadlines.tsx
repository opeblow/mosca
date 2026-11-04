"use client";

import { useEffect, useState } from "react";

type Deadline = { label: string; date: string; note: string };

const DEADLINES: Deadline[] = [
  {
    label: "RSA and ECC deprecated",
    date: "2030-01-01",
    note: "NIST IR 8547 (draft) transition timeline, 112-bit security",
  },
  {
    label: "RSA and ECC disallowed",
    date: "2035-01-01",
    note: "NIST IR 8547 (draft), all quantum-vulnerable public-key algorithms",
  },
  {
    label: "Median quantum estimate",
    date: "2036-01-01",
    note: "Mosca default prior. Set your own in mosca.toml",
  },
];

const DAY = 86_400_000;

function daysUntil(iso: string, now: number): number {
  return Math.max(0, Math.ceil((Date.parse(`${iso}T00:00:00Z`) - now) / DAY));
}

export function Deadlines() {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="deadlines" role="list">
      {DEADLINES.map((d) => (
        <div className="deadline" role="listitem" key={d.date}>
          <div className="label">{d.label}</div>
          <div className="deadline-value" aria-live="off">
            {now === null ? "—" : daysUntil(d.date, now).toLocaleString("en-US")}
            <span className="label" style={{ marginLeft: 10 }}>
              days
            </span>
          </div>
          <p className="deadline-note">{d.note}</p>
        </div>
      ))}
    </div>
  );
}
