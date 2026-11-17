"""TC-6  Fruits & vegetables (trained Random Forest + documented interactions) and the personalised dose."""


def foods(body):
    r = body["report"]
    return [f["food"] for f in r["recommended_foods"]], [f["food"] for f in r["foods_to_avoid"]]


def test_iron_eat_with_vitamin_c_fruit_and_keep_spinach_apart(search, report):
    _, body = report(search("Sangobion"), "woman_26_periods")
    eat, avoid = foods(body)
    assert any(f in eat for f in ("Orange", "Guava", "Lemon", "Strawberry"))
    assert "Spinach" in avoid


def test_a_food_is_never_both_eat_and_avoid(search, report):
    for name in ("Sangobion", "Caltrate", "Centrum", "Neurobion"):
        _, body = report(search(name), "woman_26_periods")
        eat, avoid = foods(body)
        assert not set(eat) & set(avoid), name


def test_only_fruits_and_vegetables_are_advised(search, report):
    _, body = report(search("Sangobion"), "woman_26_periods")
    eat, avoid = foods(body)
    assert not {"Milk", "Tea (Black)", "Coffee"} & set(eat + avoid)


def test_food_model_accuracy_is_reported(client):
    assert "Random Forest" in client.get("/").json()["food_model"]


def test_dose_is_given_for_a_safe_report(search, report):
    _, body = report(search("Neurobion"), "man_30")
    dose = body["report"]["recommended_dosage"]["summary"]
    assert dose["amount"] and dose["how_often"]
    assert dose["short_course"] is True          # high B6: short course only


def test_strength_is_compared_with_nih_limit(search, report):
    _, body = report(search("Neurobion"), "man_30")
    b6 = [n for n in body["report"]["recommended_dosage"]["nutrients"] if n["nutrient"].startswith("Vitamin B6")][0]
    assert b6["over_limit"] is True


def test_thousands_separator_is_not_read_as_a_decimal():
    """'10,000 IU' must be ten thousand, not ten — otherwise a strong vitamin D would look weak."""
    import personal_check
    assert personal_check.parse_amounts("Vitamin D3 10,000 IU") == {"vitamin_d": 10000.0}
    assert personal_check.parse_amounts("Vitamin C 1,000 mg") == {"vitamin_c": 1000.0}
    assert personal_check.parse_amounts("Folic acid 2,5 mg")["folate"] == 2500.0
