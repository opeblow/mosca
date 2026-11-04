import { pct } from "@/lib/model";
import type { Asset } from "@/lib/ledger";

type Turn = {
  who: string;
  role: string;
  agent?: boolean;
  time: string;
  body: React.ReactNode;
};

const M = ({ children }: { children: React.ReactNode }) => <span className="mention">{children}</span>;

export function Transcript({ assets, toMigrate }: { assets: Asset[]; toMigrate: number }) {
  const top = assets.filter((a) => a.priority > 0).slice(0, 5);

  const turns: Turn[] = [
    {
      who: "user",
      role: "Security lead",
      time: "06:50",
      body: (
        <p>
          <M>@Mosca</M> scan
        </p>
      ),
    },
    {
      who: "mosca",
      role: "Custom agent",
      agent: true,
      time: "06:50",
      body: (
        <>
          <p>
            Scanned <code>main</code>: {assets.length} cryptographic assets, {toMigrate} need migration. The CBOM is
            attached to this room as the document <code>CBOM acme-payments main</code>, and the assessment is in the
            ledger. Highest priority:
          </p>
          <div className="table-scroll">
            <table className="mini-table">
              <thead>
                <tr>
                  <th>System</th>
                  <th>Algorithm</th>
                  <th>P(exposed)</th>
                  <th>Start by</th>
                </tr>
              </thead>
              <tbody>
                {top.map((a) => (
                  <tr key={a.id}>
                    <td>{a.system}</td>
                    <td>
                      {a.algorithm_name}
                      {a.parameter ? ` ${a.parameter}` : ""}
                    </td>
                    <td>{a.status === "classically-broken" ? "broken now" : pct(a.exposure)}</td>
                    <td>{a.status === "classically-broken" ? "now" : a.years_late > 0 ? "overdue" : a.deadline_year}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            <strong>Question for dev, owner of auth:</strong> how many years must signatures from{" "}
            <code>auth</code> stay trusted? Until you answer I assume the default.
          </p>
        </>
      ),
    },
    {
      who: "user",
      role: "Owner, auth",
      time: "06:51",
      body: (
        <p>
          <M>@Mosca</M> 10 years
        </p>
      ),
    },
    {
      who: "mosca",
      role: "Custom agent",
      agent: true,
      time: "06:51",
      body: (
        <p>
          Recorded in the ledger: <code>auth</code> signatures must stay trusted for 10 years (answered by user).
          auth ECDSA P-256 and auth RSA signature: 1% to <strong>70%</strong>, start by 2028 to overdue.
        </p>
      ),
    },
    {
      who: "user",
      role: "Security lead",
      time: "07:35",
      body: (
        <p>
          <M>@claude-code.migrator</M> Fix the edge TLS config in <code>infra/nginx/api.conf</code>: offer
          X25519MLKEM768 first with X25519 as fallback, and remove 3DES from the ciphers. Work on a new branch
          pq/edge-hybrid-tls and commit.
        </p>
      ),
    },
    {
      who: "claude-code.migrator",
      role: "Migrator role, held by Claude Code",
      agent: true,
      time: "07:35",
      body: (
        <p>
          Committed on <code>pq/edge-hybrid-tls</code>. <code>api.conf:9</code>:{" "}
          <code>ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1</code>, hybrid first with classical fallback.{" "}
          <code>api.conf:10</code>: removed DES-CBC3-SHA. The edge nginx must be built against OpenSSL 3.5 or newer.
        </p>
      ),
    },
    {
      who: "user",
      role: "Security lead",
      time: "07:39",
      body: (
        <p>
          <M>@Mosca</M> rescan pq/edge-hybrid-tls
        </p>
      ),
    },
    {
      who: "mosca",
      role: "Custom agent",
      agent: true,
      time: "07:39",
      body: (
        <p>
          Rescanned <code>pq/edge-hybrid-tls</code> against <code>main</code>: exposure down 6%.{" "}
          <code>edge/3des</code> resolved. Readiness 13% to 16%.
        </p>
      ),
    },
    {
      who: "opencode.reviewer",
      role: "Reviewer role, held by OpenCode",
      agent: true,
      time: "07:45",
      body: (
        <p>
          Approve. <code>api.conf:9</code>: X25519MLKEM768 is the correct group name for OpenSSL 3.5+, and the
          fallback keeps non-PQ clients connecting. <code>api.conf:10</code>: dropping 3DES is correct; only
          3DES-only clients are lost.
        </p>
      ),
    },
    {
      who: "user",
      role: "Security lead",
      time: "07:46",
      body: <p>Approved. pq/edge-hybrid-tls is good to merge.</p>,
    },
    {
      who: "claude-code.migrator",
      role: "Migrator role, held by Claude Code",
      agent: true,
      time: "07:46",
      body: <p>I haven&apos;t merged: the migrator role says a person merges. One commit ahead of main, tree clean.</p>,
    },
  ];

  return (
    <div className="transcript" role="log" aria-label="Session in the q-day Switch room">
      {turns.map((t, i) => (
        <div className="turn" data-agent={t.agent ? "true" : "false"} key={i}>
          <div className="turn-who">
            {t.agent ? "@" : ""}
            {t.who}
            <small>{t.role}</small>
          </div>
          <div className="turn-body">{t.body}</div>
          <div className="turn-time">{t.time}</div>
        </div>
      ))}
    </div>
  );
}
