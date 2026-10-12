"""Finder: Gemini with Google Search looks up a new payee's official phone number; code checks it.

It runs only when the ledger has nobody to call. It is given the payee's name only, never the
originals, so the instruction cannot steer it. Its answer is used only if code confirms it on a page
that Google Search grounded the answer in: the page shows the number and the payee's name, it is not on
the sender's domain, and the number does not appear in the instruction (a fraudster's own number).
Otherwise there is no independent number to call, and the rules block approval.
"""

import json
import logging
import os
import re
import unicodedata
from collections.abc import Callable
from urllib.parse import urlparse

import requests
from pydantic import BaseModel

from .models import Contact
from .reader import Original

TIMEOUT = 8
MAX_SOURCES = 4
MAX_BYTES = 1_000_000
_PHONE = re.compile(r"^0\d{9,10}$")
_LEGAL = re.compile(r"株式会社|有限会社|合同会社|合資会社|合名会社|\(株\)|（株）|\s")

logger = logging.getLogger("payguard.finder")

FINDER_INSTRUCTION = """\
Find the official main phone number of the Japanese company named in the user message, using Google Search.
Use only the company's own website or a public directory (such as a chamber of commerce or a government
listing). Answer with JSON only: {"phone": "<number as written on the page>", "name": "<company name on
the page>"}. If you cannot find it on such a page, answer {"phone": null, "name": null}.
"""


class Answer(BaseModel):
    phone: str | None = None
    name: str | None = None


class Page(BaseModel):
    url: str
    text: str


def digits(s: str) -> str:
    return re.sub(r"\D", "", unicodedata.normalize("NFKC", s))


def _core_name(name: str) -> str:
    return _LEGAL.sub("", unicodedata.normalize("NFKC", name))


def parse(text: str) -> Answer:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return Answer()
    try:
        return Answer.model_validate(json.loads(m.group(0)))
    except (ValueError, TypeError):
        return Answer()


def confirm(
    answer: Answer, payee: str, pages: list[Page], instruction_numbers: set[str], sender_domain: str | None
) -> Contact | None:
    number = digits(answer.phone or "")
    if not _PHONE.match(number) or number in instruction_numbers:
        return None
    core = _core_name(payee)
    for page in pages:
        host = (urlparse(page.url).hostname or "").lower()
        if sender_domain and (host == sender_domain or host.endswith("." + sender_domain)):
            continue
        text = unicodedata.normalize("NFKC", page.text)
        if number in digits(text) and core and core in _LEGAL.sub("", text):
            return Contact(name=payee, phone=answer.phone.strip(), source="official")
    return None


def instruction_numbers(originals: list[Original]) -> set[str]:
    found: set[str] = set()
    for o in originals:
        if o.is_text:
            found |= {digits(m) for m in re.findall(r"[0-9０-９][0-9０-９\-‐－ ()（）]{8,}[0-9０-９]", o.text)}
    return found


def _fetch(url: str) -> Page | None:
    """Fetch a grounded source: https only, HTML only, at most MAX_BYTES."""
    if not url.startswith("https://"):
        return None
    with requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "payguard-finder"}, stream=True) as res:
        if res.status_code != 200 or not res.url.startswith("https://") or "html" not in res.headers.get("content-type", ""):
            return None
        body = res.raw.read(MAX_BYTES, decode_content=True)
    text = re.sub(r"<[^>]+>", " ", body.decode(res.encoding or "utf-8", errors="replace"))
    return Page(url=res.url, text=text)


def _ask(payee: str) -> tuple[Answer, list[str]]:
    from google import genai
    from google.genai import types

    client = genai.Client()
    res = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        contents=payee,
        config=types.GenerateContentConfig(
            system_instruction=FINDER_INSTRUCTION,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        ),
    )
    meta = res.candidates[0].grounding_metadata if res.candidates else None
    sources = [c.web.uri for c in (meta.grounding_chunks or []) if c.web and c.web.uri] if meta else []
    return parse(res.text or ""), sources[:MAX_SOURCES]


def official_contact(
    payee: str,
    originals: list[Original],
    sender_domain: str | None,
    ask: Callable[[str], tuple[Answer, list[str]]] = _ask,
    fetch: Callable[[str], Page | None] = _fetch,
) -> Contact | None:
    answer, sources = ask(payee)
    pages = []
    for url in sources:
        try:
            page = fetch(url)
        except requests.RequestException:
            page = None
        if page:
            pages.append(page)
    contact = confirm(answer, payee, pages, instruction_numbers(originals), sender_domain)
    logger.info(
        json.dumps({"message": "finder", "answered": answer.phone is not None, "sources": len(sources), "confirmed": contact is not None})
    )
    return contact
