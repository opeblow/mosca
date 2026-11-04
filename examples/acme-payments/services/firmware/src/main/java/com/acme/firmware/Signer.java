package com.acme.firmware;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;

/** Signs firmware images for card terminals. Terminals stay in the field for 10+ years. */
public final class Signer {
    private final KeyPair keys;

    public Signer() throws Exception {
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("EC");
        kpg.initialize(new ECGenParameterSpec("secp256r1"));
        this.keys = kpg.generateKeyPair();
    }

    public byte[] sign(byte[] image) throws Exception {
        Signature sig = Signature.getInstance("SHA256withECDSA");
        sig.initSign(keys.getPrivate());
        sig.update(image);
        return sig.sign();
    }
}
