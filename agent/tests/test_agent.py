from app.agent import root_agent


def test_root_agent_is_configured():
    assert root_agent.name == "root_agent"
    assert root_agent.model


def test_health():
    from fastapi.testclient import TestClient

    from main import app

    assert TestClient(app).get("/health").json() == {"status": "ok"}
