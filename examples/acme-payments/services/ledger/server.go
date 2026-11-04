package main

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"log"
	"net/http"
)

func tlsConfig() *tls.Config {
	return &tls.Config{
		MinVersion:       tls.VersionTLS12,
		CurvePreferences: []tls.CurveID{tls.X25519, tls.CurveP256},
	}
}

// exportKey wraps ledger exports for the reconciliation partner.
func exportKey() *rsa.PrivateKey {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		log.Fatal(err)
	}
	return key
}

func main() {
	srv := &http.Server{Addr: ":8443", TLSConfig: tlsConfig()}
	_ = exportKey()
	log.Fatal(srv.ListenAndServeTLS("ledger.crt", "ledger.key"))
}
