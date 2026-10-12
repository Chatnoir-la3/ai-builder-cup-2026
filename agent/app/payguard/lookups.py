"""Facts from outside the ledger, fetched by code before the check.

- Links in the instruction, against Google Web Risk (`uris.search`).
- The age of the sender's email domain, from its RDAP registration event.

No model is involved. A lookup with nothing to say stays unknown, and the rules then say nothing about
it. A lookup that fails is recorded in `failed`: Web Risk can block a payment, so its failure is a finding;
a missing domain age only leaves the ledger checks to decide. Reserved names such as `.example` are never
looked up.
"""

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import google.auth
import requests
from google.auth.transport.requests import AuthorizedSession

from .models import Instruction, Lookups
from .reader import Original
from .rules import _email_domain

TIMEOUT = 5
MAX_LINKS = 5
WEB_RISK = "https://webrisk.googleapis.com/v1/uris:search"
THREATS = ("MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE")
RDAP = "https://rdap.org/domain/{}"
RESERVED = (".example", ".test", ".invalid", ".localhost")

_LINK = re.compile(r"https?://[^\s<>\"'()（）「」、。]+")

logger = logging.getLogger("payguard.lookups")


def links(originals: list[Original]) -> list[str]:
    found: list[str] = []
    for o in originals:
        if o.is_text:
            for url in _LINK.findall(o.text):
                url = url.rstrip(".,;:")
                if url not in found:
                    found.append(url)
    return found[:MAX_LINKS]


def _host(url: str) -> str:
    return re.sub(r"^https?://", "", url).split("/", 1)[0].split(":", 1)[0].lower()


def reserved(domain: str) -> bool:
    return domain == "example" or domain.endswith(RESERVED)


def _session() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(credentials)


def listed(urls: list[str], session: Callable[[], AuthorizedSession] = _session) -> list[str]:
    urls = [u for u in urls if not reserved(_host(u))]
    if not urls:
        return []
    s = session()
    out = []
    for url in urls:
        res = s.get(WEB_RISK, params={"uri": url, "threatTypes": list(THREATS)}, timeout=TIMEOUT)
        res.raise_for_status()
        if res.json().get("threat"):
            out.append(url)
    return out


def registered_on(domain: str, get: Callable[..., requests.Response] = requests.get) -> date | None:
    if reserved(domain):
        return None
    res = get(RDAP.format(domain), timeout=TIMEOUT, headers={"Accept": "application/rdap+json"})
    if res.status_code == 404:
        return None
    res.raise_for_status()
    for event in res.json().get("events", []):
        if event.get("eventAction") == "registration":
            return datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00")).date()
    return None


def _quietly(name: str, fn: Callable[[], object], default: object, failed: list[str]) -> object:
    try:
        return fn()
    except Exception as e:  # recorded, not raised: the check still runs on the ledger
        logger.warning('{"message": "lookup failed", "lookup": "%s", "error": "%s"}', name, type(e).__name__)
        failed.append(name)
        return default


def fetch(ins: Instruction, originals: list[Original], today: date) -> Lookups:
    domain = _email_domain(ins.sender_address)
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        urls = pool.submit(_quietly, "web_risk", lambda: listed(links(originals)), [], failed)
        reg = pool.submit(_quietly, "rdap", lambda: registered_on(domain) if domain else None, None, failed)
        listed_urls, registered = urls.result(), reg.result()
    return Lookups(
        listed_urls=listed_urls,
        domain_age_days=(today - registered).days if isinstance(registered, date) else None,
        failed=sorted(failed),
    )
