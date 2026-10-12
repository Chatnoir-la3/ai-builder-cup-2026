"""Calls Gemini with Google Search for real. Run with RUN_LIVE_GEMINI=1 and application default credentials."""

import os

import pytest

from app.payguard import finder

pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE_GEMINI") != "1", reason="set RUN_LIVE_GEMINI=1 to call Gemini")


def test_fictional_company_has_no_official_number():
    assert finder.official_contact("ウトウ商事株式会社", [], "utou-shoji.example") is None
