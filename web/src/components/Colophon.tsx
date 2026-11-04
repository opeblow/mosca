import Link from "next/link";

import { site } from "@/lib/site";

export function Colophon() {
  return (
    <footer className="colophon">
      <div className="wrap">
        <div className="colophon-grid">
          <div>
            <div className="label">Colophon</div>
            <p style={{ maxWidth: "36em" }}>
              Named after Michele Mosca, whose inequality X + Y &gt; Z is the standard way to reason about quantum
              risk. Set in Instrument Serif and IBM Plex. Open source under the Apache 2.0 license.
            </p>
          </div>
          <div>
            <div className="label">Product</div>
            <ul>
              <li>
                <Link href="/#method">Method</Link>
              </li>
              <li>
                <Link href="/#room">In the room</Link>
              </li>
              <li>
                <Link href="/ledger">Ledger</Link>
              </li>
            </ul>
          </div>
          <div>
            <div className="label">Source</div>
            <ul>
              <li>
                <a href={site.repoUrl} rel="noreferrer">
                  Repository
                </a>
              </li>
              <li>
                <a href="https://cyclonedx.org/capabilities/cbom/" rel="noreferrer">
                  CycloneDX CBOM
                </a>
              </li>
              <li>
                <a href="https://csrc.nist.gov/projects/post-quantum-cryptography" rel="noreferrer">
                  NIST PQC
                </a>
              </li>
            </ul>
          </div>
        </div>
        <p className="colophon-mark" aria-hidden="true">
          X + Y &gt; Z
        </p>
      </div>
    </footer>
  );
}
