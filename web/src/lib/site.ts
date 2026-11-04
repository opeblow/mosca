/** Site-wide settings. Set NEXT_PUBLIC_REPO_URL when the repository is public. */
export const site = {
  name: "Mosca",
  tagline: "Quantum-readiness for engineering teams",
  repoUrl: process.env.NEXT_PUBLIC_REPO_URL ?? "https://github.com/opeblow/mosca",
  description:
    "Mosca finds every cryptographic algorithm in your codebase, asks the people who own the data how long it must stay secret, and shows which systems a quantum computer will expose first.",
};
