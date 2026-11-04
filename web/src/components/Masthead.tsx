import Link from "next/link";

import { site } from "@/lib/site";

export function Masthead() {
  return (
    <header className="masthead">
      <div className="wrap masthead-inner">
        <Link href="/" className="wordmark" aria-label="Mosca home">
          <span className="wordmark-name">Mosca</span>
          <span className="wordmark-dot" aria-hidden="true" />
        </Link>
        <nav className="nav" aria-label="Primary">
          <Link href="/#method" className="nav-secondary">
            Method
          </Link>
          <Link href="/#room" className="nav-secondary">
            In the room
          </Link>
          <Link href="/ledger">Ledger</Link>
          <a href={site.repoUrl} className="button button-small" rel="noreferrer">
            Source
          </a>
        </nav>
      </div>
    </header>
  );
}
