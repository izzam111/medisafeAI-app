"""
import_usda_foods.py — adds fruits and vegetables eaten in Pakistan to MediSafe's food data,
with their nutrients from USDA FoodData Central (the US Department of Agriculture's food database).

Run it from the modeltraining folder, with the venv active:
    python import_usda_foods.py

It writes data/foods_pakistan.json. Then retrain:  python train_model.py
Works with the public DEMO_KEY (30 requests an hour). For your own free key: https://api.data.gov/signup
and put USDA_API_KEY=... in backend/.env.
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "foods_pakistan.json")
ENV = os.path.join(os.path.dirname(HERE), ".env")


def api_key() -> str:
    if os.environ.get("USDA_API_KEY"):
        return os.environ["USDA_API_KEY"]
    if os.path.exists(ENV):
        with open(ENV, encoding="utf-8-sig") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k.strip() == "USDA_API_KEY" and v.strip():
                    return v.strip().strip('"')
    return "DEMO_KEY"


# name in the app → (exact USDA "SR Legacy" description, type, oxalate level, tannin level)
# Oxalate and tannin are not in USDA. Levels use the same 0-80 scale as foods_db.json
# (spinach 80 = very high, beets 40 = high, ≤10 = low), from published oxalate and polyphenol food lists.
FOODS = {
    "Okra (Bhindi)":             ("Okra, raw", "vegetable", 40, 0),
    "Eggplant (Baingan)":        ("Eggplant, raw", "vegetable", 10, 5),
    "Cauliflower (Gobhi)":       ("Cauliflower, raw", "vegetable", 5, 0),
    "Cabbage (Band Gobhi)":      ("Cabbage, raw", "vegetable", 3, 0),
    "Peas (Matar)":              ("Peas, green, raw", "vegetable", 5, 0),
    "Potato (Aloo)":             ("Potatoes, flesh and skin, raw", "vegetable", 25, 0),
    "Radish (Mooli)":            ("Radishes, oriental, raw", "vegetable", 5, 0),
    "Turnip (Shaljam)":          ("Turnips, raw", "vegetable", 5, 0),
    "Bitter Gourd (Karela)":     ("Balsam-pear (bitter gourd), pods, raw", "vegetable", 10, 5),
    "Bottle Gourd (Lauki)":      ("Gourd, white-flowered (calabash), raw", "vegetable", 3, 0),
    "Mustard Greens (Saag)":     ("Mustard greens, raw", "vegetable", 5, 0),
    "Green Chilli (Hari Mirch)": ("Peppers, hot chili, green, raw", "vegetable", 5, 0),
    "Dates (Khajoor)":           ("Dates, medjool", "fruit", 5, 10),
    "Figs (Anjeer)":             ("Figs, raw", "fruit", 10, 10),
    "Watermelon (Tarbooz)":      ("Watermelon, raw", "fruit", 0, 0),
    "Melon (Kharbooza)":         ("Melons, cantaloupe, raw", "fruit", 0, 0),
    "Grapes (Angoor)":           ("Grapes, red or green (European type, such as Thompson seedless), raw", "fruit", 3, 15),
    "Apricot (Khubani)":         ("Apricots, raw", "fruit", 3, 10),
    "Peach (Aaru)":              ("Peaches, yellow, raw", "fruit", 3, 5),
    "Plum (Aloo Bukhara)":       ("Plums, raw", "fruit", 5, 15),
    "Kinnow (Mandarin)":         ("Tangerines, (mandarin oranges), raw", "fruit", 5, 0),
    "Lychee":                    ("Litchis, raw", "fruit", 0, 5),
    "Jamun (Java Plum)":         ("Java-plum, (jambolan), raw", "fruit", 5, 30),
    "Chikoo (Sapodilla)":        ("Sapodilla, raw", "fruit", 5, 15),
    "Persimmon (Japani Phal)":   ("Persimmons, japanese, raw", "fruit", 5, 30),
    "Loquat (Lokat)":            ("Loquats, raw", "fruit", 5, 10),
    "Mulberry (Shahtoot)":       ("Mulberries, raw", "fruit", 5, 10),
}

# USDA nutrient number → (our column, how to put it on the foods_db.json scale; values are per 100 g)
NUTRIENTS = {
    "303": ("iron",        lambda v: v / 8 * 100),     # mg → % of 8 mg
    "401": ("vitamin_c",   lambda v: v),               # mg
    "301": ("calcium",     lambda v: v / 10),          # mg → % of 1000 mg
    "309": ("zinc",        lambda v: v / 11 * 100),    # mg → % of 11 mg
    "304": ("magnesium",   lambda v: v / 4),           # mg → % of 400 mg
    "430": ("vitamin_k",   lambda v: v),               # mcg
    "328": ("vitamin_d",   lambda v: v / 20 * 100),    # mcg → % of 20 mcg
    "418": ("vitamin_b12", lambda v: v / 2.4 * 100),   # mcg → % of 2.4 mcg
    "323": ("vitamin_e",   lambda v: v / 15 * 100),    # mg → % of 15 mg
    "851": ("omega3",      lambda v: v / 1.6 * 100),   # g ALA → % of 1.6 g
    "619": ("omega3",      lambda v: v / 1.6 * 100),
    "306": ("potassium",   lambda v: v / 10),          # mg ÷ 10
    "417": ("folate",      lambda v: v / 400 * 100),   # mcg → % of 400 mcg
}


def search(description: str, key: str) -> dict | None:
    q = urllib.parse.urlencode({"query": description, "dataType": "SR Legacy", "pageSize": 10, "api_key": key})
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?{q}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MediSafe-FYP/1.0"}),
                                        timeout=40) as r:
                foods = json.loads(r.read()).get("foods", [])
            exact = [f for f in foods if f.get("description", "").lower() == description.lower()]
            return (exact or foods or [None])[0]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("   ! USDA limit reached for this key. Get a free key at https://api.data.gov/signup "
                      "and add USDA_API_KEY=... to backend/.env, then run this again.")
                return "LIMIT"
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return None


def main():
    key = api_key()
    print(f"Reading {len(FOODS)} fruits and vegetables from USDA FoodData Central "
          f"({'your key' if key != 'DEMO_KEY' else 'DEMO_KEY'})…")
    out, missing = {}, []
    if os.path.exists(OUT):                             # keep foods saved last time; only fetch the missing ones
        with open(OUT, encoding="utf-8") as f:
            out = {k: v for k, v in json.load(f).items() if k in FOODS}
    limit_hit = False
    for name, (desc, kind, oxalate, tannin) in FOODS.items():
        if name in out:
            continue
        food = None if limit_hit else search(desc, key)
        limit_hit = limit_hit or food == "LIMIT"
        food = None if food == "LIMIT" else food
        if not food:
            missing.append(name)
            print(f"   ✗ {name}: not found")
            continue
        row = {col: 0 for col, _ in NUTRIENTS.values()}
        for n in food.get("foodNutrients", []):
            num = str(n.get("nutrientNumber", ""))
            if num in NUTRIENTS and n.get("value") is not None:
                col, scale = NUTRIENTS[num]
                row[col] = max(row[col], round(scale(float(n["value"])), 1))
        row.update(oxalate=oxalate, tannin=tannin, type=kind,
                   source=f"USDA FoodData Central fdcId {food.get('fdcId')} ({food.get('description')}); "
                          "oxalate/tannin from published food lists")
        out[name] = row
        print(f"   ✓ {name:28} iron {row['iron']:5}  vit C {row['vitamin_c']:5}  calcium {row['calcium']:5}  "
              f"vit K {row['vitamin_k']:5}")
        time.sleep(0.3)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\nSaved {len(out)} of {len(FOODS)} foods to {OUT}" + (f"  (missing: {', '.join(missing)})" if missing else ""))
    print("Next: python train_model.py")


if __name__ == "__main__":
    main()
