from app.agent import _plugins, app, root_agent


def test_root_agent_is_the_workflow():
    from app.payguard.pipeline import pipeline

    assert root_agent is pipeline
    assert app.root_agent is root_agent


def test_plugins_are_off_without_env(monkeypatch):
    monkeypatch.delenv("MODEL_ARMOR_TEMPLATE", raising=False)
    monkeypatch.delenv("AUDIT_DATASET", raising=False)
    assert _plugins() == []


def test_plugins_follow_env(monkeypatch):
    monkeypatch.setenv("MODEL_ARMOR_TEMPLATE", "projects/p/locations/asia-southeast1/templates/t")
    monkeypatch.setenv("AUDIT_DATASET", "agent_audit")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    plugins = _plugins()
    names = sorted(type(p).__name__ for p in plugins)
    assert names == ["BigQueryAgentAnalyticsPlugin", "ModelArmorPlugin"]

    audit = next(p for p in plugins if type(p).__name__ == "BigQueryAgentAnalyticsPlugin")
    assert audit.config.log_multi_modal_content is False
    assert audit.config.log_session_metadata is False
    assert audit.config.event_denylist == ["STATE_DELTA"]
    assert audit.config.content_formatter("口座：普通 8812345", "LLM_REQUEST") == "[REDACTED]"


def test_health():
    from fastapi.testclient import TestClient

    from main import app as api

    assert TestClient(api).get("/health").json() == {"status": "ok"}
