from mosca.model import Kind
from mosca.scanner import configs, deps, lexical, pem, python_ast
from mosca.taxonomy import Status, Usage


def algs(findings):
    return sorted(f.algorithm for f in findings)


# ---- Python -----------------------------------------------------------------------

def test_python_resolves_aliased_imports():
    src = (
        "from cryptography.hazmat.primitives.asymmetric import rsa as r\n"
        "k = r.generate_private_key(public_exponent=65537, key_size=3072)\n"
    )
    [f] = list(python_ast.detect("a.py", src))
    assert f.algorithm == "rsa" and f.key_bits == 3072 and f.line == 2
    assert f.classical_bits == 128


def test_python_short_rsa_key_is_classically_broken():
    src = "import rsa\npub, priv = rsa.newkeys(1024)\n"
    [f] = list(python_ast.detect("a.py", src))
    assert f.status is Status.CLASSICAL


def test_python_hashlib_and_new():
    src = "import hashlib\nhashlib.md5(b'x')\nhashlib.new('sha1')\nhashlib.sha256()\n"
    assert algs(python_ast.detect("a.py", src)) == ["md5", "sha1", "sha256"]


def test_python_jwt_algorithms():
    src = "import jwt\njwt.encode({}, k, algorithm='ES256')\njwt.decode(t, k, algorithms=['RS256', 'HS256'])\n"
    assert algs(python_ast.detect("a.py", src)) == ["ecdsa", "hmac-sha256", "rsa-signature"]


def test_python_ec_curve_and_ed25519():
    src = (
        "from cryptography.hazmat.primitives.asymmetric import ec, ed25519\n"
        "ec.generate_private_key(ec.SECP384R1())\n"
        "ed25519.Ed25519PrivateKey.generate()\n"
    )
    found = list(python_ast.detect("a.py", src))
    assert [(f.algorithm, f.curve) for f in found] == [("ec", "P-384"), ("ed25519", None)]


def test_python_ignores_strings_and_comments():
    src = "# rsa.generate_private_key(key_size=1024)\nx = 'hashlib.md5()'\n"
    assert list(python_ast.detect("a.py", src)) == []


def test_python_syntax_error_is_not_fatal():
    assert list(python_ast.detect("a.py", "def (:\n")) == []


def test_python_aes_key_length():
    src = (
        "import os\nfrom cryptography.hazmat.primitives.ciphers import algorithms\n"
        "algorithms.AES(os.urandom(32))\nalgorithms.AES(os.urandom(16))\nalgorithms.AES(k)\n"
    )
    assert algs(python_ast.detect("a.py", src)) == ["aes", "aes-128", "aes-256"]


# ---- Lexical (JS/TS/Go/Java) -------------------------------------------------------

def test_strip_comments_keeps_lines_and_strings():
    src = 'a // createHash("md5")\n/* x\ny */ b = "// not a comment"\n'
    out = lexical.strip_comments(src)
    assert out.count("\n") == src.count("\n")
    assert "md5" not in out and "// not a comment" in out


def test_typescript_node_crypto():
    src = (
        'const k = generateKeyPairSync("rsa", { modulusLength: 2048 });\n'
        '// createHash("md5")\n'
        'createHash("sha1");\n'
        'createCipheriv("aes-128-gcm", key, iv);\n'
    )
    found = list(lexical.detect("x.ts", src))
    assert algs(found) == ["aes-128", "rsa", "rsa", "sha1"]
    assert any(f.key_bits == 2048 for f in found)


def test_go_stdlib_including_hybrid():
    src = (
        "key, _ := rsa.GenerateKey(rand.Reader, 4096)\n"
        "c := []tls.CurveID{tls.X25519MLKEM768, tls.X25519, tls.CurveP384}\n"
        "h := md5.Sum(b)\n"
    )
    found = {f.algorithm: f for f in lexical.detect("main.go", src)}
    assert found["rsa"].key_bits == 4096
    assert found["x25519mlkem768"].status is Status.HYBRID
    assert found["ecdh"].curve == "P-384"
    assert "x25519" in found and "md5" in found


def test_java_jca():
    src = (
        'KeyPairGenerator g = KeyPairGenerator.getInstance("RSA"); g.initialize(2048);\n'
        'Signature.getInstance("SHA256withECDSA");\n'
        'MessageDigest.getInstance("MD5");\n'
        'Cipher.getInstance("DESede/CBC/PKCS5Padding");\n'
    )
    assert algs(lexical.detect("A.java", src)) == ["3des", "ecdsa", "md5", "rsa", "rsa"]


def test_lexical_respects_language():
    assert list(lexical.detect("a.go", 'createHash("md5")')) == []


# ---- Configuration -----------------------------------------------------------------

def test_nginx_groups_and_ciphers():
    src = "ssl_ecdh_curve X25519MLKEM768:prime256v1;\nssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:DES-CBC3-SHA;\n"
    found = list(configs.detect("api.conf", src))
    by = {f.algorithm for f in found}
    assert {"x25519mlkem768", "ecdh", "3des", "aes-256"} <= by
    assert "dh" not in by  # DHE inside ECDHE must not count


def test_sshd_config():
    src = "KexAlgorithms mlkem768x25519-sha256,curve25519-sha256\nHostKeyAlgorithms ssh-rsa\n"
    assert algs(configs.detect("sshd_config", src)) == ["rsa-signature", "x25519", "x25519mlkem768"]


def test_config_comments_ignored():
    assert list(configs.detect("sshd_config", "# HostKeyAlgorithms ssh-rsa\n")) == []


def test_env_jwt_algorithm():
    [f] = list(configs.detect(".env", "JWT_ALGORITHM=RS256\n"))
    assert f.algorithm == "rsa-signature" and f.kind is Kind.CONFIG


# ---- Certificates and keys -----------------------------------------------------------

def test_certificate_is_parsed(sample_repo):
    text = (sample_repo / "infra/certs/api.pem").read_text()
    [f] = list(pem.detect("api.pem", text))
    assert f.algorithm == "rsa-signature" and f.key_bits == 2048
    assert f.kind is Kind.CERTIFICATE and f.usage is Usage.SIGNATURE
    assert "expires" in f.note


def test_ssh_public_keys():
    text = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl a@b\n"
    [f] = list(pem.detect("id_ed25519.pub", text))
    assert f.algorithm == "ed25519"


# ---- Dependencies --------------------------------------------------------------------

def test_package_json():
    text = '{"dependencies": {"node-forge": "1", "react": "18"}, "devDependencies": {"jsonwebtoken": "9"}}'
    assert algs(deps.detect("package.json", text)) == ["rsa", "rsa-signature"]


def test_go_mod_prefix_match():
    text = "module x\n\nrequire (\n\tgithub.com/golang-jwt/jwt/v5 v5.2.0\n\tgithub.com/cloudflare/circl v1.4.0\n)\n"
    assert algs(deps.detect("go.mod", text)) == ["ml-kem-768", "rsa-signature"]


def test_dependency_findings_are_low_confidence():
    [f] = list(deps.detect("requirements.txt", "pycryptodome==3.20\nrequests\n"))
    assert f.confidence < 0.6 and f.kind is Kind.DEPENDENCY
