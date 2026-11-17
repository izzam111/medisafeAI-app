"""
import_dsld.py — adds real supplement labels from the NIH Dietary Supplement Label Database (DSLD)
to MediSafe's dataset.

DSLD is run by the NIH Office of Dietary Supplements: https://dsld.od.nih.gov  (free, no key needed).
For each product it gives the brand, maker, every ingredient with its amount per serving,
the directions and the warnings printed on the label.

Run it from the backend folder, with the venv active:
    python modeltraining/import_dsld.py

It writes modeltraining/data/dsld_products.json. Restart the backend afterwards.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
import personal_check as pc                         # same nutrient names, units and limits the app uses

API = "https://api.ods.od.nih.gov/dsld/v9"
OUT = os.path.join(BACKEND, "modeltraining", "data", "dsld_products.json")
PER_TERM = 25                                       # products kept per search term (keeps us under 1000 requests)
CACHE = os.path.join(BACKEND, "modeltraining", "data", "dsld_cache.json")   # labels already downloaded


def api_key() -> str | None:
    """NIH's API runs on api.data.gov: the same free key as USDA (api.data.gov/signup)."""
    for name in ("DATA_GOV_API_KEY", "USDA_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    env = os.path.join(BACKEND, ".env")
    if os.path.exists(env):
        with open(env, encoding="utf-8-sig") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k.strip() in ("DATA_GOV_API_KEY", "USDA_API_KEY") and v.strip().strip('"').strip("'"):
                    return v.strip().strip('"').strip("'")
    return None


KEY = api_key()


class RateLimited(Exception):
    pass

# What we search for: the nutrients and herbs MediSafe can check, plus big brands sold in Pakistan.
TERMS = [
    "vitamin d3", "vitamin c", "vitamin b12", "vitamin e", "vitamin a", "vitamin k2", "b complex", "biotin",
    "folic acid", "iron", "calcium", "calcium vitamin d", "zinc", "magnesium", "potassium", "multivitamin",
    "multivitamin women", "multivitamin men", "prenatal", "fish oil", "omega-3", "coq10", "melatonin",
    "ashwagandha", "turmeric", "ginger", "garlic", "moringa", "spirulina", "psyllium",
    "Centrum", "Nature Made", "Nature's Bounty", "GNC", "Solgar", "NOW Foods", "Seven Seas", "Blackmores",
]

# Herbs and other non-vitamin ingredients → the matching entry in supplement_info.json
HERBS = {
    r"ashwagandha|withania": "Ashwagandha", r"turmeric|curcumin": "Turmeric/Curcumin", r"\bginger\b": "Ginger Extract",
    r"\bgarlic\b": "Garlic Extract", r"moringa": "Moringa (Sohanjna)", r"spirulina": "Spirulina",
    r"melatonin": "Melatonin", r"fish oil|omega-?3|\bepa\b|\bdha\b": "Omega-3 Fish Oil",
    r"coenzyme q|coq10|ubiquinol": "Coenzyme Q10", r"psyllium": "Ispaghol (Psyllium Husk)", r"senna": "Senna (Seena)",
    r"bitter melon": "Karela (Bitter Melon)", r"nigella|black seed": "Nigella Sativa (Kalonji)",
    r"\bamla\b|emblica": "Amla (Indian Gooseberry)", r"shilajit": "Shilajit",
}
# Main nutrient → the matching entry in supplement_info.json (what it's used for, side effects)
NUTRIENT_INFO = {
    "iron": "Iron Supplement", "calcium": "Calcium Supplement", "vitamin_d": "Vitamin D3", "vitamin_c": "Vitamin C",
    "zinc": "Zinc Supplement", "magnesium": "Magnesium", "potassium": "Potassium", "biotin": "Biotin",
    "vitamin_b12": "Vitamin B12", "folate": "Folic Acid", "vitamin_a": "Vitamin A", "vitamin_e": "Vitamin E",
    "vitamin_k": "Vitamin K2",
}


def get(path: str, **params) -> dict | None:
    if KEY:
        params["api_key"] = KEY
    url = f"{API}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MediSafe-FYP/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimited()
            if attempt == 2:
                print(f"   ! {path}: HTTP {e.code}")
        except Exception as e:
            if attempt == 2:
                print(f"   ! {path}: {e.__class__.__name__}")
        time.sleep(1.5 * (attempt + 1))
    return None


def hits_of(data) -> list:
    if not data:
        return []
    hits = data.get("hits", [])
    if isinstance(hits, dict):                      # elasticsearch style {"hits": {"hits": [...]}}
        hits = hits.get("hits", [])
    return hits


def rows(ingredient_rows: list):
    for row in ingredient_rows or []:
        yield row
        yield from rows(row.get("nestedRows"))


def nutrient_of(row: dict) -> str | None:
    text = f"{row.get('ingredientGroup') or ''} {row.get('name') or ''}".lower()
    for key, pattern in pc.NAMES.items():
        if re.search(pattern, text, re.I):
            return key
    return None


def amount_of(row: dict, nutrient: str) -> float | None:
    for q in row.get("quantity") or []:
        try:
            value = float(q.get("quantity"))
        except (TypeError, ValueError):
            continue
        unit = (q.get("unit") or "").split()[0].lower() if q.get("unit") else ""
        if value > 0 and unit:
            return pc._to_unit(value, unit, nutrient)
    return None


def text_of(label: dict) -> str:
    """Directions, warnings and other statements printed on the label, as one text."""
    parts = []
    for st in label.get("statements") or []:
        kind, notes = str(st.get("type") or ""), str(st.get("notes") or "")
        if notes:
            parts.append(f"{kind}: {notes}" if kind else notes)
    return " ".join(parts)[:1500]


def maker_of(label: dict) -> str | None:
    for c in label.get("contacts") or []:
        d = c.get("contactDetails") or c
        if d.get("name"):
            return str(d["name"]).strip()
    return None


def convert(label: dict) -> dict | None:
    brand, full = (label.get("brandName") or "").strip(), (label.get("fullName") or "").strip()
    if not full or label.get("offMarket") in (1, True, "1"):
        return None
    name = full if full.lower().startswith(brand.lower()) else f"{brand} {full}".strip()
    name = re.sub(r"\s+", " ", name)[:70]

    strength, herbs, names = {}, [], []
    for row in rows(label.get("ingredientRows")):
        names.append(row.get("name") or "")
        n = nutrient_of(row)
        if n and n not in strength:
            amount = amount_of(row, n)
            if amount:
                strength[n] = round(amount, 3)
        text = f"{row.get('ingredientGroup') or ''} {row.get('name') or ''}"
        herbs += [key for pattern, key in HERBS.items() if re.search(pattern, text, re.I) and key not in herbs]
    if not strength and not herbs:
        return None                                 # nothing MediSafe can check

    lower = name.lower()
    if "prenatal" in lower or "pregnan" in lower:
        group, info = "prenatal", "Prenatal Vitamin"
    elif herbs and len(strength) <= 1:
        group, info = "herbal", herbs[0]
    elif "iron" in strength and len(strength) <= 4:
        group, info = "iron", "Iron Supplement"
    elif len(strength) >= 5:
        group, info = "vitamin_mineral", "Multivitamin"
    else:
        need = lambda n: pc.daily_need(n, {"age": 30, "sex": "female", "periods": "yes", "pregnant": False,
                                           "breastfeeding": False}) or 1e9
        main = max(strength, key=lambda n: strength[n] / need(n))       # the nutrient with the biggest dose
        group, info = "vitamin_mineral", NUTRIENT_INFO.get(main, "Multivitamin")

    serving = (label.get("servingSizes") or [{}])[0]
    per = serving.get("minQuantity") or serving.get("quantity")
    unit = serving.get("unit") or ""
    return {
        "id": label.get("id"), "name": name, "brand": brand, "maker": maker_of(label),
        "group": group, "info_key": info, "nutrients": list(strength), "strength": strength, "herbs": herbs,
        "serving": f"{per:g} {unit}".strip() if isinstance(per, (int, float)) else None,
        "label_text": text_of(label), "source": f"NIH DSLD label {label.get('id')}",
    }


def main():
    print("Searching the NIH Dietary Supplement Label Database"
          + (" (with your api.data.gov key)…" if KEY else " (no key: the limit is small, add USDA_API_KEY to backend/.env)…"))
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    ids = dict.fromkeys(cache.get("_ids", []))
    stopped = False
    try:
        if not ids:
            for term in TERMS:
                found = hits_of(get("search-filter", q=term, size=PER_TERM, status=1))
                for h in found:
                    if h.get("_id"):
                        ids.setdefault(str(h["_id"]))
                print(f"   {term:22} {len(found)} products found")
            cache["_ids"] = list(ids)
        todo = [i for i in ids if i not in cache]
        print(f"{len(ids)} products, {len(ids) - len(todo)} already downloaded, reading {len(todo)} labels…")
        def fetch(i):
            if stopped:
                return
            label = get(f"label/{i}")
            if label:
                cache[i] = label
        with ThreadPoolExecutor(2) as pool:
            for n, _ in enumerate(pool.map(fetch, todo), 1):
                if n % 100 == 0:
                    print(f"   {n}/{len(todo)}")
    except RateLimited:
        stopped = True
        print("\n   ! NIH says: rate limit reached. Run this again later (it carries on where it stopped),"
              "\n     or add your free api.data.gov key as USDA_API_KEY=... in backend/.env.")
    finally:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    labels = [v for k, v in cache.items() if k != "_ids"]
    products, seen = [], set()
    for label in labels:
        p = convert(label) if label else None
        if p and p["name"].lower() not in seen:
            seen.add(p["name"].lower())
            products.append(p)
    products.sort(key=lambda p: p["name"].lower())
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"_about": "Supplement labels from the NIH Office of Dietary Supplements' Dietary Supplement Label "
                             "Database (DSLD), https://dsld.od.nih.gov. Imported by import_dsld.py.",
                   "imported": time.strftime("%Y-%m-%d"), "products": products}, f, indent=1, ensure_ascii=False)
    groups = {}
    for p in products:
        groups[p["group"]] = groups.get(p["group"], 0) + 1
    print(f"\nSaved {len(products)} products to {OUT}")
    print("By type:", groups)
    print("Restart the backend to use them.")


if __name__ == "__main__":
    main()
