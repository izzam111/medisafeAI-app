"""
Shared setup for the MediSafe AI test suite (no GUI: every test calls the backend directly).

Run from the backend folder:
    python -m pytest tests -v

Test mode (MEDISAFE_TESTING=1) switches Firebase and the AI off, so tests never write to the real
database and never send data to a model. The camera and OCR are replaced by fixed label text, so every
run gives the same result; everything else (datasets, rules engine, trained food model) is the real code.
"""
import os
import sys

os.environ["MEDISAFE_TESTING"] = "1"
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import pytest
from fastapi.testclient import TestClient

import app as medisafe          # backend/app.py
import personal_check

# The people every safety test is run for
PEOPLE = {
    "man_30":           dict(age=30, sex="male"),
    "man_70":           dict(age=70, sex="male"),
    "boy_8":            dict(age=8, sex="male"),
    "girl_6":           dict(age=6, sex="female"),
    "girl_8_periods":   dict(age=8, sex="female", periods="yes"),
    "girl_15_periods":  dict(age=15, sex="female", periods="yes"),
    "woman_26_periods": dict(age=26, sex="female", periods="yes"),
    "pregnant_28":      dict(age=28, sex="female", periods="yes", pregnant=True),
    "breastfeeding_30": dict(age=30, sex="female", periods="yes", breastfeeding=True),
    "woman_55_menopause": dict(age=55, sex="female", periods="no"),
}


@pytest.fixture(scope="session")
def client():
    return TestClient(medisafe.app)


@pytest.fixture
def scan(client, monkeypatch):
    """scan([("Centrum", 60), ("MEN", 40)]) → the /scan-supplement result for a photo whose OCR reads those lines.
    Each line is (text, letter height in pixels): big text = the brand name."""
    def run(lines, is_supplement=True):
        boxes = [([[0, 0], [10 * len(t), 0], [10 * len(t), h], [0, h]], t, 0.9) for t, h in lines]
        monkeypatch.setattr(medisafe.reader, "readtext", lambda *a, **k: boxes)
        monkeypatch.setattr(medisafe, "photo_is_supplement",
                            lambda image: (True, "") if is_supplement else (False, "looks like a food plate"))
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new("RGB", (600, 800), "white").save(buf, "JPEG")
        r = client.post("/scan-supplement", files=[("files", ("pack.jpg", buf.getvalue(), "image/jpeg"))])
        assert r.status_code == 200, r.text
        return r.json()
    return run


@pytest.fixture
def search(client):
    def run(name):
        r = client.post("/search-product", json={"name": name})
        return r.json() if r.status_code == 200 else None
    return run


@pytest.fixture
def report(client):
    """report(scan_result, "woman_26_periods", ["Heavy periods"]) → (http status, safety report)"""
    def run(scan_result, person, reasons=()):
        r = client.post("/safety-report", json={"scan_id": scan_result["scan_id"], "reasons": list(reasons), **PEOPLE[person]})
        return r.status_code, r.json()
    return run


def colour(report_json) -> str:
    """The colour the app shows: green = Safe, orange = Take with care, red = Not safe / Not right for your reason."""
    s = report_json["report"]["is_safe_to_take"]
    tone = s.get("tone") or {"Safe": "ok", "Use with caution": "caution", "Not safe": "stop"}[s["verdict"]]
    return {"ok": "green", "caution": "orange", "stop": "red"}[tone]
