"""TC-5  'Why do you take it?': only reasons the supplement is really used for, and a wrong reason turns the report red."""
from conftest import colour


def reasons_for(client, s, age, sex, periods=None):
    return client.post("/suggest-reasons", json={"scan_id": s["scan_id"], "name": s["product"]["name"], "age": age,
                                                 "sex": sex, "periods": periods}).json()["reasons"]


def test_iron_supplement_only_offers_iron_reasons(client, search):
    options = reasons_for(client, search("Sangobion"), 26, "female", "yes")
    assert "Low iron / anaemia" in options
    assert not any(word in r.lower() for r in options for word in ("vitamin d", "stress", "sleep", "bone"))


def test_women_only_reasons_are_hidden_for_men(client, search):
    options = reasons_for(client, search("Sangobion"), 30, "male")
    assert "Heavy periods" not in options and "Pregnancy" not in options


def test_no_pregnancy_reasons_after_menopause(client, search):
    options = reasons_for(client, search("Femibion"), 60, "female", "no")
    assert "Pregnancy" not in options


def test_calcium_offers_bone_reasons(client, search):
    options = reasons_for(client, search("Caltrate"), 60, "female", "no")
    assert "Bone health" in options and "After menopause" in options


def test_herbal_offers_its_own_uses(client, search):
    options = reasons_for(client, search("Ashwagandha"), 30, "male")
    assert "Stress and anxiety" in options


def test_right_reason_helps(search, report):
    _, body = report(search("Sangobion"), "woman_26_periods", ["Heavy periods"])
    assert colour(body) == "green"
    assert body["report"]["purpose_check"]["results"][0]["result"] == "helps"


def test_illness_reason_wont_help(search, report):
    _, body = report(search("Centrum"), "man_30", ["Seizures"])
    assert colour(body) == "red"
    assert body["report"]["is_safe_to_take"]["title"] == "Not right for your reason"


def test_unrelated_reason_is_not_proven(search, report):
    _, body = report(search("Sangobion"), "woman_26_periods", ["Stress and anxiety"])
    assert colour(body) == "red"


def test_iron_has_no_everyday_option(client, search):
    options = reasons_for(client, search("Sangobion"), 26, "female", "yes")
    assert not any("everyday" in r.lower() or "general" in r.lower() for r in options)


def test_multivitamin_offers_everyday_nutrition(client, search):
    options = reasons_for(client, search("Centrum"), 30, "male")
    assert "Everyday nutrition (no specific problem)" in options


def test_oligomenorrhea_counts_as_periods(search, report, client):
    s = search("Sangobion")
    r = client.post("/safety-report", json={"scan_id": s["scan_id"], "age": 26, "sex": "female", "periods": "irregular"})
    assert r.status_code == 200 and colour(r.json()) == "green"
