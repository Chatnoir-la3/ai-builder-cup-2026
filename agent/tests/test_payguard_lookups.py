from datetime import date

import pytest

from app.payguard import lookups
from app.payguard.models import Instruction
from app.payguard.reader import Original

TODAY = date(2026, 10, 10)


def text(body: str) -> Original:
    return Original(name="mail.email.txt", mime_type="text/plain", data=body.encode("utf-8"))


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code, self._body = status, body

    def json(self) -> dict:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, threats: dict[str, list[str]]):
        self.threats, self.asked = threats, []

    def get(self, url, params, timeout):
        self.asked.append(params["uri"])
        hit = self.threats.get(params["uri"])
        return FakeResponse(200, {"threat": {"threatTypes": hit}} if hit else {})


def test_links_come_from_text_originals_only():
    found = lookups.links(
        [
            text("請求書はこちら（https://portal.shigino-bussan.example/inv?id=7）。\nhttp://a.example/x, http://a.example/x"),
            Original(name="chat.png", mime_type="image/png", data=b"https://in-an-image.example"),
        ]
    )
    assert found == ["https://portal.shigino-bussan.example/inv?id=7", "http://a.example/x"]


def test_senders_come_from_the_header_of_each_email():
    found = lookups.senders(
        [
            text("From: 佐藤 一郎 <Sato.Ichiro@freemail.example>\nTo: suzuki@miori-koumuten.example\n\nFrom: not-a-header@body.example"),
            text("To: a@b.example\nFrom: billing@utou-shoji.example\n\n請求書を送ります。"),
            Original(name="chat.png", mime_type="image/png", data=b"From: in-an-image@c.example"),
        ]
    )
    assert found == ["sato.ichiro@freemail.example", "billing@utou-shoji.example"]


def test_web_risk_reports_listed_links_and_skips_reserved_names():
    session = FakeSession({"http://bad.test-phish.net/login": ["SOCIAL_ENGINEERING"]})
    urls = ["http://bad.test-phish.net/login", "https://ok.example.org/", "https://invoice.example/x"]
    assert lookups.listed(urls, session=lambda: session) == ["http://bad.test-phish.net/login"]
    assert session.asked == ["http://bad.test-phish.net/login", "https://ok.example.org/"]


def test_no_links_means_no_web_risk_call():
    def fail():
        raise AssertionError("should not be called")

    assert lookups.listed(["https://invoice.example/x"], session=fail) == []


def test_rdap_registration_date():
    def get(url, timeout, headers):
        assert url == "https://rdap.org/domain/utou-shoji.jp"
        return FakeResponse(200, {"events": [{"eventAction": "last changed", "eventDate": "2026-10-09T00:00:00Z"},
                                             {"eventAction": "registration", "eventDate": "2026-10-05T03:00:00Z"}]})

    assert lookups.registered_on("utou-shoji.jp", get=get) == date(2026, 10, 5)


@pytest.mark.parametrize("domain", ["tsubakuro-kenzai.example", "x.test", "example"])
def test_reserved_domains_are_not_looked_up(domain):
    def get(*a, **k):
        raise AssertionError("should not be called")

    assert lookups.registered_on(domain, get=get) is None


def test_fetch_records_failures_as_unknown(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network")

    monkeypatch.setattr(lookups, "listed", boom)
    monkeypatch.setattr(lookups, "registered_on", boom)
    ins = Instruction(channel="email", sender_address="billing@utou-shoji.jp")
    result = lookups.fetch(ins, [text("https://a.net/")], TODAY)
    assert result.listed_urls == [] and result.domain_age_days is None
    assert result.failed == ["rdap", "web_risk"]


def test_fetch_gives_domain_age(monkeypatch):
    monkeypatch.setattr(lookups, "listed", lambda urls: [])
    monkeypatch.setattr(lookups, "registered_on", lambda d: date(2026, 10, 5))
    ins = Instruction(channel="email", sender_address="billing@Utou-Shoji.jp")
    assert lookups.fetch(ins, [], TODAY).domain_age_days == 5


def test_every_link_is_found_not_just_the_first_few():
    body = " ".join(f"https://site{i}.example.org/p" for i in range(12))
    assert len(lookups.links([text(body)])) == 12


def test_too_many_links_fail_the_lookup_rather_than_check_some(monkeypatch):
    def fail():
        raise AssertionError("should not be called")

    urls = [f"https://site{i}.example.org/p" for i in range(lookups.MAX_LINKS + 1)]
    with pytest.raises(lookups.TooManyLinks):
        lookups.listed(urls, session=fail)
    # Reserved names do not count towards the limit.
    assert lookups.listed([*urls[:2], *(f"https://x{i}.example/" for i in range(20))], session=lambda: FakeSession({})) == []

    monkeypatch.setattr(lookups, "registered_on", lambda d: None)
    monkeypatch.setattr(lookups, "_session", fail)
    result = lookups.fetch(Instruction(channel="email"), [text(" ".join(urls))], TODAY)
    assert result.failed == ["web_risk"]
