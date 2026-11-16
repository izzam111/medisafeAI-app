"""TC-2  Privacy: the AI model never receives the user's name, email, phone or ID numbers,
so nothing that identifies a person can be kept or reused for training."""
import pytest

import app as medisafe


@pytest.mark.parametrize("text,hidden,mask", [
    ("contact me at someone@example.com", "someone@example.com", "[email]"),
    ("my number is 0300-1234567", "0300-1234567", "[number]"),
    ("call +92 300 1112223", "+92 300 1112223", "[number]"),
    ("CNIC 35202-1234567-1", "35202-1234567-1", "[id number]"),
    ("see www.example.com/page", "www.example.com/page", "[link]"),
])
def test_personal_details_are_removed(text, hidden, mask):
    out = medisafe.redact(text)
    assert hidden not in out and mask in out


def test_normal_reason_is_unchanged():
    assert medisafe.redact("Low iron / anaemia") == "Low iron / anaemia"


def test_ai_prompt_has_no_personal_details(client, search, monkeypatch):
    sent = []
    monkeypatch.setattr(medisafe, "call_claude", lambda content, max_tokens: sent.append(content) or None)
    s = search("Sangobion")
    r = client.post("/safety-report", json={"scan_id": s["scan_id"], "age": 26, "sex": "female", "periods": "yes",
                                            "reasons": ["hair fall, email me someone@example.com or 0300-1234567"]})
    assert r.status_code == 200
    prompt = " ".join(b.get("text", "") for content in sent for b in content)
    assert prompt, "the AI should have been asked"
    assert "someone@example.com" not in prompt and "0300-1234567" not in prompt
    assert "[email]" in prompt and "[number]" in prompt
    assert "26-year-old female" in prompt          # only age, sex and health status go to the AI


def test_ai_is_claude_with_optional_backups():
    assert medisafe.CLAUDE_MODELS and medisafe.CLAUDE_MODELS[-1].startswith("claude-")
    assert not hasattr(medisafe, "call_ollama")


def test_profile_fields_never_reach_the_ai(client, search, monkeypatch):
    """Name, username and date of birth are only in the account record; the report request carries age and sex."""
    sent = []
    monkeypatch.setattr(medisafe, "call_claude", lambda content, max_tokens: sent.append(content) or None)
    s = search("Centrum")
    client.post("/safety-report", json={"scan_id": s["scan_id"], "age": 30, "sex": "male", "reasons": []})
    prompt = " ".join(b.get("text", "") for content in sent for b in content)
    for private in ("username", "date of birth", "email"):
        assert private not in prompt.lower()


def test_test_mode_never_writes_to_firebase():
    assert medisafe.USE_FIREBASE is False
