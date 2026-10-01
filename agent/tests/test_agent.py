from app.agent import _plugins, app, root_agent


def test_root_agent_is_configured():
    assert root_agent.name == "root_agent"
    assert root_agent.model
    assert app.root_agent is root_agent


def test_plugins_are_off_without_env(monkeypatch):
    monkeypatch.delenv("MODEL_ARMOR_TEMPLATE", raising=False)
    monkeypatch.delenv("AUDIT_DATASET", raising=False)
    assert _plugins() == []


def test_plugins_follow_env(monkeypatch):
    monkeypatch.setenv("MODEL_ARMOR_TEMPLATE", "projects/p/locations/asia-southeast1/templates/t")
    monkeypatch.setenv("AUDIT_DATASET", "agent_audit")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    names = sorted(type(p).__name__ for p in _plugins())
    assert names == ["BigQueryAgentAnalyticsPlugin", "ModelArmorPlugin"]


def test_health():
    from fastapi.testclient import TestClient

    from main import app as api

    assert TestClient(api).get("/health").json() == {"status": "ok"}
