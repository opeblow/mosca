from datetime import date

from mosca import risk
from mosca.model import Finding, Kind, ScanResult
from mosca.policy import Policy
from mosca.taxonomy import Usage


def f(alg, usage=None, curve=None):
    return Finding(algorithm=alg, path="svc/x.java", line=1, kind=Kind.CODE, detector="t",
                   usage=usage, curve=curve)


def run(*findings):
    return risk.assess(ScanResult(".", list(findings)), Policy(), today=date(2026, 11, 4), samples=1000)


def test_ec_key_merges_into_its_only_use():
    out = run(f("ec", curve="P-256"), f("ecdsa"))
    [asset] = out.assets
    assert asset.algorithm == "ecdsa" and asset.parameter == "P-256" and asset.usage == "signature"


def test_ec_key_stays_separate_when_ambiguous():
    out = run(f("ec"), f("ecdsa"), f("ecdh"))
    assert sorted(a.algorithm for a in out.assets) == ["ec", "ecdh", "ecdsa"]


def test_rsa_with_encryption_usage_is_not_merged_into_signatures():
    out = run(f("rsa", usage=Usage.ENCRYPTION), f("rsa-signature"))
    assert sorted(a.algorithm for a in out.assets) == ["rsa", "rsa-signature"]
