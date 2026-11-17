"""TC-3  Scan & Search: CLIP checks the photo, OCR reads the label, the product and its version are identified."""


def test_photo_that_is_not_a_supplement_is_rejected(scan):
    r = scan([("Rice", 50)], is_supplement=False)
    assert r["success"] is False


def test_brand_is_read(scan):
    r = scan([("NEUROBION", 60), ("Vitamin B1 B6 B12", 12)])
    assert r["success"] and r["product"]["name"] == "Neurobion" and r["product"]["supported"]


def test_ocr_mistakes_are_tolerated(scan):
    r = scan([("Fefo1-Vit", 60)])
    assert r["product"]["name"] == "Fefol Vit"


def test_version_men_is_detected(scan):
    r = scan([("gsk", 10), ("Centrum", 60), ("MEN", 40), ("Multivitamin / Multimineral", 8)])
    assert r["product"]["name"] == "Centrum Men"
    assert r["label"]["target"]["sex"] == "male"


def test_version_kids_is_detected(scan):
    r = scan([("Centrum", 60), ("Kids", 40)])
    assert r["label"]["target"]["key"] == "kids"


def test_keep_out_of_reach_of_children_is_not_a_kids_product(scan):
    r = scan([("Centrum", 60), ("Keep out of reach of children", 8)])
    assert r["label"]["target"] is None


def test_scratched_name_is_identified_from_ingredients(scan):
    r = scan([("Ferrous Sulphate 150 mg Folic Acid 0.5 mg capsules", 14)])
    assert r["product"]["identified"] and r["product"]["source"] == "ingredients"
    assert "Iron" in r["product"]["name"]


def test_unreadable_pack_asks_for_the_name(scan):
    r = scan([("blurry", 8)])
    assert r["product"]["identified"] is False


def test_medicine_is_recognised(scan):
    r = scan([("Klaricid", 60), ("Clarithromycin 500mg", 12)])
    assert r["product"]["medicine"] is True and r["product"]["supported"] is False


def test_maker_is_verified(scan):
    r = scan([("Neurobion", 60), ("Manufactured by Martin Dow Marker Ltd under licence of Merck KGaA", 8)])
    assert r["company"]["status"] == "verified"
