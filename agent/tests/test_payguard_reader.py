from app.payguard import DATA_DIR, Instruction
from app.payguard.reader import Evidence, Original, Reading, build_content, ground, reader_agent

ORIGINALS = DATA_DIR / "originals"
EMAIL = Original.from_path(ORIGINALS / "account-change.email.txt")
CHAT = Original.from_path(ORIGINALS / "ceo-chat.line.png")


def reading(instruction: dict, evidence: list[dict]) -> Reading:
    return Reading(instruction=Instruction.model_validate(instruction), evidence=[Evidence(**e) for e in evidence])


def test_originals_are_typed_by_extension():
    assert EMAIL.is_text and EMAIL.mime_type == "text/plain"
    assert not CHAT.is_text and CHAT.mime_type == "image/png"


def test_build_content_labels_each_source():
    content = build_content([EMAIL, CHAT])
    assert content.parts[0].text == "[source 1] account-change.email.txt"
    assert "8812345" in content.parts[1].text
    assert content.parts[2].text == "[source 2] ceo-chat.line.png"
    assert content.parts[3].inline_data.mime_type == "image/png"


def test_supported_values_are_kept():
    r = reading(
        {"channel": "email", "account_number": "8812345", "amount": 486000, "account_holder": "ヤマダ タロウ"},
        [
            {"field": "account_number", "source": 1, "quote": "口座：普通 8812345"},
            {"field": "amount", "source": 1, "quote": "ご請求金額：486,000円（税込）"},
            {"field": "account_holder", "source": 1, "quote": "口座名義：ヤマダ タロウ", "box_2d": [1, 2, 3, 4]},
        ],
    )
    g = ground(r, [EMAIL])
    assert g.unverified == []
    assert g.instruction.account_number == "8812345"
    assert all(ev.box_2d is None for ev in g.evidence)  # boxes only make sense on images


def test_value_not_in_the_original_is_cleared():
    # The quote is plausible, but the email never says it: a misread or an injected answer.
    r = reading(
        {"channel": "email", "account_number": "1234567"},
        [{"field": "account_number", "source": 1, "quote": "口座：普通 1234567"}],
    )
    g = ground(r, [EMAIL])
    assert g.unverified == ["account_number"]
    assert g.instruction.account_number is None
    assert g.evidence == []


def test_value_without_evidence_is_cleared():
    g = ground(reading({"channel": "email", "amount": 486000}, []), [EMAIL])
    assert g.unverified == ["amount"]
    assert g.instruction.amount is None


def test_quote_must_support_the_value():
    r = reading(
        {"channel": "email", "amount": 999000},
        [{"field": "amount", "source": 1, "quote": "ご請求金額：486,000円（税込）"}],
    )
    assert ground(r, [EMAIL]).unverified == ["amount"]


def test_unknown_source_is_ignored():
    r = reading({"channel": "line", "amount": 3000000}, [{"field": "amount", "source": 5, "quote": "3,000,000円"}])
    assert ground(r, [CHAT]).unverified == ["amount"]


def test_image_evidence_keeps_only_valid_boxes():
    r = reading(
        {"channel": "line", "amount": 3000000, "account_number": "5503921"},
        [
            {"field": "amount", "source": 1, "quote": "3,000,000円", "box_2d": [600, 70, 630, 300]},
            {"field": "account_number", "source": 1, "quote": "普通 5503921", "box_2d": [630, 70, 600, 300]},
        ],
    )
    g = ground(r, [CHAT])
    assert g.unverified == []
    boxes = {ev.field: ev.box_2d for ev in g.evidence}
    assert boxes == {"amount": [600, 70, 630, 300], "account_number": None}


def test_reader_agent_writes_structured_reading_to_state():
    assert reader_agent.output_schema is Reading
    assert reader_agent.output_key == "reading"
    assert reader_agent.include_contents == "none"
    assert "{" not in reader_agent.instruction  # ADK treats braces as state placeholders
