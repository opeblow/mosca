import Link from "next/link";

import { AlgorithmIndex } from "@/components/AlgorithmIndex";
import { Colophon } from "@/components/Colophon";
import { Deadlines } from "@/components/Deadlines";
import { Masthead } from "@/components/Masthead";
import { MoscaDiagram } from "@/components/MoscaDiagram";
import { Transcript } from "@/components/Transcript";
import { sampleView } from "@/lib/ledger";
import { site } from "@/lib/site";

const STEPS = [
  {
    n: "01",
    title: "Inventory",
    text: "Mosca reads code in Python, TypeScript, Go and Java, plus TLS and SSH configs, certificates, keys and dependency manifests. The result is a CycloneDX 1.6 cryptographic bill of materials.",
  },
  {
    n: "02",
    title: "Ask the owners",
    text: "Only the people who own the data know how long it must stay secret. Mosca asks each owner in the team chat and records the answer, with their name, in an append-only ledger.",
  },
  {
    n: "03",
    title: "Rank by exposure",
    text: "Each asset gets P(X + Y > Z): the chance its data is still sensitive when a code-breaking quantum computer arrives. Broken-today algorithms like MD5 and 3DES go first.",
  },
  {
    n: "04",
    title: "Migrate and verify",
    text: "Coding agents draft the post-quantum change, a second agent reviews it, a person approves. Mosca rescans the branch and reports exactly how much exposure went away.",
  },
];

const STANDARDS: [string, string][] = [
  ["CycloneDX 1.6", "Cryptographic bill of materials"],
  ["FIPS 203", "ML-KEM key encapsulation"],
  ["FIPS 204", "ML-DSA signatures"],
  ["FIPS 205", "SLH-DSA hash-based signatures"],
  ["NIST IR 8547", "Transition timeline (draft)"],
];

export default function Home() {
  const sample = sampleView().assessment;

  return (
    <>
      <Masthead />
      <main>
        <section className="hero">
          <div className="wrap">
            <div className="hero-meta reveal">
              <span className="label">Mosca / quantum-readiness for engineering teams</span>
              <span className="label">Open source / Apache 2.0</span>
            </div>
            <div className="grid">
              <h1 className="hero-title reveal reveal-2">
                The data you encrypt today has a <em>decryption date.</em>
              </h1>
              <div className="hero-body reveal reveal-3">
                <div>
                  <p className="lede">{site.description} Then it helps your team fix them, in the chat you already use.</p>
                  <div className="actions">
                    <a className="button" href="#install">
                      Install the scanner
                    </a>
                    <Link className="button button-ghost" href="/ledger">
                      Open the sample ledger
                    </Link>
                  </div>
                </div>
                <Deadlines />
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="method">
          <div className="wrap grid">
            <div className="section-head">
              <div className="label">01 / Method</div>
              <div>
                <h2 className="section-title">One inequality decides which systems are already too late.</h2>
                <p className="section-intro">
                  Adversaries record encrypted traffic now and wait for a quantum computer to read it. Michele Mosca
                  framed the question every security team now has to answer. Mosca, the tool, answers it for each
                  algorithm in each system you run.
                </p>
              </div>
            </div>
            <div className="inequality">
              <p className="formula" aria-label="X plus Y is greater than Z">
                X<span className="op"> + </span>Y<span className="gt"> &gt; </span>Z
              </p>
              <dl className="definitions">
                <div>
                  <dt>X</dt>
                  <dd>
                    <strong>Shelf life.</strong> How long the data must stay secret, or how long a signature must stay
                    trusted. Answered by the owner, in chat.
                  </dd>
                </div>
                <div>
                  <dt>Y</dt>
                  <dd>
                    <strong>Migration time.</strong> Estimated from where the algorithm lives: one config line, a
                    library call in forty files, or a certificate chain other companies verify.
                  </dd>
                </div>
                <div>
                  <dt>Z</dt>
                  <dd>
                    <strong>Threat timeline.</strong> A probability distribution over the year a code-breaking quantum
                    computer exists. You set it; Mosca never pretends to know.
                  </dd>
                </div>
              </dl>
            </div>
            <MoscaDiagram />
          </div>
        </section>

        <section className="section" id="room">
          <div className="wrap grid">
            <div className="section-head">
              <div className="label">02 / In the room</div>
              <div>
                <h2 className="section-title">A migration is a team sport. So it happens where the team talks.</h2>
                <p className="section-intro">
                  Mosca joins your team chat through Switch as an agent with its own identity. Coding agents take
                  roles in the same room: one writes the change, another reviews it. People answer the questions
                  only they can answer, and approve every change.
                </p>
              </div>
            </div>
            <div className="label" style={{ gridColumn: "1 / -1", marginBottom: 14 }}>
              Illustrative session / numbers from a real scan of the sample repository
            </div>
            <Transcript assets={sample.assets} toMigrate={sample.summary.to_migrate} />
          </div>
        </section>

        <section className="section">
          <div className="wrap grid">
            <div className="section-head">
              <div className="label">03 / Process</div>
              <h2 className="section-title">From unknown to accounted for.</h2>
            </div>
            <div className="steps">
              {STEPS.map((s) => (
                <div className="step" key={s.n}>
                  <div className="label">{s.n}</div>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section">
          <div className="wrap grid">
            <div className="section-head">
              <div className="label">04 / Reference</div>
              <div>
                <h2 className="section-title">What Mosca looks for, and what replaces it.</h2>
              </div>
            </div>
            <AlgorithmIndex />
          </div>
        </section>

        <section className="section" id="install">
          <div className="wrap grid">
            <div className="install">
              <div>
                <div className="label">05 / Install</div>
                <h2 className="section-title" style={{ marginTop: 16 }}>
                  Run it on your own code in two minutes.
                </h2>
                <p className="section-intro">
                  The scanner has no runtime dependencies beyond Python 3.11. Nothing leaves your machine. Add{" "}
                  <code>--fail-above</code> to stop a build when exposure crosses your threshold.
                </p>
              </div>
              <pre className="terminal" aria-label="Install commands">
                <span className="c"># install</span>
                {"\n"}
                <span className="p">$ </span>pip install ./core
                {"\n\n"}
                <span className="c"># cryptographic bill of materials</span>
                {"\n"}
                <span className="p">$ </span>mosca scan . -o cbom.json
                {"\n\n"}
                <span className="c"># rank by quantum exposure</span>
                {"\n"}
                <span className="p">$ </span>mosca assess .
                {"\n\n"}
                <span className="c"># gate CI on a risk threshold</span>
                {"\n"}
                <span className="p">$ </span>mosca assess . --fail-above 0.25
                {"\n\n"}
                <span className="c"># compare a migration branch</span>
                {"\n"}
                <span className="p">$ </span>mosca diff ../main ../pq-migration
              </pre>
            </div>
          </div>
        </section>

        <section className="section">
          <div className="wrap grid">
            <div className="section-head">
              <div className="label">06 / Standards</div>
              <h2 className="section-title">Built on public standards, not opinions.</h2>
            </div>
            <div className="standards">
              {STANDARDS.map(([name, text]) => (
                <div className="standard" key={name}>
                  <strong>{name}</strong>
                  <span>{text}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
      <Colophon />
    </>
  );
}
