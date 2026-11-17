"""TC-4  Safety verdict for each supplement and each kind of person (age, sex, periods, pregnancy, breastfeeding).
green = Safe, orange = Take with care, red = Not safe / not right for the reason."""
import pytest

from conftest import colour

SCANNED = {
    "Centrum Men":   [("Centrum", 60), ("MEN", 40), ("Keep out of reach of children", 8)],
    "Centrum Women": [("Centrum", 60), ("Women", 40)],
    "Centrum Kids":  [("Centrum", 60), ("Kids", 40)],
    "Centrum 50+":   [("Centrum", 60), ("Silver 50+", 40)],
    "Centrum":       [("Centrum", 60), ("Multivitamin for men and women", 12)],
}
SEARCHED = {"Neurobion": "Neurobion", "Sangobion": "Sangobion", "Femibion": "Femibion", "Ashwagandha": "Ashwagandha",
            "Caltrate": "Caltrate", "NIH Vitamin D3 5000 IU": "Fresh Nutrition Vitamin D3 + K2",
            "NIH Melatonin 3 mg": "CVS Health Melatonin 3 mg", "NIH Iron 27 mg": "Adaptogen Research Iron Chelate"}

CASES = [
    # product, person, reasons, expected colour
    ("Centrum Men", "girl_8_periods", [], "red"), ("Centrum Men", "man_30", [], "green"),
    ("Centrum Men", "woman_26_periods", [], "red"), ("Centrum Men", "boy_8", [], "red"),
    ("Centrum Women", "woman_26_periods", [], "green"), ("Centrum Women", "man_30", [], "red"),
    ("Centrum Women", "girl_15_periods", [], "red"),
    ("Centrum Kids", "boy_8", [], "green"), ("Centrum Kids", "woman_26_periods", [], "orange"),
    ("Centrum 50+", "man_70", [], "green"), ("Centrum 50+", "woman_26_periods", [], "orange"),
    ("Centrum 50+", "girl_15_periods", [], "red"),
    ("Centrum", "girl_8_periods", [], "red"), ("Centrum", "girl_6", [], "red"), ("Centrum", "girl_15_periods", [], "green"),
    ("Centrum", "man_30", [], "green"),
    ("Neurobion", "girl_8_periods", [], "red"), ("Neurobion", "girl_15_periods", [], "red"),
    ("Neurobion", "man_30", [], "orange"), ("Neurobion", "man_70", [], "orange"),
    ("Sangobion", "boy_8", [], "red"), ("Sangobion", "man_30", [], "orange"), ("Sangobion", "woman_26_periods", [], "green"),
    ("Sangobion", "woman_55_menopause", [], "orange"), ("Sangobion", "pregnant_28", [], "green"),
    ("Sangobion", "girl_15_periods", [], "green"),
    ("Femibion", "man_30", [], "red"), ("Femibion", "woman_26_periods", [], "orange"), ("Femibion", "pregnant_28", [], "green"),
    ("Femibion", "breastfeeding_30", [], "green"), ("Femibion", "girl_6", [], "red"),
    ("Ashwagandha", "pregnant_28", [], "red"), ("Ashwagandha", "breastfeeding_30", [], "red"),
    ("Ashwagandha", "man_30", [], "green"), ("Ashwagandha", "girl_15_periods", [], "orange"),
    ("Caltrate", "woman_55_menopause", [], "green"), ("Caltrate", "man_70", [], "green"),
    ("NIH Vitamin D3 5000 IU", "girl_8_periods", [], "red"), ("NIH Vitamin D3 5000 IU", "man_30", [], "orange"),
    ("NIH Melatonin 3 mg", "girl_6", [], "orange"), ("NIH Melatonin 3 mg", "man_30", [], "green"),
    ("NIH Iron 27 mg", "boy_8", [], "red"), ("NIH Iron 27 mg", "woman_26_periods", [], "green"),
    ("NIH Iron 27 mg", "man_30", [], "orange"),
]


@pytest.fixture
def product(scan, search):
    def get(name):
        return scan(SCANNED[name]) if name in SCANNED else search(SEARCHED[name])
    return get


@pytest.mark.parametrize("name,person,reasons,expected", CASES, ids=[f"{p} | {who} -> {exp}" for p, who, _, exp in CASES])
def test_verdict(product, report, name, person, reasons, expected):
    status, body = report(product(name), person, reasons)
    assert status == 200, body
    assert colour(body) == expected, body["report"]["is_safe_to_take"]["reason"]


def test_red_report_hides_no_reason(product, report):
    """A red verdict always says why."""
    _, body = report(product("Centrum Men"), "girl_8_periods")
    s = body["report"]["is_safe_to_take"]
    assert "made for men" in s["reason"].lower()
    assert any(c["status"] == "stop" for c in s["checks"])
