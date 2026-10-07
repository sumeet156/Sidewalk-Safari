import httpx
import pytest

from app.providers.ollama import MISSION_RESPONSE_SCHEMA, OllamaProvider


class FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, str]:
        return {"response": '{"missions":[]}'}


def test_ollama_uses_constrained_schema_timeout_and_keeps_model_loaded(monkeypatch) -> None:
    request: dict = {}

    def fake_post(url: str, *, json: dict, timeout: httpx.Timeout) -> FakeResponse:
        request.update(url=url, json=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("app.providers.ollama.httpx.post", fake_post)
    provider = OllamaProvider(timeout_seconds=240)
    assert provider.generate("Build a safari") == '{"missions":[]}'
    assert request["json"]["format"] == MISSION_RESPONSE_SCHEMA
    assert request["json"]["keep_alive"] == "10m"
    assert request["timeout"].read == 240
    assert request["timeout"].connect == 10
    assert request["json"]["options"]["num_predict"] == 384
    mission_schema = request["json"]["format"]["properties"]["missions"]["items"]
    assert mission_schema["properties"]["text"]["maxLength"] == 160
    assert mission_schema["properties"]["est_minutes"]["maximum"] == 30


def test_ollama_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        OllamaProvider(timeout_seconds=0)


def test_ollama_env_timeout_must_be_positive(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(ValueError, match="OLLAMA_TIMEOUT_SECONDS"):
        from app.providers.ollama import create_provider

        create_provider()


def test_ollama_retries_once_after_request_timeout(monkeypatch) -> None:
    calls = 0

    def fake_post(url: str, *, json: dict, timeout: httpx.Timeout) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("slow local response")
        return FakeResponse()

    monkeypatch.setattr("app.providers.ollama.httpx.post", fake_post)
    provider = OllamaProvider(timeout_seconds=240)
    assert provider.generate("Build a safari") == '{"missions":[]}'
    assert calls == 2
