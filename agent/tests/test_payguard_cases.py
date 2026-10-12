"""The evaluation set must give exactly the findings and tiers it expects (see app/payguard/evalset.py)."""

import pytest

from app.payguard import evalset
from app.payguard.evalset import CASES, Case, check_with_lookups
from app.payguard.rules import check


def test_cases_cover_the_simulation():
    assert len({c.id for c in CASES}) == len(CASES) == 28
    assert sum(c.kind == "attack" for c in CASES) == 18


@pytest.mark.parametrize("c", CASES, ids=lambda c: c.id)
def test_ledger_alone(c: Case):
    result = check(c.book, c.payment, c.ins)
    assert {f.code for f in result.findings} == c.ledger
    assert (result.verify_with is not None) is c.ledger_number


@pytest.mark.parametrize("c", CASES, ids=lambda c: c.id)
def test_with_lookups(c: Case):
    result = check_with_lookups(c)
    assert {f.code for f in result.findings} == c.ledger | c.added
    assert result.tier == c.tier


def test_summary():
    s = evalset.summary(evalset.results())
    assert s.as_expected == 28
    assert (s.attacks, s.attacks_stopped, s.genuine_blocked) == (18, 18, 0)
    # Without the official number lookup, genuine new suppliers (L04, L10) have nobody to call and are blocked.
    assert s.genuine_blocked_by_ledger == 2


def test_detail_explains_each_finding():
    d = evalset.detail("A12")
    assert d.tier == "block" and [r.code for r in d.reasons] == ["NEW_PAYEE", "URL_LISTED"]
    assert all(r.text and "{" not in r.text for r in d.reasons)
