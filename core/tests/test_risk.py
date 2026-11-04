import shutil
from datetime import date

import pytest

from mosca import diff, policy, risk
from mosca.model import Finding, Kind, ScanResult
from mosca.policy import CrqcPrior, Policy, System
from mosca.scanner import scan

TODAY = date(2026, 11, 4)


def finding(alg="rsa", path="svc/a.py", **kw):
    return Finding(algorithm=alg, path=path, line=1, kind=kw.pop("kind", Kind.CODE), detector="t", **kw)


def assess(findings, pol=None):
    return risk.assess(ScanResult(root=".", findings=findings), pol or Policy(), today=TODAY, samples=4000)


def test_exposure_is_deterministic():
    a = assess([finding()])
    b = assess([finding()])
    assert a.assets[0].exposure == b.assets[0].exposure


def test_exposure_grows_with_shelf_life():
    def p(years):
        pol = Policy(systems=[System("svc", ("svc/**",), shelf_life_years=years)])
        return assess([finding()], pol).assets[0].exposure

    values = [p(y) for y in (0, 3, 7, 15, 30)]
    assert values == sorted(values)
    assert values[0] < 0.05 and values[-1] > 0.95


def test_later_crqc_reduces_exposure():
    early = Policy(crqc=CrqcPrior(median_year=2032, earliest_year=2028))
    late = Policy(crqc=CrqcPrior(median_year=2045, earliest_year=2035))
    assert assess([finding()], early).assets[0].exposure > assess([finding()], late).assets[0].exposure


def test_classically_broken_is_always_top_priority():
    out = assess([finding("md5"), finding("rsa")])
    assert out.assets[0].algorithm == "md5" and out.assets[0].exposure == 1.0


def test_safe_algorithms_carry_no_priority():
    out = assess([finding("ml-kem-768"), finding("x25519mlkem768"), finding("aes-256")])
    assert all(a.priority == 0 for a in out.assets)
    assert out.readiness == 1.0


def test_signature_uses_signature_lifetime():
    pol = Policy(systems=[System("svc", ("svc/**",), shelf_life_years=30, signature_lifetime_years=1)])
    out = assess([finding("ecdsa")], pol)
    assert out.assets[0].x_years == 1


def test_owner_answer_overrides_default_and_clears_question():
    before = assess([finding()])
    assert [q.system for q in before.pending_questions()] == ["svc"]
    pol = Policy(answers={"svc": {"shelf_life_years": 25, "answered_by": "ana"}})
    after = assess([finding()], pol)
    assert after.pending_questions() == []
    assert after.assets[0].x_source == "answered by ana"
    assert after.assets[0].exposure > before.assets[0].exposure


def test_findings_merge_into_one_asset_per_system_and_algorithm():
    out = assess([finding(key_bits=2048), finding(usage=None, path="svc/b.py")])
    [asset] = out.assets
    assert asset.parameter == "2048" and len(asset.occurrences) == 2


def test_invalid_prior_rejected():
    with pytest.raises(ValueError):
        CrqcPrior(median_year=2030, earliest_year=2031)


def test_glob_matching():
    pol = policy.from_dict({"systems": [{"name": "pay", "paths": ["services/payments/**"]}]})
    assert pol.system_for("services/payments/a/b.py").name == "pay"
    assert pol.system_for("services/other/x.py").name == "services"
    assert pol.system_for("README.md").name == "(root)"


def test_sample_repo_end_to_end(sample_repo):
    pol = policy.load(sample_repo)
    out = risk.assess(scan(sample_repo), pol, today=TODAY, samples=4000)
    systems = {a.system for a in out.assets}
    assert {"payments", "auth", "ledger", "firmware", "edge", "analytics"} <= systems
    top = out.assets[0]
    assert top.status == "classically-broken"
    firmware = next(a for a in out.assets if a.system == "firmware" and a.algorithm == "ecdsa")
    assert firmware.x_years == 12  # from mosca.toml signature_lifetime_years


def test_migration_branch_reduces_exposure(sample_repo, tmp_path):
    after_root = tmp_path / "after"
    shutil.copytree(sample_repo, after_root)
    conf = after_root / "infra/nginx/api.conf"
    conf.write_text(conf.read_text().replace("X25519:prime256v1", "X25519MLKEM768")
                    .replace(":DES-CBC3-SHA", ""))
    pol = policy.load(sample_repo)
    before = risk.assess(scan(sample_repo), pol, today=TODAY, samples=4000)
    after = risk.assess(scan(after_root), pol, today=TODAY, samples=4000)
    delta = diff.compare(before, after)
    assert delta.reduction > 0
    assert "edge/3des" in delta.removed
    assert "exposure down" in diff.chat(delta)
