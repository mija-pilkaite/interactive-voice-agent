import json
import re
import pytest
from spike_cli.verification_agent import VerificationAgent


    
class DummyChoice:
    def __init__(self, content):
        self.message = type("X", (), {"content": content})

class DummyResp:
    def __init__(self, content):
        self.choices = [DummyChoice(content)]

class DummyClient:
    def __init__(self, response):
        self._response = response
    @property
    def chat(self):
        return self
    @property
    def completions(self):
        return self
    def create(self, model, messages, stream=False):
        return self._response

@pytest.fixture
def config(tmp_path, monkeypatch):
    data = {
        "agent": {
            "system_prompt_template": "You are a bot for {patient_name}",
            "model": "gpt-4"
        },
        "patient": {
            "member_id": "ABC123",
            "patient_name": "Testy",
            "date_of_birth": "Jan 1 2000"
        }
    }
    path = tmp_path / "cfg.yml"
    path.write_text(json.dumps(data))
    return data
@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    
def test_process_updates_state(monkeypatch, config):
    state = {"member_id":"ABC123","patient_name":"Testy","date_of_birth":"Jan 1 2000","insurance_active_to":"2025-12-31"}
    assistant_msg = f"Here it is\n```json\n{json.dumps(state)}\n```"
    dummy_response = DummyResp(assistant_msg)

    agent = VerificationAgent(config)
    monkeypatch.setattr(agent, "client", DummyClient(dummy_response))

    reply, new_state = agent.process("hello")
    assert "Here it is" in reply
    assert new_state["insurance_active_to"] == "2025-12-31"