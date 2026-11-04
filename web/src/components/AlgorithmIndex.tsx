type Column = {
  swatch: string;
  label: string;
  title: string;
  text: string;
  rows: [string, string][];
};

const COLUMNS: Column[] = [
  {
    swatch: "swatch-broken",
    label: "Shor's algorithm",
    title: "Quantum-broken",
    text: "A quantum computer recovers the private key. Encrypted traffic recorded today becomes readable.",
    rows: [
      ["RSA", "ML-KEM / ML-DSA"],
      ["ECDSA, Ed25519", "ML-DSA-65"],
      ["ECDH, X25519", "X25519MLKEM768"],
      ["Diffie-Hellman", "X25519MLKEM768"],
      ["DSA", "ML-DSA-65"],
    ],
  },
  {
    swatch: "swatch-classical",
    label: "No quantum needed",
    title: "Broken today",
    text: "Already insecure on ordinary computers. Mosca puts these first, ahead of any quantum risk.",
    rows: [
      ["MD5", "SHA-384"],
      ["SHA-1", "SHA-384"],
      ["DES, 3DES", "AES-256-GCM"],
      ["RC4", "ChaCha20-Poly1305"],
      ["RSA under 2048", "ML-KEM-768"],
    ],
  },
  {
    swatch: "swatch-weak",
    label: "Grover's algorithm",
    title: "Weakened",
    text: "Security bits roughly halve. Still usable, but long-lived data deserves 256-bit keys.",
    rows: [
      ["AES-128", "AES-256"],
      ["AES, size unknown", "confirm 256-bit"],
    ],
  },
  {
    swatch: "swatch-safe",
    label: "FIPS 203 / 204 / 205",
    title: "Quantum-safe",
    text: "Post-quantum standards and hybrids. Mosca counts these toward readiness.",
    rows: [
      ["ML-KEM-768", "FIPS 203"],
      ["ML-DSA-65", "FIPS 204"],
      ["SLH-DSA", "FIPS 205"],
      ["X25519MLKEM768", "hybrid"],
      ["AES-256, SHA-384", "symmetric"],
    ],
  },
];

export function AlgorithmIndex() {
  return (
    <div className="index">
      {COLUMNS.map((c) => (
        <div className="index-col" key={c.title}>
          <div className="label">
            <span className={`swatch ${c.swatch}`} aria-hidden="true" />
            {c.label}
          </div>
          <h3>{c.title}</h3>
          <p>{c.text}</p>
          <ul className="index-list">
            {c.rows.map(([found, fix]) => (
              <li key={found}>
                <span>{found}</span>
                <span>{fix}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
