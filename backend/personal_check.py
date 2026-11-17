"""
personal_check.py — decides if a supplement suits THIS person, using data, not AI.

Inputs : what the label says (read by OCR) + the user's profile (age, sex, periods, pregnancy, breastfeeding)
Data   : nutrient_limits.json  → daily need and safe upper limit per nutrient, by age and sex (NIH ODS)
         supplement_rules.json → who each supplement suits: children, pregnancy, periods, herbal warnings
         purpose_rules.json    → what each supplement is (and isn't) for, to check the user's reasons
Output : a list of checks (ok / caution / stop), dosage directions, and an overall verdict.
"""

import json, math, os, re

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modeltraining", "data")
with open(os.path.join(DATA_DIR, "nutrient_limits.json"), encoding="utf-8") as f:
    LIMITS = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
with open(os.path.join(DATA_DIR, "supplement_rules.json"), encoding="utf-8") as f:
    _rules = json.load(f)
GROUPS, PRODUCTS = _rules["groups"], _rules["products"]
with open(os.path.join(os.path.dirname(DATA_DIR), "models", "purpose_rules.json"), encoding="utf-8") as f:
    PURPOSE = json.load(f)
with open(os.path.join(DATA_DIR, "reason_map.json"), encoding="utf-8") as f:
    REASON_MAP = json.load(f)
with open(os.path.join(DATA_DIR, "target_groups.json"), encoding="utf-8") as f:
    TARGETS = json.load(f)["groups"]


def find_target(*texts: str) -> dict | None:
    """Who the product is made for (Men, Women, Kids, 50+, Teens), from its name or label words.
    'men and women' / 'for adults and children' are general products, so they count as no target."""
    text = " ".join(t for t in texts if t).lower()
    if re.search(r"\bmen\b.{0,12}\bwomen\b|\bwomen\b.{0,12}\bmen\b|adults? and children", text):
        text = re.sub(r"\b(wo)?men'?s?\b|\bchildren\b", " ", text)
    for g in TARGETS:
        if re.search(g["pattern"], text):
            return {k: g[k] for k in ("key", "label", "phrase", "sex", "min_age", "max_age") if k in g}
    return None

RANK = {"ok": 0, "caution": 1, "stop": 2}
FROM_RULE = {"ok": "ok", "ask_doctor": "caution", "avoid": "stop"}

# ═══════════════════════════════════════════════════════════════════════════════
# 1. READING THE LABEL
# ═══════════════════════════════════════════════════════════════════════════════

# Names a label may use for each nutrient. Salt names (ferrous sulphate…) are not the same as the
# amount of the mineral itself, so for those we only trust an "equivalent to … elemental" amount.
NAMES = {
    "vitamin_a":   r"vitamin\s*a\b|retinol|retinyl\s*\w+",
    "vitamin_c":   r"vitamin\s*c\b|ascorbic\s*acid|sodium\s*ascorbate",
    "vitamin_d":   r"vitamin\s*d\s*3?\b|cholecalciferol",
    "vitamin_e":   r"vitamin\s*e\b|(?:dl?-?\s*alpha\s*)?tocopher\w*",
    "vitamin_k":   r"vitamin\s*k\s*[12]?\b|menaquinone|phytomenadione",
    "vitamin_b1":  r"vitamin\s*b\s*1\b|thiamine?\b(?:\s*(?:mononitrate|hydrochloride|hcl))?",
    "niacin":      r"vitamin\s*b\s*3\b|niacin(?:amide)?|nicotinamide",
    "vitamin_b6":  r"vitamin\s*b\s*6\b|pyridoxine(?:\s*(?:hydrochloride|hcl))?",
    "folate":      r"folic\s*acid|l?-?\s*methylfolate|folate|vitamin\s*b\s*9\b",
    "vitamin_b12": r"vitamin\s*b\s*12\b|cyanocobalamin|methylcobalamin|hydroxocobalamin",
    "biotin":      r"biotin|vitamin\s*b\s*7\b",
    "iron":        r"elemental\s*iron|\biron\b|ferrous\s*\w+|ferric\s*\w+",
    "zinc":        r"elemental\s*zinc|\bzinc\b",
    "calcium":     r"elemental\s*calcium|\bcalcium\b",
    "magnesium":   r"elemental\s*magnesium|\bmagnesium\b",
    "potassium":   r"\bpotassium\b",
}
SALT = r"(?:sulphate|sulfate|fumarate|gluconate|carbonate|citrate|oxide|chloride|bisglycinate|glycinate|lactate|phosphate|polymaltose)"
AMOUNT = r"(\d+(?:[.,]\d+)?)\s*(mg|mcg|µg|ug|iu|i\.u\.?|g)\b"


def _to_unit(value: float, unit: str, nutrient: str) -> float | None:
    unit = unit.lower().replace("µg", "mcg").replace("ug", "mcg").replace("i.u.", "iu").replace("i.u", "iu")
    want = LIMITS[nutrient]["unit"].lower()
    if unit == "iu":
        per_iu = {"vitamin_d": ("iu", 1), "vitamin_a": ("mcg", 0.3), "vitamin_e": ("mg", 0.67)}.get(nutrient)
        if not per_iu:
            return None
        unit, value = per_iu[0], value * per_iu[1]
    grams = {"g": 1e3, "mg": 1, "mcg": 1e-3}          # everything to mg first
    if unit in grams and want in grams:
        return value * grams[unit] / grams[want]
    if nutrient == "vitamin_d" and unit == "mcg":       # 1 mcg vitamin D = 40 IU
        return value * 40
    return value if unit == want else None


def parse_amounts(text: str) -> dict:
    """'Vitamin B6 200 mg' → {'vitamin_b6': 200.0} (in the unit nutrient_limits.json uses)."""
    text = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", text)    # 10,000 IU → 10000 (thousands separator)
    text = text.replace(",", ".")                          # 2,5 mg → 2.5 (decimal comma)
    found = {}
    for nutrient, names in NAMES.items():
        for m in re.finditer(names, text, re.I):
            after = text[m.end(): m.end() + 70]
            is_salt = (re.search(SALT, m.group(0), re.I) or re.match(rf"\s*\(?\s*(?:as\s+)?\w*\s*{SALT}", after, re.I)
                       or re.match(SALT, after.strip(), re.I))
            elemental = re.search(rf"(?:equivalent|equiv\.?|eq\.?)\s*to\s*(?:elemental\s*\w+\s*)?{AMOUNT}", after, re.I)
            as_form = re.match(rf"\s*\(\s*as\s+[^)]{{1,40}}\)\s*{AMOUNT}", after, re.I)   # "Iron (as ferrous fumarate) 65 mg"
            if as_form and not re.search(SALT, m.group(0), re.I):
                num, unit = as_form.groups()
            elif elemental:
                num, unit = elemental.groups()
            elif is_salt:
                continue                                  # salt weight ≠ mineral amount
            else:
                direct = (re.match(rf"[^0-9a-z]{{0,25}}?(?:\([^)]{{0,30}}\)\s*)?{AMOUNT}", after, re.I)
                          or re.search(rf"{AMOUNT}\s*(?:of\s+)?(?:dl?-?\s*)?$", text[max(0, m.start() - 25): m.start()], re.I))
                if not direct:                            # amount may also come before the name: "400 IU vitamin E"
                    continue
                num, unit = direct.groups()
            value = _to_unit(float(num), unit, nutrient)
            if value:
                found[nutrient] = round(value, 3)
                break
    return found


def parse_age_limit(text: str) -> tuple[int | None, str | None]:
    """Age limit printed on the pack, e.g. 'Not recommended for children under 12 years'."""
    patterns = [
        r"not\s+(?:recommended|suitable|intended|to\s+be\s+(?:used|given)|for\s+use)\s+(?:for|in|to|by)\s+children\s+(?:under|below|less\s+than|younger\s+than)\s+(\d{1,2})",
        r"not\s+for\s+(?:use\s+(?:by|in)\s+)?children\s+(?:under|below|less\s+than|younger\s+than)\s+(?:the\s+age\s+of\s+)?(\d{1,2})",
        r"children\s+(?:under|below|less\s+than)\s+(\d{1,2})\s*(?:years?|yrs?)?\s*[:\-–]?\s*(?:do\s+not|should\s+not|not\s+recommended)",
        r"adults?\s+and\s+children\s+(?:over|above|aged)\s+(\d{1,2})",
        r"for\s+(?:adults|children)\s+(?:over|above|aged)\s+(\d{1,2})",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return int(m.group(1)), m.group(0)
    m = re.search(r"\b(?:for\s+adults?\s+only|adults?\s+only|not\s+for\s+(?:use\s+(?:by|in)\s+)?children)\b", text, re.I)
    if m:
        return 18, m.group(0)
    return None, None


def parse_pregnancy_warning(text: str) -> str | None:
    m = re.search(r"(?:not\s+(?:recommended|suitable|to\s+be\s+used)|do\s+not\s+(?:use|take)|avoid)[^.]{0,40}(?:pregnan|breast\s*feed|lactat)\w*",
                  text, re.I)
    return m.group(0) if m else None


def parse_directions(text: str) -> str | None:
    """'Take 1 tablet daily' / 'One capsule twice a day' as printed on the pack."""
    m = re.search(r"(?:take\s+)?(?:\d|one|two|three|1/2|half)\s+(?:tablets?|capsules?|caplets?|sachets?|softgels?|teaspoons?|tsp)"
                  r"\s+(?:[a-z]+\s+){0,3}?(?:(?:once|twice|thrice|\d\s*times)\s+(?:a|per)\s+day|(?:once|twice|thrice)\s+daily|daily|a\s+day|per\s+day)",
                  text, re.I)
    return m.group(0).strip() if m else None


def strength_list(amounts: dict) -> list:
    """{'vitamin_b6': 200} → [{'nutrient': 'Vitamin B6 (Pyridoxine)', 'amount': '200 mg'}] for showing in the app."""
    return [{"nutrient": LIMITS[n]["name"], "amount": fmt(v, LIMITS[n]["unit"])} for n, v in amounts.items()]


def read_label(text: str) -> dict:
    min_age, age_text = parse_age_limit(text)
    return {"amounts": parse_amounts(text), "min_age": min_age, "age_text": age_text,
            "pregnancy_warning": parse_pregnancy_warning(text), "directions": parse_directions(text)}

# ═══════════════════════════════════════════════════════════════════════════════
# 2. DAILY NEED AND SAFE LIMIT FOR THIS PERSON
# ═══════════════════════════════════════════════════════════════════════════════

def daily_need(nutrient: str, p: dict) -> float | None:
    age = p["age"]
    if nutrient == "iron" and p["sex"] == "female" and p.get("periods") == "no" and not p.get("pregnant"):
        for lo, hi, val in LIMITS["iron"]["no_periods_female_need"]:
            if lo <= age <= hi:
                return val
    for lo, hi, male, female, preg, bf in LIMITS[nutrient]["need"]:
        if lo <= age <= hi:
            if p.get("pregnant") and preg:
                return preg
            if p.get("breastfeeding") and bf:
                return bf
            return female if p["sex"] == "female" else male
    return None


def safe_limit(nutrient: str, age: int) -> float | None:
    for lo, hi, val in LIMITS[nutrient]["ul"]:
        if lo <= age <= hi:
            return val
    return None


def limit_group(nutrient: str, age: int) -> str:
    for lo, hi, _ in LIMITS[nutrient]["ul"]:
        if lo <= age <= hi:
            return "adults" if lo >= 19 else f"ages {lo} to {hi}"
    return f"age {age}"


def fmt(value: float, unit: str) -> str:
    v = f"{value:,.1f}".rstrip("0").rstrip(".")
    return f"{v} {unit}"

# ═══════════════════════════════════════════════════════════════════════════════
# 3. THE PERSONAL CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def _rule(product: dict, group: dict, key: str) -> dict | None:
    return product.get(key) or group.get(key)


def assess(dataset_key: str | None, label: dict, p: dict) -> dict:
    """p = {"age": int, "sex": "male"|"female", "periods": "yes"|"no"|None, "pregnant": bool, "breastfeeding": bool}"""
    product = PRODUCTS.get(dataset_key or "", {"group": "general", "nutrients": []})
    group = GROUPS[product["group"]]
    checks, notes = [], []
    add = lambda key, title, status, text: checks.append({"key": key, "title": title, "status": status, "text": text})
    age, female = p["age"], p["sex"] == "female"

    if product["group"] == "not_supplement":
        add("product", "Product", "stop", group["all"]["text"])
        return {"checks": checks, "dosage": None, "notes": [], "verdict": "Not safe"}

    # Strength per tablet: from the label if OCR read it, otherwise the known pack strength.
    amounts = {n: v for n, v in label.get("amounts", {}).items() if n in LIMITS}
    source = "label"
    if not amounts and product.get("typical_strength"):
        amounts, source = dict(product["typical_strength"]), "typical"

    # ── Age ───────────────────────────────────────────────────────────────────
    over = [(n, v, safe_limit(n, age)) for n, v in amounts.items()
            if safe_limit(n, age) is not None and v > safe_limit(n, age)]
    child_age = group.get("child_age", 14)
    target = label.get("target")
    sex_word = {"male": "men", "female": "women"}
    many = len(product.get("nutrients", [])) >= 5 or product["group"] in ("prenatal",)
    if target and target.get("sex") and p["sex"] != target["sex"]:
        you = ({"male": "Boys", "female": "Girls"} if age < 18 else {"male": "Men", "female": "Women"})[p["sex"]]
        add("target", "Made for", "stop",
            f"This is made for {sex_word[target['sex']]}. {you} need different amounts (for example of iron), "
            f"so use a {'children' if age < 12 else sex_word[p['sex']]}'s or general formula.")
    if age < 1:
        add("age", "Age", "stop", "Supplements for babies under 1 year should only be given on a doctor's advice.")
    elif target and target.get("min_age") and age < target["min_age"]:
        who = "adults" if target["min_age"] == 18 else f"ages {target['min_age']} and over"
        add("age", "Age", "stop" if age < 18 else "caution",
            f"This {target.get('phrase', target['label'])} formula is made for {who}. You are {age}. "
            + ("Children need a children's formula with smaller amounts." if age < 18 else "A general adult formula fits you better."))
    elif target and target.get("max_age") and age > target["max_age"]:
        add("age", "Age", "caution", f"This is a {target.get('phrase', target['label'])} formula, made for ages up to {target['max_age']}. "
                                     f"At {age}, an adult formula fits your needs better.")
    elif label.get("min_age") and age < label["min_age"]:
        add("age", "Age", "stop", f"The pack says: \"{label['age_text']}\". You are {age}, so this product is not for you.")
    elif over:
        n, v, ul = over[0]
        u, times = LIMITS[n]["unit"], v / ul
        how_much = "twice" if 1.8 <= times <= 2.2 else f"{times:.0f} times" if times >= 2.5 else "more than"
        start = (f"One tablet has {fmt(v, u)} of {LIMITS[n]['name']}, {how_much} the safe daily limit "
                 f"for {limit_group(n, age)} ({fmt(ul, u)}).")
        if age < 18:
            add("age", "Age", "stop", start + " It is not suitable for you unless a doctor prescribed it.")
        else:
            add("age", "Dose strength", "caution",
                start + " Fine for a short course. Taking it every day for months can cause harm, so use it long-term only if a doctor advises.")
    elif age < 12 and not amounts and not (target and target.get("max_age")) and product["group"] in ("vitamin_mineral", "iron", "prenatal"):
        # We don't know its strength, and adult products are usually for ages 12 and over
        add("age", "Age", "stop" if many or product["group"] == "iron" else "caution",
            ("This is an adult multivitamin. Children under 12 need a children's formula with smaller amounts."
             if many else "Most adult supplements are for ages 12 and over. Use a children's formula, or the children's dose "
                          "printed on the pack, and ask a doctor first."))
    elif age < child_age and group.get("child"):
        rule = group["child"]
        add("age", "Age", FROM_RULE[rule["status"]], rule["text"])
    elif not dataset_key and not amounts and not label.get("min_age"):
        add("age", "Age", "caution", "We don't have age data for this product. Follow the age directions on the pack.")
    else:
        text = f"Suitable for age {age}."
        if label.get("min_age"):
            text += f" The pack says it is for ages {label['min_age']} and over."
        add("age", "Age", "ok", text)

    # ── Sex, periods, pregnancy, breastfeeding ────────────────────────────────
    g = product["group"]
    if g == "prenatal":
        if age < child_age:
            pass                                         # already covered by the age check
        elif not female:
            add("sex", "Made for", "stop", group["male"]["text"])
        elif p.get("pregnant") or p.get("breastfeeding"):
            rule = group["pregnant"] if p.get("pregnant") else group["breastfeeding"]
            add("sex", "Made for", "ok", rule["text"])
        else:
            add("sex", "Made for", "caution", group["female_not_pregnant"]["text"])
    elif g == "iron" and age >= child_age and not p.get("pregnant"):
        if female and p.get("periods") in ("yes", "no"):
            add("periods", "Periods and iron", "ok" if p["periods"] == "yes" else "caution", group["periods"][p["periods"]])
        elif not female and age >= 19:
            add("sex", "Iron need", "caution", group["male_adult"])

    if female and p.get("pregnant"):
        if label.get("pregnancy_warning"):
            add("pregnancy", "Pregnancy", "stop", f"The pack says: \"{label['pregnancy_warning']}\".")
        elif g != "prenatal" and _rule(product, group, "pregnant"):
            rule = _rule(product, group, "pregnant")
            add("pregnancy", "Pregnancy", FROM_RULE[rule["status"]], rule["text"])
    if female and p.get("breastfeeding") and g != "prenatal" and _rule(product, group, "breastfeeding"):
        rule = _rule(product, group, "breastfeeding")
        add("breastfeeding", "Breastfeeding", FROM_RULE[rule["status"]], rule["text"])

    if product.get("note"):
        notes.append(product["note"])

    # ── Dosage ────────────────────────────────────────────────────────────────
    dosage = build_dosage(amounts, source, label.get("directions"), p, product, over)

    worst = max((c["status"] for c in checks), key=RANK.get, default="ok")
    verdict = {"ok": "Safe", "caution": "Use with caution", "stop": "Not safe"}[worst]
    return {"checks": checks, "dosage": dosage, "notes": notes, "verdict": verdict}


def build_dosage(amounts: dict, source: str, directions: str | None, p: dict, product: dict, over: list) -> dict:
    """Per-nutrient table (per tablet / your daily need / safe limit) + plain steps."""
    rows, timing = [], []
    for n, v in amounts.items():
        need, ul, unit = daily_need(n, p), safe_limit(n, p["age"]), LIMITS[n]["unit"]
        rows.append({"nutrient": LIMITS[n]["name"], "per_tablet": fmt(v, unit),
                     "daily_need": fmt(need, unit) if need else None,
                     "percent_of_need": round(100 * v / need) if need else None,
                     "safe_limit": fmt(ul, unit) if ul else "No limit set",
                     "over_limit": bool(ul and v > ul)})
    for n in (list(amounts) or product.get("nutrients", [])):
        tip = LIMITS[n].get("how_to_take")
        if tip and tip not in timing:
            timing.append(tip)

    if over and p["age"] < 18:
        steps = ["Don't take this product unless a doctor prescribed it for you.",
                 "If a doctor did prescribe it, take exactly the dose they gave and no more."]
    elif over:
        steps = [f"The pack says: {directions}." if directions else "Take no more than 1 tablet a day.",
                 "Use it for a short course only, as your doctor or pharmacist advises. Don't take more than 1 tablet a day."]
    else:
        if directions:
            steps = [f"The pack says: {directions}."]
        elif rows:
            steps = ["Take 1 tablet a day unless the pack or your doctor says otherwise."]
        else:
            steps = ["Take the dose printed on the pack. We couldn't read the strength from the photo, so we can't check it against your age."]
        if p["age"] < 14:
            steps.append("Use the children's dose on the pack. If the pack has no children's dose, ask a pharmacist before giving it.")
        steps.append("Don't take more than the pack says. The safe limit counts what you get from food too.")
    steps += timing
    return {"steps": steps, "nutrients": rows, "strength_source": source if rows else None,
            "summary": dose_summary(directions, list(amounts) or product.get("nutrients", []),
                                    doctor_only=bool(over) and p["age"] < 18, short_course=bool(over) and p["age"] >= 18)}


WORDS = {"one": "1", "two": "2", "three": "3", "half": "½", "1/2": "½"}


def dose_summary(directions: str | None, nutrients: list, doctor_only: bool, short_course: bool = False) -> dict:
    """Big-type dose card: amount / how often / when. Taken from the pack's directions, never guessed."""
    if doctor_only:
        return {"doctor_only": True}
    when = next((LIMITS[n]["when"] for n in nutrients if n in LIMITS and LIMITS[n].get("when")), None)
    amount = how_often = None
    if directions:
        m = re.search(r"(\d|one|two|three|1/2|half)\s+(tablet|capsule|caplet|sachet|softgel|teaspoon|tsp)", directions, re.I)
        if m:
            n = WORDS.get(m.group(1).lower(), m.group(1))
            amount = f"{n} {m.group(2).lower()}{'s' if n not in ('1', '½') else ''}"
        d = directions.lower()
        how_often = ("3 times a day" if re.search(r"thrice|3\s*times", d) else "twice a day" if re.search(r"twice|2\s*times", d)
                     else "once a day" if re.search(r"once|daily|a\s+day|per\s+day", d) else None)
    if short_course:
        amount, how_often = amount or "1 tablet", "once a day"
    usual = False
    if not amount and not how_often and nutrients:      # pack directions not read: the usual dose for vitamins/minerals
        amount, how_often, usual = "1 tablet", "once a day", True
    return {"doctor_only": False, "short_course": short_course, "amount": amount, "how_often": how_often, "when": when,
            "usual": usual}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DOES IT HELP WITH THE USER'S REASON?  (works without AI)
# ═══════════════════════════════════════════════════════════════════════════════

# A reason that names a nutrient ("iron deficiency", "low B12") needs a product that contains that nutrient.
NEEDS = {
    "iron":        r"\biron\b|an(?:a)?emi|ha?emoglobin|low blood|khoon",
    "calcium":     r"\bcalcium\b",
    "vitamin_d":   r"vitamin\s*d\b|vit\.?\s*d\b",
    "vitamin_b12": r"\bb\s*-?\s*12\b",
    "folate":      r"folic|folate",
    "zinc":        r"\bzinc\b",
    "magnesium":   r"magnesium",
    "vitamin_c":   r"vitamin\s*c\b",
    "vitamin_a":   r"vitamin\s*a\b",
    "vitamin_e":   r"vitamin\s*e\b",
    "potassium":   r"potassium",
    "biotin":      r"biotin",
}
GENERAL = r"general health|daily use|daily vitamin|overall health|everyday nutrition"
EVERYDAY = "Everyday nutrition (no specific problem)"   # taking it to top up the diet, not for a health problem
# Illnesses that need a doctor's treatment. No vitamin, mineral or herbal supplement treats these.
MEDICAL = (r"seizure|epilep|\bfits?\b|convuls|cancer|tumou?r|stroke|heart attack|kidney (?:failure|disease)|"
           r"liver disease|hepatitis|tubercul|\btb\b|infection|fever|\bcolds?\b|\bflu\b|influenza|cough|covid|"
           r"asthma|pneumonia|typhoid|malaria|dengue|migraine|headache|schizo|bipolar|psychos|parkinson|alzheimer|"
           r"thyroid|allerg|ulcer|hiv|blood pressure|hypertension")


def _a(word: str) -> str:
    return ("an " if word[:1] in "aeiou" else "a ") + word


def _purpose_rule(name: str, dataset_key: str | None) -> dict | None:
    text = f"{name} {dataset_key or ''}".lower()
    keys = [k for k in PURPOSE if k != "default" and k in text]
    return PURPOSE[max(keys, key=len)] if keys else None


def main_nutrients(product: dict, has: list, label_amounts: dict) -> list:
    """The nutrients a product is mainly for: a strong dose (half a day's need or more), at most 3.
    Small extras (vitamin C added to help iron absorb) don't decide what the product is for."""
    amounts = {n: v for n, v in {**product.get("typical_strength", {}), **label_amounts}.items() if n in LIMITS}
    adult = {"age": 30, "sex": "female", "periods": "yes", "pregnant": False, "breastfeeding": False}
    if amounts:
        share = {n: v / (daily_need(n, adult) or 1e9) for n, v in amounts.items()}
        strong = sorted((n for n in share if share[n] >= 0.5), key=share.get, reverse=True)
        if strong:
            return strong[:3]
    return has[:2]


def product_reasons(name: str, dataset_key: str | None, label_amounts: dict, p: dict | None = None,
                    herbs: list | None = None) -> list:
    """Reasons this product is actually used for, from what is inside it (reason_map.json).
    p = profile: reasons only for women, or for some ages, are left out for others."""
    product = PRODUCTS.get(dataset_key or "", {"group": "general", "nutrients": []})
    has = list(dict.fromkeys([*product.get("nutrients", []), *[n for n in label_amounts if n in LIMITS]]))
    text = f"{name} {dataset_key or ''} {' '.join(herbs or [])}".lower()
    rows = []
    for key, items in REASON_MAP["products"].items():          # herbs and named products first
        if key in text:
            rows += items
    if product["group"] == "prenatal":
        rows += REASON_MAP["products"]["prenatal"]
    if len(has) >= 5:                                           # a multivitamin: what multivitamins are for
        rows += [r for r in REASON_MAP["multivitamin"] if not r.get("needs_any") or set(r["needs_any"]) & set(has)]
    else:
        for n in main_nutrients(product, has, label_amounts):
            rows += REASON_MAP["nutrients"].get(n, [])
    rule = _purpose_rule(name, dataset_key)
    out = []
    for r in rows:
        label = r["label"]
        if label in out:
            continue
        if rule and any(k in label.lower() for k in rule["not_valid"]):
            continue                                            # the product's own rules say it is not for this
        if p:
            if r.get("female") and p.get("sex") != "female":
                continue
            if r.get("min_age") and p.get("age", 0) < r["min_age"]:
                continue
            if r.get("max_age") and p.get("age", 0) > r["max_age"]:
                continue
            if label == "Heavy periods" and p.get("periods") == "no":
                continue
            if label in ("Pregnancy", "Planning a pregnancy", "Breastfeeding") and p.get("periods") == "no" and p.get("age", 0) >= 35:
                continue                                        # after menopause
        out.append(label)
    return out


def check_reasons(name: str, dataset_key: str | None, label_amounts: dict, reasons: list) -> list:
    """Each reason → helps / no / unsure, with a plain sentence. Uses nutrient content + purpose_rules.json."""
    product = PRODUCTS.get(dataset_key or "", {"group": "general", "nutrients": []})
    has = set(product.get("nutrients", [])) | set(label_amounts)
    herbal = product["group"] in ("herbal", "hormone")
    rule = _purpose_rule(name, dataset_key)
    known = {x.lower() for x in product_reasons(name, dataset_key, label_amounts)}
    results = []
    for reason in reasons:
        r = reason.lower()
        needed = [n for n, pattern in NEEDS.items() if re.search(pattern, r)]
        if r in known and not re.search(GENERAL, r):
            res, text = "helps", f"{name} is used for {reason.lower()}, based on what is inside it."
        elif re.search(GENERAL, r):
            res, text = "helps", "Fine for general daily use, within the safe daily limits."
        elif needed and herbal:
            n = LIMITS[needed[0]]["name"].split(" (")[0]
            res, text = "no", f"{name} is a herbal product, not a measured {n.lower()} supplement. Ask your doctor about a proper {n.lower()} supplement."
        elif needed:
            missing = [n for n in needed if n not in has]
            if missing:
                n = LIMITS[missing[0]]["name"].split(" (")[0]
                res, text = "no", f"{name} has no {n.lower()}, so it won't help with this. Ask your doctor about {_a(n.lower())} supplement."
            else:
                n = LIMITS[needed[0]]["name"].split(" (")[0]
                res, text = "helps", f"{name} contains {n.lower()}, which is used for this."
        elif rule and any(k in r for k in rule["not_valid"]):
            res, text = "no", rule["invalid_msg"]
        elif re.search(MEDICAL, r):
            res, text = "no", (f"{name} does not treat {reason.lower()}. This needs a doctor's care and the right "
                               "medicine, not a supplement.")
        elif rule and any(k in r for k in rule["valid"]):
            res, text = "helps", rule["valid_msg"]
        elif "niacin" in has and re.search(r"cholesterol|lipid|triglycer", r):
            # NIH ODS: niacin changes blood fats only at high, prescription doses and has not been shown to prevent heart disease
            res, text = "no", ("Niacin changes cholesterol only at high, prescription doses that need a doctor's supervision, "
                               "and studies have not shown that it prevents heart disease. Don't take it for cholesterol "
                               "unless your doctor prescribes it.")
        else:
            res, text = "unsure", f"There is no good evidence that {name} helps with {reason.lower()}."
        results.append({"reason": reason, "result": res, "text": text})
    return results


def reason_check_row(results: list) -> dict | None:
    """One line for the 'Your checks' list."""
    no = [r for r in results if r["result"] == "no"]
    if no:
        return {"key": "reason", "title": "Your reason", "status": "stop", "text": no[0]["text"]}
    unsure = [r for r in results if r["result"] == "unsure"]
    if unsure:
        return {"key": "reason", "title": "Your reason", "status": "stop", "text": unsure[0]["text"]}
    if results and all(r["result"] == "helps" for r in results):
        return {"key": "reason", "title": "Your reason", "status": "ok", "text": "It is used for the reasons you gave."}
    return None


# Reasons shown on "Why do you take it?" when the AI is off. Only the ones check_reasons() says help are shown,
# so the suggestions can never contradict the report.
REASON_OPTIONS = [
    "Low iron / anaemia", "Tiredness and weakness", "Low vitamin B12", "Nerve pain or tingling", "Low vitamin D",
    "Bone health", "Low calcium", "Pregnancy", "Immunity", "Hair, skin and nails", "Joint pain",
    "Heart health", "Sleep problems", "Stress and anxiety", "Constipation", "Blood sugar / diabetes",
    "Brain and memory", "Muscle cramps",
]


def suggested_reasons(name: str, dataset_key: str | None, label_amounts: dict, ai_reasons: list | None = None,
                      p: dict | None = None, herbs: list | None = None) -> list:
    """Only reasons this product is really used for. AI suggestions are added only if our checks agree they help."""
    keep = product_reasons(name, dataset_key, label_amounts, p, herbs)
    if ai_reasons:
        for r in check_reasons(name, dataset_key, label_amounts, ai_reasons):
            if r["result"] == "helps" and r["reason"].lower() not in {k.lower() for k in keep}:
                keep.append(r["reason"])
    if not keep:                                    # nothing specific known: the only honest option
        keep.append(EVERYDAY)
    return keep[:9]
