import pytest

from app.payguard import finder
from app.payguard.finder import Answer, Page, confirm
from app.payguard.reader import Original

PAYEE = "株式会社ヨシキリ工業"
OFFICIAL = Page(url="https://www.yoshikiri-kogyo.example.jp/company", text="<h1>株式会社 ヨシキリ工業</h1> 代表 ０３－００００－３００１")


def mail(body: str) -> Original:
    return Original(name="m.email.txt", mime_type="text/plain", data=body.encode("utf-8"))


def test_parse_reads_json_inside_text():
    assert finder.parse('Here: {"phone": "03-0000-3001", "name": "ヨシキリ工業"}').phone == "03-0000-3001"
    assert finder.parse("not found") == Answer()
    assert finder.parse("{broken") == Answer()


def test_number_on_a_grounded_page_naming_the_payee_is_official():
    contact = confirm(Answer(phone="03-0000-3001"), PAYEE, [OFFICIAL], set(), "yoshikiri-mail.example")
    assert contact is not None and contact.source == "official" and contact.phone == "03-0000-3001"


@pytest.mark.parametrize(
    ("answer", "pages", "in_instruction", "sender", "why"),
    [
        (Answer(phone="03-0000-9999"), [OFFICIAL], set(), None, "number not on the page"),
        (Answer(phone="03-0000-3001"), [Page(url="https://dir.example.jp/", text="03-0000-3001 別の会社")], set(), None, "page does not name the payee"),
        (Answer(phone="03-0000-3001"), [OFFICIAL], {"0300003001"}, None, "the instruction gave this number"),
        (Answer(phone="03-0000-3001"), [OFFICIAL], set(), "yoshikiri-kogyo.example.jp", "page on the sender's domain"),
        (Answer(phone="12345"), [OFFICIAL], set(), None, "not a phone number"),
        (Answer(), [OFFICIAL], set(), None, "no answer"),
        (Answer(phone="03-0000-3001"), [], set(), None, "no grounded page"),
    ],
)
def test_unconfirmed_answers_are_not_used(answer, pages, in_instruction, sender, why):
    assert confirm(answer, PAYEE, pages, in_instruction, sender) is None, why


def test_numbers_in_the_instruction_are_collected():
    numbers = finder.instruction_numbers([mail("ご不明点は 03-0000-3001（担当直通）まで。口座 1234567")])
    assert "0300003001" in numbers


def test_official_contact_fetches_grounded_sources():
    asked = []

    def ask(payee):
        asked.append(payee)
        return Answer(phone="03-0000-3001"), ["https://grounding.example/1", "https://grounding.example/2"]

    def fetch(url):
        return OFFICIAL if url.endswith("/2") else None

    contact = finder.official_contact(PAYEE, [mail("請求書を送ります")], None, ask=ask, fetch=fetch)
    assert asked == [PAYEE] and contact is not None


def test_finder_runs_only_for_a_new_payee_with_nobody_to_call(monkeypatch):
    from app.payguard import demo
    from app.payguard.pipeline import check_node
    from tests.test_payguard_pipeline import faithful_reading

    calls = []
    monkeypatch.setattr(finder, "official_contact", lambda *a, **k: calls.append(a) or None)
    for pid in ("P-1001", "P-1002", "P-1003"):  # P-1003 is a new payee, but the CEO is in the ledger
        check_node(faithful_reading(pid).model_dump(), pid)
    assert calls == []

    s = demo.scenario_for("P-1003")
    new_payee = s.instruction.model_copy(update={"sender_name": "ウトウ商事 経理部 山本", "sender_address": "billing@utou-shoji.example", "channel": "email"})
    monkeypatch.setattr(demo, "scenario_for", lambda pid: s.model_copy(update={"instruction": new_payee}))
    reading = faithful_reading("P-1003").model_copy(update={"instruction": new_payee})
    state = check_node(reading.model_dump(), "P-1003").actions.state_delta
    assert len(calls) == 1 and calls[0][0] == "合同会社ルリカケ"
    assert state["check"]["verify_with"] is None  # nothing confirmed: approval is blocked
