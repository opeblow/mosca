import { createHash, generateKeyPairSync } from "node:crypto";
import jwt from "jsonwebtoken";

const { privateKey, publicKey } = generateKeyPairSync("ec", {
  namedCurve: "prime256v1",
});

export function issueSession(userId: string): string {
  return jwt.sign({ sub: userId }, privateKey, { algorithm: "ES256", expiresIn: "1h" });
}

export function verifySession(token: string) {
  return jwt.verify(token, publicKey, { algorithms: ["ES256"] });
}

export function deviceFingerprint(userAgent: string, ip: string): string {
  return createHash("sha1").update(`${userAgent}|${ip}`).digest("hex");
}
