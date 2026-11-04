# The exposure model

This document explains exactly how Mosca turns a scan into a number, so that anyone can check the reasoning and disagree with specific assumptions instead of the whole result.

## 1. Assets

A scan produces findings: one per place an algorithm is used. Findings are grouped into **assets**, one per `(system, algorithm)` pair. Systems come from `paths` globs in `mosca.toml`; unmatched files fall back to their top-level directory.

A bare key generation (`ec`, `rsa`) does not say what the key protects. When the same system uses that key family in exactly one specific way (for example ECDSA only), the key generation is merged into that asset. If the use is ambiguous the asset stays separate and is treated conservatively.

## 2. Status

Every algorithm in the catalog (`core/src/mosca/taxonomy.py`) has one status:

| Status | Meaning | Treatment |
|---|---|---|
| classically broken | Insecure without a quantum computer: MD5, SHA-1, DES, 3DES, RC4, RSA or DH under 2048 bits | Exposure 1.0, always ranked first |
| quantum-broken | Shor's algorithm recovers the key: RSA, ECDSA, ECDH, Ed25519, X25519, DH, DSA | Full Mosca model |
| quantum-weakened | Grover's algorithm halves security bits: AES-128 | Advisory only |
| hybrid | Classical plus post-quantum: X25519MLKEM768 | Counts as ready |
| quantum-safe | ML-KEM, ML-DSA, SLH-DSA, AES-256, SHA-384 and similar | Counts as ready |

Key size matters: RSA strength follows the NIST SP 800-57 comparable-strength table, so RSA-1024 is classified as classically broken.

## 3. X: how long the protection must last

The meaning of X depends on what the algorithm protects:

- **Confidentiality** (key exchange, encryption, unknown): X is the number of years the data must stay secret. Harvest-now-decrypt-later applies: traffic recorded today is exposed once a quantum computer exists.
- **Authenticity** (signatures): X is the number of years existing signatures must stay trusted. A signed firmware image in a terminal that stays in the field for twelve years has X = 12.

Sources, in order of precedence:

1. An owner's answer recorded in the ledger (`answered by ana`)
2. `shelf_life_years` or `signature_lifetime_years` on the system in `mosca.toml`
3. The system's `data_class`, mapped through `[data_classes]`
4. The default, flagged as an open question for the owner

## 4. Y: how long migration will take

```
Y = (base + 0.12 * log2(1 + occurrences) + 0.1 * log2(1 + files) + 0.25) * signature_factor
```

- `base` is the largest of the per-location efforts present: config 0.15, code 0.3, key 0.3, dependency 0.4, certificate 0.6 (years)
- the logarithms grow effort with spread, with diminishing returns
- 0.25 years covers testing, staged rollout and coordination
- `signature_factor` is 1.5 for signatures, because every verifier has to upgrade as well

This is a heuristic and is labelled as one. Set `migration_years` on a system to override it.

In the probability calculation Y is uncertain: `Y ~ Triangular(0.7y, y, 2.0y)`. The skew reflects that migrations run late far more often than early.

## 5. Z: when a quantum computer arrives

```
Z = max(earliest_year - now, 0) + LogNormal(mu, spread)
mu = ln(median_year - now - offset)
```

The default prior (`median_year = 2036`, `earliest_year = 2029`, `spread = 0.6`) is a starting point, not a forecast. Every organisation should set its own. Mosca prints the median and the 5% year with every report so the assumption is never hidden.

## 6. Exposure

```
P(exposed) = P(X + Y > Z)
```

It is estimated with 20,000 Monte Carlo samples, seeded by the asset id and its inputs, so identical inputs always give identical output.

Two derived figures:

- **Start by**: `now + Z_q - X - Y`, where `Z_q` is the quantile of Z at the target exposure (default 5%). If that year has passed, the asset is **overdue**.
- **Priority**: `100 * P(exposed) * criticality * confidence`. Criticality comes from `mosca.toml`; confidence is the strongest detector confidence for the asset (a call site is stronger evidence than a dependency).

## 7. Readiness

Readiness is the share of occurrences that are already quantum-safe, hybrid or only weakened. It is deliberately simple, so a team can explain it in one sentence.

## 8. Diff

`mosca diff` assesses two trees with the same policy and reports:

- assets resolved and assets introduced
- per-asset exposure changes
- total expected exposure (`sum of P(exposed) * occurrences` over assets that need migration), and its relative reduction
