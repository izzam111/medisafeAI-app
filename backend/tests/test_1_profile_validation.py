"""TC-1  User profile validation: bad or personal data is refused before it is saved or sent anywhere."""
import pytest

VALID = [
    ("adult woman", dict(name="Izza Maryam", age=26, sex="female", periods="yes")),
    ("adult man, no name", dict(name="", age=30, sex="male")),
    ("Urdu name", dict(name="عزہ", age=22, sex="female", periods="yes")),
    ("pregnant woman", dict(name="Sara", age=28, sex="female", periods="yes", pregnant=True)),
    ("breastfeeding woman", dict(name="Amna", age=30, sex="female", periods="yes", breastfeeding=True)),
    ("girl of 6", dict(name="Hira", age=6, sex="female")),
    ("elderly man", dict(name="Ahmed Khan", age=95, sex="male")),
    ("date of birth instead of age", dict(name="Izza", dob="2001-05-14", sex="female", periods="yes")),
    ("oligomenorrhea", dict(name="Amna", dob="1999-01-02", sex="female", periods="irregular")),
    ("username", dict(name="Izza", username="izza_m1", dob="2001-05-14", sex="female", periods="yes")),
]

INVALID = [
    ("phone number as name", dict(name="0300-1234567", age=26, sex="female"), "Name can only have letters"),
    ("email as name", dict(name="someone@example.com", age=26, sex="female"), "Name can only have letters"),
    ("one letter name", dict(name="Z", age=26, sex="female"), "Name can only have letters"),
    ("name too long", dict(name="A" * 41, age=26, sex="female"), "40 characters"),
    ("age 0", dict(name="Ali", age=0, sex="male"), "Age must be between 1 and 120"),
    ("age 150", dict(name="Ali", age=150, sex="male"), "Age must be between 1 and 120"),
    ("unknown sex", dict(name="Ali", age=30, sex="other"), "male"),
    ("pregnant man", dict(name="Ali", age=30, sex="male", pregnant=True), "only apply to females"),
    ("man with periods", dict(name="Ali", age=30, sex="male", periods="yes"), "only apply to females"),
    ("pregnant girl of 9", dict(name="Sara", age=9, sex="female", pregnant=True), "ages 12 to 60"),
    ("breastfeeding at 70", dict(name="Sara", age=70, sex="female", breastfeeding=True), "ages 12 to 60"),
    ("periods at age 5", dict(name="Sara", age=5, sex="female", periods="yes"), "girls under 8"),
    ("man with irregular periods", dict(name="Ali", age=30, sex="male", periods="irregular"), "only apply to females"),
    ("birthday in the future", dict(name="Ali", dob="2999-01-01", sex="male"), "future"),
    ("impossible date", dict(name="Ali", dob="2001-02-30", sex="male"), "real date"),
    ("no age or birthday", dict(name="Ali", sex="male"), "date of birth"),
    ("username with spaces", dict(name="Ali", username="ali khan", age=30, sex="male"), "username"),
    ("username too short", dict(name="Ali", username="al", age=30, sex="male"), "username"),
]


@pytest.mark.parametrize("case,profile", VALID, ids=[c for c, _ in VALID])
def test_valid_profile_is_saved(client, case, profile):
    r = client.put("/profile", json=profile)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("case,profile,message", INVALID, ids=[c for c, _, _ in INVALID])
def test_invalid_profile_is_refused(client, case, profile, message):
    r = client.put("/profile", json=profile)
    assert r.status_code == 422
    assert message.lower() in r.json()["detail"].lower()


def test_report_refuses_more_than_5_reasons(client, search):
    s = search("Centrum")
    r = client.post("/safety-report", json={"scan_id": s["scan_id"], "age": 30, "sex": "male", "reasons": ["a", "b", "c", "d", "e", "f"]})
    assert r.status_code == 422 and "at most 5" in r.json()["detail"]


def test_report_refuses_very_long_reason(client, search):
    s = search("Centrum")
    r = client.post("/safety-report", json={"scan_id": s["scan_id"], "age": 30, "sex": "male", "reasons": ["x" * 81]})
    assert r.status_code == 422 and "80 characters" in r.json()["detail"]


def test_report_refuses_pregnant_man(client, search):
    s = search("Centrum")
    r = client.post("/safety-report", json={"scan_id": s["scan_id"], "age": 30, "sex": "male", "pregnant": True})
    assert r.status_code == 422


def test_age_is_worked_out_from_date_of_birth():
    import datetime
    import app as medisafe
    today = datetime.date.today()
    ten_years_ago = today.replace(year=today.year - 10).isoformat()
    assert medisafe.age_from_dob(ten_years_ago) == 10
    day_before_birthday = (today.replace(year=today.year - 10) + datetime.timedelta(days=1)).isoformat()
    assert medisafe.age_from_dob(day_before_birthday) == 9      # birthday tomorrow: still 9 today


def test_username_is_saved_in_small_letters(client):
    from app import Profile
    assert Profile(name="Izza", username="Izza_M1", age=22, sex="female").username == "izza_m1"


def test_sign_in_with_email_needs_no_lookup(client):
    r = client.post("/auth/login-email", json={"identifier": "someone@example.com"})
    assert r.status_code == 200 and r.json()["email"] == "someone@example.com"


def test_username_lookup_is_rate_limited(client):
    codes = [client.post("/auth/login-email", json={"identifier": "nobody_here"}).status_code for _ in range(12)]
    assert 429 in codes
