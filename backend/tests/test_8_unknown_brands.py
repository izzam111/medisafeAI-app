"""TC-8  Products not in our data: the report is made from the composition printed on the pack itself.
Two brands of the same vitamin with different strengths must give their own results."""
from conftest import colour


def test_unknown_brand_is_read_from_its_label(scan):
    r = scan([("NUTRIFACTOR", 60), ("Nutri B3", 30), ("Each tablet contains: Niacin 500 mg", 10)])
    assert r["product"]["supported"] and not r["product"]["medicine"]
    assert r["label"]["amounts"] == {"niacin": 500.0}
    assert "Niacin" in r["product"]["name"]


def test_unknown_brand_gets_a_report_not_an_error(scan, report):
    r = scan([("NUTRIFACTOR", 60), ("Each tablet contains: Niacin 500 mg", 10)])
    status, rep = report(r, "man_30")
    assert status == 200, rep
    assert colour(rep) in ("orange", "red")          # 500 mg is far above the 35 mg safe daily limit


def test_same_vitamin_different_strength_gives_different_results(scan, report):
    low = scan([("BRANDX", 60), ("Each tablet contains: Niacin 14 mg", 10)])
    high = scan([("BRANDY", 60), ("Each tablet contains: Niacin 500 mg", 10)])
    _, rep_low = report(low, "man_30")
    _, rep_high = report(high, "man_30")
    assert colour(rep_low) == "green" and colour(rep_high) != "green"


def test_child_is_stopped_by_a_strong_unknown_product(scan, report):
    r = scan([("NUTRIFACTOR", 60), ("Each tablet contains: Niacin 500 mg", 10)])
    _, rep = report(r, "boy_8")
    assert colour(rep) == "red"


def test_unknown_iron_product_uses_the_iron_rules(scan):
    r = scan([("NUTRIFACTOR", 60), ("Iron (as ferrous fumarate) 65 mg Folic acid 400 mcg", 10)])
    assert r["product"]["dataset_key"] == "Iron Supplement"
    assert r["label"]["amounts"]["iron"] == 65.0


def test_report_says_the_pack_composition_was_used(scan, report):
    r = scan([("NUTRIFACTOR", 60), ("Each tablet contains: Niacin 500 mg", 10)])
    _, rep = report(r, "man_30")
    assert "Niacin" in str(rep["report"]) and "printed on your pack" in str(rep["report"])


def test_brand_on_the_pack_is_shown_as_the_company(scan, monkeypatch):
    """Nutricost-style front label: no 'Manufactured by' line, the brand is the company."""
    import app as medisafe
    monkeypatch.setattr(medisafe, "claude_read_label", lambda images, text: {
        "product_name": "Nutricost Vitamin B6", "brand": "Nutricost", "manufacturer": None,
        "active_ingredients": ["Vitamin B6 (Pyridoxine HCl) 100 mg"], "other_ingredients": [], "is_supplement": True})
    r = scan([("nutricost", 30), ("Vitamin B6", 60), ("Pyridoxine HCI", 30), ("240 CAPSULES", 10), ("DIETARY SUPPLEMENT", 10)])
    assert r["company"]["status"] == "brand_seen" and r["company"]["name"] == "Nutricost"
    assert r["label"]["amounts"] == {"vitamin_b6": 100.0}
    assert r["label"]["facts_seen"] is False                 # only the front of the bottle was in the photo


def test_report_asks_for_the_back_when_only_the_front_was_seen(scan, report, monkeypatch):
    import app as medisafe
    monkeypatch.setattr(medisafe, "claude_read_label", lambda images, text: {
        "product_name": "Nutricost Vitamin B6", "brand": "Nutricost", "manufacturer": None,
        "active_ingredients": ["Vitamin B6 (Pyridoxine HCl) 100 mg"], "is_supplement": True})
    r = scan([("nutricost", 30), ("Vitamin B6", 60), ("240 CAPSULES", 10)])
    _, rep = report(r, "man_30")
    assert "only saw the front" in str(rep["report"]) and "Nutricost" in str(rep["report"])


def test_every_ingredient_on_the_label_is_listed(scan):
    r = scan([("BRANDZ", 60), ("Supplement Facts", 12),
              ("Vitamin C 500 mg Zinc 10 mg Rose hips 25 mg Bioflavonoids 50 mg", 10)])
    names = {x["name"].lower(): x["checked"] for x in r["label"]["all_ingredients"]}
    assert names.get("vitamin c") is True and names.get("zinc") is True
    assert names.get("rose hips") is False and names.get("bioflavonoids") is False
    assert r["label"]["facts_seen"] is True


def test_typed_label_is_checked_like_a_scanned_one(scan, report, client):
    """Only the front was photographed: the user types the amounts from the back, and they are checked."""
    r = scan([("nutricost", 30), ("Vitamin B6", 60), ("240 CAPSULES", 10)])
    t = client.post("/label-text", json={"scan_id": r["scan_id"], "text": "Vitamin B6 200 mg, Folic acid 400 mcg, rice flour"})
    assert t.status_code == 200, t.text
    assert t.json()["label"]["amounts"]["vitamin_b6"] == 200.0 and t.json()["product"]["supported"]
    _, rep = report(r, "man_30")
    assert "you entered" in str(rep["report"])
    assert colour(rep) != "green"                 # 200 mg B6 is twice the 100 mg adult limit


def test_typed_text_without_amounts_is_refused(scan, client):
    r = scan([("nutricost", 30), ("Vitamin B6", 60)])
    t = client.post("/label-text", json={"scan_id": r["scan_id"], "text": "vitamin b6 tablets"})
    assert t.status_code == 422


def test_front_only_photo_gets_the_full_list_by_lookup(scan, report, client, monkeypatch):
    """Only the front was photographed: the app looks up the full Supplement Facts itself (NIH DSLD or the brand's site)."""
    import app as medisafe
    monkeypatch.setattr(medisafe, "claude_read_label", lambda images, text: {
        "product_name": "Nutricost Vitamin B6", "brand": "Nutricost", "active_ingredients": ["Vitamin B6 100 mg"], "is_supplement": True})
    monkeypatch.setattr(medisafe, "lookup_composition", lambda brand, product: {
        "lines": ["Vitamin B6 (as Pyridoxine HCl) 100 mg"], "other": ["Rice flour", "Gelatin capsule"],
        "name": "Vitamin B6 100 mg", "source": "NIH Dietary Supplement Label Database", "url": "https://dsld.od.nih.gov/label/1"})
    r = scan([("nutricost", 30), ("Vitamin B6", 60), ("240 CAPSULES", 10)])
    assert r["label"]["facts_seen"] is False
    t = client.post("/lookup-composition", json={"scan_id": r["scan_id"]})
    assert t.status_code == 200, t.text
    lab = t.json()["label"]
    assert lab["facts_seen"] and lab["composition_source"]["name"].startswith("NIH")
    assert {"Rice flour", "Gelatin capsule"} <= {x["name"] for x in lab["all_ingredients"]}
    _, rep = report(r, "man_30")
    assert "full ingredient list from NIH" in str(rep["report"])


def test_lookup_never_overrides_the_amount_on_the_pack(scan, client, monkeypatch):
    import app as medisafe
    monkeypatch.setattr(medisafe, "lookup_composition", lambda brand, product: {
        "lines": ["Niacin 50 mg", "Zinc 10 mg"], "other": [], "name": "x", "source": "the product's page online", "url": None})
    r = scan([("BRANDQ", 60), ("Niacin 500 mg", 10)])
    t = client.post("/lookup-composition", json={"scan_id": r["scan_id"]}).json()
    assert t["label"]["amounts"]["niacin"] == 500.0 and t["label"]["amounts"]["zinc"] == 10.0


def test_lookup_that_finds_nothing_says_so(scan, client, monkeypatch):
    import app as medisafe
    monkeypatch.setattr(medisafe, "lookup_composition", lambda brand, product: None)
    r = scan([("BRANDQ", 60), ("Niacin 500 mg", 10)])
    assert client.post("/lookup-composition", json={"scan_id": r["scan_id"]}).status_code == 404


def test_no_composition_found_is_never_called_safe(scan, report, client, monkeypatch):
    """Only a name on the pack, nothing found online: the report says the dose was not checked and is not green."""
    import app as medisafe
    monkeypatch.setattr(medisafe, "claude_read_label", lambda images, text: {
        "product_name": "Zorvex Daily", "brand": "Zorvex", "is_supplement": True})
    monkeypatch.setattr(medisafe, "lookup_composition", lambda brand, product: None)
    r = scan([("ZORVEX", 60), ("Daily", 30)])
    assert client.post("/lookup-composition", json={"scan_id": r["scan_id"]}).status_code == 404
    _, rep = report(r, "man_30")
    assert "dose was NOT checked" in str(rep["report"]) and colour(rep) != "green"
