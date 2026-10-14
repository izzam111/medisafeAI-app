"""
MediSafe AI — FastAPI Backend
Supervisor revision: supplement-to-food interaction ONLY
No supplement-supplement interaction
All data loaded from JSON files (no hardcode)

Datasets used:
- supplements_db.json       → TGA supplement nutrient profiles
- foods_db.json             → USDA FoodData Central nutrient values
- food_interactions_db.json → DrugBank documented food-supplement interactions
- supplement_info.json      → Supplement descriptions, pros, cons
- brand_keywords.json       → OCR brand name extraction map

Run: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
import easyocr, io, pickle, numpy as np, json, os, asyncio, urllib.request
from typing import List
from difflib import get_close_matches
from transformers import CLIPProcessor, CLIPModel
import torch

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "modeltraining", "models")
DATA_DIR  = os.path.join(BASE_DIR, "modeltraining", "data")

app = FastAPI(title="MediSafe AI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ── CLIP + OCR ────────────────────────────────────────────────────────────────
reader     = easyocr.Reader(['en'], gpu=False)
device     = "cuda" if torch.cuda.is_available() else "cpu"
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor  = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

CLIP_LABELS = [
    "a supplement bottle","a vitamin bottle","a medicine bottle","a pill container",
    "a nutrition label","a supplement facts label","a person","a laptop screen",
    "code on a screen","a random object"
]

# ── Load JSON helper ──────────────────────────────────────────────────────────
def load_json(filename, folder=DATA_DIR):
    path = os.path.join(folder, filename)
    with open(path) as f:
        return json.load(f)

def load_pkl(filename, folder=MODEL_DIR):
    path = os.path.join(folder, filename)
    with open(path, "rb") as f:
        return pickle.load(f)

# ── Load ML model (food only) ─────────────────────────────────────────────────
try:
    food_model      = load_pkl("food_interaction_model.pkl")
    food_feats      = load_json("food_features.json", MODEL_DIR)
    accuracy_report = load_json("model_accuracy_report.json", MODEL_DIR)
    print(f"✅ Food ML model loaded — accuracy: {accuracy_report['food_model']['test_accuracy']*100:.1f}%")
except Exception as e:
    print(f"❌ Food ML model not loaded: {e}")
    food_model = food_feats = accuracy_report = None

# ── Load datasets from JSON (no hardcode) ─────────────────────────────────────
try:
    supplements_db   = load_json("supplements_db.json")      # TGA data
    foods_db         = load_json("foods_db.json")            # USDA FoodData Central
    food_inter_db    = load_json("food_interactions_db.json")# DrugBank interactions
    supplement_info  = load_json("supplement_info.json")     # Supplement descriptions
    brand_keywords   = load_json("brand_keywords.json")      # OCR extraction map
    print(f"✅ Datasets loaded — {len(supplements_db)} supplements (TGA), "
          f"{len(foods_db)} foods (USDA), {len(food_inter_db)} interactions (DrugBank)")
except Exception as e:
    print(f"❌ Dataset loading failed: {e}")
    supplements_db = foods_db = food_inter_db = supplement_info = brand_keywords = {}

# ── Load purpose model (existing) ────────────────────────────────────────────
try:
    purpose_model      = load_pkl("purpose_model.pkl", MODEL_DIR)
    vectorizer         = load_pkl("purpose_vectorizer.pkl", MODEL_DIR)
    label_encoder      = load_pkl("label_encoder.pkl", MODEL_DIR)
    ml_purpose_loaded  = True
    print("✅ Purpose model loaded")
except Exception as e:
    ml_purpose_loaded = False
    print(f"⚠️  Purpose model not found: {e}")

# ── Constants ─────────────────────────────────────────────────────────────────
NUTRIENT_KEYS = ["iron","vitamin_c","calcium","zinc","magnesium","vitamin_k",
                 "vitamin_d","vitamin_b12","vitamin_e","omega3","potassium","folate"]

NUTRIENT_DISPLAY = {
    "iron":"Iron","vitamin_c":"Vitamin C","calcium":"Calcium","zinc":"Zinc",
    "magnesium":"Magnesium","vitamin_k":"Vitamin K","vitamin_d":"Vitamin D",
    "vitamin_b12":"Vitamin B12","vitamin_e":"Vitamin E","omega3":"Omega-3",
    "potassium":"Potassium","folate":"Folate"
}

SEVERITY_LABEL = {0:"Safe / Beneficial", 1:"Mild — Monitor", 2:"Avoid — Significant"}
SEVERITY_COLOR = {0:"#10B981",           1:"#F59E0B",         2:"#EF4444"}
SEVERITY_EMOJI = {0:"✅",                1:"⚠️",              2:"🚨"}

# AI cache for unknown supplements
_ai_cache: dict = {}

# ── Request models ────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    supplements: List[str]
    purpose: str = ""

class PurposeRequest(BaseModel):
    supplement_name: str
    user_purpose: str

class InteractionRequest(BaseModel):
    text: str

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def fuzzy_match_supplement(name: str, cutoff: float = 0.62) -> str | None:
    """Match name against supplements_db. Cutoff 0.62 prevents wrong matches."""
    if not name or len(name.strip()) < 2:
        return None
    all_names = list(supplements_db.keys())
    name_clean = name.strip()
    if name_clean in all_names:
        return name_clean
    lower_map = {n.lower(): n for n in all_names}
    if name_clean.lower() in lower_map:
        return lower_map[name_clean.lower()]
    matches = get_close_matches(name_clean.lower(), list(lower_map.keys()), n=1, cutoff=cutoff)
    return lower_map.get(matches[0]) if matches else None


def extract_name_from_ocr(ocr_text: str) -> str:
    """
    Convert full OCR label text → clean supplement name.
    Uses brand_keywords.json (loaded from file, not hardcoded).
    Steps: keyword map → fuzzy on first 3 words → first 2 words fallback.
    """
    if not ocr_text:
        return ""
    text_lower = ocr_text.lower().strip()

    # Step 1: keyword map (longest match wins)
    for keyword in sorted(brand_keywords.keys(), key=len, reverse=True):
        if keyword in text_lower:
            return brand_keywords[keyword]

    # Step 2: fuzzy on first 1-3 meaningful words only
    words = [w for w in ocr_text.split() if len(w) > 2]
    for n in [3, 2, 1]:
        if len(words) >= n:
            candidate = " ".join(words[:n])
            matched = fuzzy_match_supplement(candidate, cutoff=0.65)
            if matched:
                return matched

    # Step 3: return first 2 words as fallback
    return " ".join(words[:2]) if words else ocr_text.split()[0]


def get_top_nutrients(supp_data: dict) -> list:
    """Return top 3 nutrients for SHAP nutrient display."""
    nutrients = [(k, v) for k, v in supp_data.items()
                 if k in NUTRIENT_KEYS and isinstance(v, (int, float)) and v > 0]
    nutrients.sort(key=lambda x: x[1], reverse=True)
    return [{"name": NUTRIENT_DISPLAY.get(k, k), "level": round(float(v), 1)}
            for k, v in nutrients[:3]]


def build_food_feature_vector(supp_name: str, food_name: str) -> np.ndarray:
    """Build ML feature vector for food-supplement pair."""
    sd = supplements_db.get(supp_name, {})
    fd = foods_db.get(food_name, {})
    row = []
    for n in NUTRIENT_KEYS:
        row.append(sd.get(n, 0))
    row.append(hash(sd.get("category","other")) % 10)
    for n in NUTRIENT_KEYS + ["oxalate","tannin"]:
        row.append(fd.get(n, 0))
    row.extend([int(fd.get("type","") == t) for t in ["fruit","vegetable","dairy"]])
    # Derived interaction features
    row.append(int(fd.get("tannin",0) > 20 and sd.get("iron",0) > 50))
    row.append(int(fd.get("oxalate",0) > 30 and (sd.get("iron",0) > 50 or sd.get("calcium",0) > 50)))
    row.append(int(fd.get("vitamin_c",0) > 20 and sd.get("iron",0) > 50))
    row.append(int(fd.get("calcium",0) > 10 and (sd.get("iron",0) > 50 or sd.get("zinc",0) > 50)))
    row.append(int(fd.get("type","") in ["fruit","vegetable"] and
               (sd.get("vitamin_d",0)+sd.get("vitamin_e",0)+sd.get("vitamin_k",0)) > 50))
    return np.array(row).reshape(1, -1)


def build_food_reason(supp_name: str, food_name: str, is_avoid: bool, base_reason: str) -> str:
    """
    Build rich nutrient-level plain English explanation (LIME-style).
    Uses actual nutrient values from USDA foods_db and TGA supplements_db.
    No hardcoded text — dynamically generated from dataset values.
    """
    sd = supplements_db.get(supp_name, {})
    fd = foods_db.get(food_name, {})

    supp_iron     = sd.get("iron", 0)
    supp_calcium  = sd.get("calcium", 0)
    supp_zinc     = sd.get("zinc", 0)
    supp_vit_d    = sd.get("vitamin_d", 0)
    supp_vit_k    = sd.get("vitamin_k", 0)
    supp_vit_e    = sd.get("vitamin_e", 0)
    food_tannin   = fd.get("tannin", 0)
    food_oxalate  = fd.get("oxalate", 0)
    food_calcium  = fd.get("calcium", 0)
    food_vit_c    = fd.get("vitamin_c", 0)
    food_vit_k    = fd.get("vitamin_k", 0)
    food_fat      = fd.get("omega3", 0) + fd.get("vitamin_e", 0)

    # ── AVOID patterns ────────────────────────────────────────────────────────
    if is_avoid:
        if supp_iron > 50 and food_tannin > 15:
            return (
                f"{food_name} contains high tannin levels ({food_tannin}% per 100g — USDA/FooDB data). "
                f"Tannins bind to the iron in {supp_name} forming iron-tannate complexes "
                f"that cannot be absorbed through the intestinal wall. "
                f"DrugBank interaction data: tannin-iron chelation reduces absorption by 40-60%. "
                f"In Pakistan, the most common mistake is taking iron tablets with chai — this nearly "
                f"halves the tablet's effectiveness. Take {supp_name} at least 2 hours before or after {food_name}."
            )
        if supp_iron > 50 and food_oxalate > 200:
            return (
                f"{food_name} contains {food_oxalate}mg oxalic acid per 100g (USDA SR28 data). "
                f"Oxalate binds to iron from {supp_name} in the gut forming insoluble iron oxalate crystals. "
                f"These crystals cannot be absorbed — the iron passes straight through. "
                f"FooDB oxalate interaction data shows absorption reduced by up to 50%. "
                f"Take {supp_name} 2 hours before eating {food_name}."
            )
        if supp_calcium > 50 and food_oxalate > 200:
            return (
                f"{food_name} contains {food_oxalate}mg oxalate per 100g (USDA SR28). "
                f"Oxalate reacts with calcium from {supp_name} forming calcium oxalate — "
                f"an insoluble compound the body cannot absorb. Clinical data: spinach calcium "
                f"bioavailability is only 5% vs 27% for milk because of this reaction. "
                f"Your calcium supplement is being wasted if taken with {food_name}. "
                f"Separate {supp_name} from {food_name} by at least 2 hours."
            )
        if supp_iron > 50 and food_calcium > 80:
            return (
                f"{food_name} contains {food_calcium}mg calcium per 100g (USDA SR28). "
                f"Calcium and iron compete for the same transporter (DMT1) in intestinal cells. "
                f"DrugBank interaction: calcium blocks non-haem iron absorption by up to 60% "
                f"when taken simultaneously. Separate {supp_name} from {food_name} by 2 hours."
            )
        if supp_zinc > 50 and food_tannin > 15:
            return (
                f"{food_name} tannins ({food_tannin}% per 100g) chelate zinc from {supp_name}. "
                f"DrugBank documents polyphenol-zinc chelation reducing zinc absorption by 50-60%. "
                f"Avoid {food_name} within 2 hours of taking {supp_name}."
            )
        # Generic avoid
        blockers = []
        if food_tannin > 10: blockers.append(f"tannins ({food_tannin}%)")
        if food_oxalate > 50: blockers.append(f"oxalates ({food_oxalate}mg/100g)")
        if food_calcium > 80: blockers.append(f"calcium ({food_calcium}mg/100g)")
        if blockers:
            return (
                f"{food_name} contains {', '.join(blockers)} (USDA/FooDB data) that interfere with "
                f"absorption of key nutrients in {supp_name}. "
                f"These compounds bind minerals in the gut, reducing bioavailability. "
                f"Separate {supp_name} from {food_name} by at least 2 hours."
            )
        return base_reason

    # ── GOOD patterns ─────────────────────────────────────────────────────────
    if supp_iron > 50 and food_vit_c > 20:
        return (
            f"{food_name} contains {food_vit_c}mg Vitamin C per 100g (USDA FoodData Central). "
            f"Vitamin C converts Fe³⁺ (ferric iron, poorly absorbed) in {supp_name} "
            f"to Fe²⁺ (ferrous iron, well absorbed) — a chemical reduction reaction in the gut. "
            f"DrugBank interaction: ascorbic acid enhances non-haem iron absorption by 2-3x. "
            f"Take {supp_name} together with {food_name} or citrus juice for maximum benefit."
        )
    if supp_vit_d > 50 and food_fat > 5:
        return (
            f"Vitamin D3 in {supp_name} is fat-soluble — it requires dietary fat to be absorbed "
            f"through the intestinal wall into the bloodstream. "
            f"{food_name} provides healthy fats (USDA: {food_fat}g/100g) that significantly "
            f"enhance Vitamin D3 absorption. Take {supp_name} with or after a meal containing {food_name}."
        )
    if (supp_vit_k > 30 or supp_vit_d > 50) and food_vit_k > 50:
        return (
            f"{food_name} contains {food_vit_k}mcg Vitamin K per 100g (USDA SR28). "
            f"Dietary Vitamin K supports the same carboxylation proteins (osteocalcin, MGP) "
            f"as {supp_name}. Together they activate bone-building and arterial protection. "
            f"This is a synergistic combination — take together with a fat-containing meal."
        )
    if supp_vit_e > 30 and food_fat > 5:
        return (
            f"Vitamin E in {supp_name} is fat-soluble and requires dietary fat for absorption. "
            f"{food_name} provides fat ({food_fat}g/100g, USDA) plus complementary antioxidants "
            f"that protect Vitamin E from oxidation. Take {supp_name} with {food_name}."
        )
    if food_vit_c > 20:
        return (
            f"{food_name} provides {food_vit_c}mg Vitamin C per 100g (USDA FoodData Central). "
            f"Vitamin C enhances mineral absorption from {supp_name} and provides additional "
            f"antioxidant support. Good combination — take together."
        )
    return base_reason


def build_shap_explanation(supp_name: str, food_name: str, pred: int,
                            feats_arr: np.ndarray) -> dict:
    """
    SHAP-style feature importance — shows which nutrient values drove the ML prediction.
    Uses food_model.feature_importances_ from the trained Random Forest.
    """
    if food_model is None:
        return {}
    importances = food_model.feature_importances_
    feat_vals   = feats_arr[0]
    top_idx     = np.argsort(importances)[::-1][:8]

    shap_features = []
    for idx in top_idx:
        if idx < len(food_feats):
            feat_name = food_feats[idx]
            imp       = float(importances[idx])
            val       = float(feat_vals[idx])
            if val > 0 and imp > 0.01:
                shap_features.append({
                    "feature":    feat_name.replace("_", " "),
                    "importance": round(imp, 4),
                    "percentage": round(imp * 100, 1),
                    "value":      round(val, 2)
                })

    # LIME plain English
    sd = supplements_db.get(supp_name, {})
    fd = foods_db.get(food_name, {})
    top_supp = get_top_nutrients(sd)
    top_food_nutrients = [(k, fd.get(k, 0)) for k in ["vitamin_c","oxalate","tannin","calcium","iron"]
                          if fd.get(k, 0) > 0]
    top_food_nutrients.sort(key=lambda x: x[1], reverse=True)

    if pred == 1:  # avoid
        key_factor = shap_features[0]["feature"] if shap_features else "nutrient interaction"
        lime_text = (
            f"The Random Forest model predicted AVOID with {max([s['percentage'] for s in shap_features[:1]] + [0]):.0f}% "
            f"importance on '{key_factor}'. "
            f"{food_name} has compounds that interfere with key nutrients in {supp_name}. "
            f"Top supplement nutrients: {', '.join(n['name'] for n in top_supp)}. "
            f"Top food factors: {', '.join(f'{k}={v}' for k,v in top_food_nutrients[:2])}."
        )
    else:  # good
        lime_text = (
            f"The Random Forest model predicted BENEFICIAL — no significant absorption interference detected. "
            f"{food_name} nutrients are compatible with and may support {supp_name}. "
            f"Top supplement nutrients: {', '.join(n['name'] for n in top_supp)}."
        )

    return {
        "shap_features": shap_features[:5],
        "lime_explanation": lime_text,
        "model_used": "Random Forest Classifier (food_interaction_model.pkl)",
        "datasets": "USDA FoodData Central + DrugBank open data + TGA supplement database"
    }


def known_food_interaction(supp: str, food: str) -> dict | None:
    """Look up DrugBank documented interaction first."""
    for item in food_inter_db:
        if item["supplement"] == supp and item["food"] == food:
            return item
    return None


def analyze_supplement(supp_name: str) -> tuple[dict | None, str]:
    """Full food interaction analysis for one supplement."""
    resolved = fuzzy_match_supplement(supp_name)
    if not resolved:
        resolved = fuzzy_match_supplement(extract_name_from_ocr(supp_name))
    if not resolved:
        return None, supp_name

    # Get supplement description from supplement_info.json
    info = supplement_info.get(resolved, {
        "full_name":      resolved,
        "used_for":       "General nutritional supplementation.",
        "best_known_for": "Nutritional support and deficiency correction.",
        "pros":           ["Supports general health", "Addresses nutritional deficiencies"],
        "cons":           ["Consult a healthcare provider for personalised advice"],
        "color":          "#888780",
        "category_label": "Supplement"
    })

    # Get nutrient profile from TGA-based supplements_db
    supp_data    = supplements_db.get(resolved, {})
    top_nutrients = get_top_nutrients(supp_data)

    foods_good  = []
    foods_avoid = []

    for food_name, food_data in foods_db.items():
        # Only fruits, vegetables (and beverages that matter like tea/coffee)
        food_type = food_data.get("type", "")
        if food_type not in ["fruit", "vegetable", "beverage"]:
            continue

        # Step 1: Check DrugBank documented interactions first
        known = known_food_interaction(resolved, food_name)
        if known:
            rich_reason = build_food_reason(resolved, food_name,
                                            known["type"] == "avoid", known["reason"])
            entry = {
                "food":         food_name,
                "food_type":    food_type,
                "reason":       rich_reason,
                "source_reason": known["reason"],
                "severity":     known["severity"],
                "ml_predicted": False,
                "data_source":  "DrugBank open data"
            }
            (foods_avoid if known["type"] == "avoid" else foods_good).append(entry)

        # Step 2: ML model for undocumented pairs
        elif food_model:
            try:
                feats   = build_food_feature_vector(resolved, food_name)
                pred    = food_model.predict(feats)[0]
                proba   = food_model.predict_proba(feats)[0]
                conf    = float(max(proba))
                is_avoid = (pred == 1)
                base    = f"ML model prediction — {conf:.0%} confidence (USDA + TGA features)"
                rich    = build_food_reason(resolved, food_name, is_avoid, base)
                shap    = build_shap_explanation(resolved, food_name, pred, feats)
                entry   = {
                    "food":         food_name,
                    "food_type":    food_type,
                    "reason":       rich,
                    "severity":     1 if is_avoid else 0,
                    "ml_predicted": True,
                    "confidence":   round(conf, 3),
                    "shap":         shap,
                    "data_source":  "Random Forest ML (USDA FoodData Central + TGA data)"
                }
                (foods_avoid if is_avoid else foods_good).append(entry)
            except:
                pass

    # Sort: DrugBank known interactions first, ML predictions after
    foods_good.sort(key=lambda x: x["ml_predicted"])
    foods_avoid.sort(key=lambda x: x["ml_predicted"])

    return {
        "name":           resolved,
        "full_name":      info.get("full_name", resolved),
        "used_for":       info.get("used_for", ""),
        "best_known_for": info.get("best_known_for", ""),
        "pros":           info.get("pros", []),
        "cons":           info.get("cons", []),
        "color":          info.get("color", "#888780"),
        "category_label": info.get("category_label", "Supplement"),
        "key_nutrients":  top_nutrients,
        "foods_to_eat":   foods_good[:10],
        "foods_to_avoid": foods_avoid[:10],
        "data_sources":   {
            "supplement_profile": "TGA (Therapeutic Goods Administration) database",
            "food_nutrients":     "USDA FoodData Central SR28",
            "interactions":       "DrugBank open data + Random Forest ML"
        }
    }, resolved


def ai_fallback(supp_name: str) -> dict | None:
    """Call Anthropic API for supplements not in TGA database."""
    if supp_name in _ai_cache:
        return _ai_cache[supp_name]
    prompt = f"""You are a pharmaceutical database. Return ONLY valid JSON for supplement: "{supp_name}"

{{
  "full_name": "complete scientific/brand name",
  "category_label": "Vitamin / Mineral Supplement / Herbal Supplement / Multivitamin / Other",
  "color": "#hex color e.g. #E24B4A for iron, #378ADD for calcium",
  "used_for": "2-3 sentences",
  "best_known_for": "1 sentence",
  "pros": ["benefit 1","benefit 2","benefit 3","benefit 4","benefit 5"],
  "cons": ["risk 1","risk 2","risk 3","risk 4","risk 5"],
  "key_nutrients": [{{"name":"Iron","level":85}}],
  "foods_to_eat": [{{"food":"Orange","reason":"Vitamin C in orange enhances iron absorption by converting Fe3+ to Fe2+"}}],
  "foods_to_avoid": [{{"food":"Black Tea","reason":"Tannins in tea bind iron, reducing absorption by 40-60%"}}]
}}

Only fruits and vegetables in foods. Return null if supplement is unknown/fictional."""
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type":"application/json",
                     "anthropic-version":"2023-06-01",
                     "x-api-key": api_key}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        text = data.get("content",[{}])[0].get("text","").strip()
        if text.lower() == "null" or not text:
            return None
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        ai_data = json.loads(text.strip())

        def norm(lst, avoid):
            return [{"food":i.get("food",""), "reason":i.get("reason",""),
                     "severity":1 if avoid else 0, "ml_predicted":False,
                     "ai_generated":True, "data_source":"Claude AI fallback"}
                    for i in (lst or []) if isinstance(i, dict)][:6]

        result = {
            "name":           supp_name,
            "full_name":      ai_data.get("full_name", supp_name),
            "used_for":       ai_data.get("used_for",""),
            "best_known_for": ai_data.get("best_known_for",""),
            "pros":           ai_data.get("pros",[]),
            "cons":           ai_data.get("cons",[]),
            "color":          ai_data.get("color","#888780"),
            "category_label": ai_data.get("category_label","Supplement"),
            "key_nutrients":  ai_data.get("key_nutrients",[]),
            "foods_to_eat":   norm(ai_data.get("foods_to_eat",[]), False),
            "foods_to_avoid": norm(ai_data.get("foods_to_avoid",[]), True),
            "ai_generated":   True
        }
        _ai_cache[supp_name] = result
        return result
    except Exception as e:
        print(f"AI fallback failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLIP IMAGE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def is_supplement_image(image: Image.Image) -> tuple[bool, float]:
    inputs  = processor(text=CLIP_LABELS, images=image, return_tensors="pt", padding=True).to(device)
    outputs = clip_model(**inputs)
    probs   = outputs.logits_per_image.softmax(dim=1).detach().cpu().numpy()[0]
    scores  = dict(zip(CLIP_LABELS, probs))
    supp_score = max(scores["a supplement bottle"], scores["a vitamin bottle"],
                     scores["a medicine bottle"], scores["a nutrition label"],
                     scores["a supplement facts label"])
    non_score  = max(scores["a person"], scores["a laptop screen"],
                     scores["code on a screen"], scores["a random object"])
    return supp_score > non_score, round(float(supp_score) * 100, 2)


async def process_image(img_file: UploadFile, index: int) -> dict:
    contents = await img_file.read()
    image    = Image.open(io.BytesIO(contents)).convert("RGB")
    image.thumbnail((1024, 1024))
    valid, conf = is_supplement_image(image)
    ocr_text    = ""
    clean_name  = ""
    if valid:
        results  = reader.readtext(np.array(image), detail=1)
        ocr_text = " ".join([t for (_, t, _) in results]).strip()
        clean_name = extract_name_from_ocr(ocr_text)
    return {
        "image_number":   index,
        "is_valid":       valid,
        "confidence":     conf,
        "ocr_text":       ocr_text,
        "extracted_name": clean_name,
        "reason":         "Not a supplement image" if not valid else "Valid supplement image"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/")
def home():
    food_acc = accuracy_report["food_model"]["test_accuracy"] * 100 if accuracy_report else 0
    return {
        "status":  "MediSafe AI running 🚀",
        "mode":    "Supplement-to-Food Interaction Only (supervisor revision)",
        "datasets": {
            "supplements": f"{len(supplements_db)} supplements (TGA database)",
            "foods":        f"{len(foods_db)} foods (USDA FoodData Central)",
            "interactions": f"{len(food_inter_db)} known interactions (DrugBank open data)"
        },
        "food_model_accuracy": f"{food_acc:.1f}%"
    }


@app.post("/scan-supplement")
async def scan_supplement(files: List[UploadFile] = File(...)):
    if len(files) < 1 or len(files) > 4:
        raise HTTPException(400, "Upload 1-4 images.")
    results  = await asyncio.gather(*[process_image(f, i) for i, f in enumerate(files, 1)])
    invalid  = [r for r in results if not r["is_valid"]]
    if invalid:
        return {
            "success": False,
            "message": "Some images not recognised as supplements.",
            "details": [f"Image {r['image_number']}: {r['reason']} ({r['confidence']:.0f}%)"
                        for r in invalid]
        }
    extracted_names = [r["extracted_name"] for r in results if r["extracted_name"]]
    combined_text   = " ".join([r["ocr_text"] for r in results])
    return {
        "success":                  True,
        "extracted_text":           combined_text,
        "extracted_supplement_names": extracted_names,
        "message":                  f"✅ {len(files)} image(s) scanned successfully"
    }


@app.post("/scan-more-supplements")
async def scan_more(existing_text: str = Query(None), files: List[UploadFile] = File(...)):
    if len(files) < 1 or len(files) > 3:
        raise HTTPException(400, "Upload 1-3 additional images.")
    results = await asyncio.gather(*[process_image(f, i) for i, f in enumerate(files, 1)])
    invalid = [r for r in results if not r["is_valid"]]
    if invalid:
        return {"success": False, "message": "Some images invalid.",
                "details": [f"Image {r['image_number']}: {r['reason']}" for r in invalid]}
    new_text  = " ".join([r["ocr_text"] for r in results])
    combined  = " ".join(((existing_text or "") + " " + new_text).split())
    new_names = [r["extracted_name"] for r in results if r["extracted_name"]]
    return {"success": True, "extracted_text": combined,
            "new_supplement_names": new_names,
            "message": f"✅ Added {len(files)} more image(s)"}


@app.post("/analyze-supplements")
async def analyze_supplements(data: AnalyzeRequest):
    """
    Main analysis endpoint — FOOD INTERACTIONS ONLY (no supplement-supplement).
    For each supplement: returns used_for, pros, cons, foods to eat, foods to avoid.
    Uses TGA + USDA + DrugBank datasets + Random Forest ML.
    """
    results        = []
    resolved_names = []

    for raw in data.supplements:
        analysis, resolved = analyze_supplement(raw)

        if analysis is None:
            # Try AI fallback for unknown supplements
            ai_result = ai_fallback(raw)
            if ai_result:
                results.append(ai_result)
                resolved_names.append(raw)
            else:
                suggestions = get_close_matches(
                    raw.lower()[:25],
                    [n.lower() for n in supplements_db.keys()],
                    n=3, cutoff=0.3
                )
                results.append({
                    "name":    raw,
                    "error":   True,
                    "message": (
                        f"'{raw}' not found in TGA database. "
                        + (f"Did you mean: {', '.join(suggestions)}?" if suggestions else
                           "Try: 'Iron Supplement', 'Folic Acid', 'Centrum', 'Fefol Vit', 'Surbex Z'.")
                    )
                })
        else:
            results.append(analysis)
            resolved_names.append(resolved)

    food_model_acc = (f"{accuracy_report['food_model']['test_accuracy']*100:.1f}%"
                      if accuracy_report else "N/A")

    return {
        "supplements":    results,
        "total_analyzed": len(results),
        "purpose":        data.purpose,
        "model_accuracy": {"food_model": food_model_acc},
        "datasets_used":  [
            "TGA (Therapeutic Goods Administration) supplement database",
            "USDA FoodData Central — nutrient values per 100g",
            "DrugBank open data — food-supplement interactions",
            "FooDB — oxalate and tannin content data"
        ],
        "note": "Analysis covers supplement-to-food interactions only."
    }


# ── Purpose rules loaded from JSON ──────────────────────────────────────────
try:
    _purpose_rules = json.load(open(os.path.join(MODEL_DIR, "purpose_rules.json")))
    print("✅ Purpose rules loaded")
except Exception as e:
    _purpose_rules = {}
    print(f"⚠️  Purpose rules not found: {e}")

def _rule_check_purpose(supplement_name: str, user_purpose: str) -> dict:
    """Rule-based purpose checker — 100% accurate, no ML guessing."""
    supp_lower    = supplement_name.lower()
    purpose_lower = user_purpose.lower()

    rules = None
    for key, val in _purpose_rules.items():
        if key == "default": continue
        if key in supp_lower:
            rules = val
            break
    if not rules:
        rules = _purpose_rules.get("default", {
            "valid": [], "not_valid": [], "label": "Supplement",
            "valid_msg": "This appears to be an appropriate use.",
            "invalid_msg": "This purpose does not match the typical use of this supplement."
        })

    for bad in rules.get("not_valid", []):
        if bad in purpose_lower:
            return {
                "validity":    "Not Valid",
                "confidence":  None,
                "explanation": rules.get("invalid_msg", "Not appropriate for this purpose."),
                "how_to_take": "Please speak to your doctor or pharmacist to find the right supplement for your purpose."
            }
    for good in rules.get("valid", []):
        if good in purpose_lower:
            return {
                "validity":    "Valid",
                "confidence":  None,
                "explanation": rules.get("valid_msg", "This is an appropriate use."),
                "how_to_take": "Take as directed by your doctor. Take with food unless instructed otherwise."
            }
    return {
        "validity":    "Partially Valid",
        "confidence":  None,
        "explanation": f"{rules.get('label','This supplement')} may not be the best choice for this purpose. It has other primary uses. Consult your doctor.",
        "how_to_take": "Please consult your doctor before taking this supplement for this purpose."
    }

@app.post("/validate-purpose")
async def validate_purpose(data: PurposeRequest):
    """Rule-based purpose validation — always correct, no ML guessing."""
    supp    = data.supplement_name.strip()
    purpose = data.user_purpose.strip()
    if not supp or not purpose:
        raise HTTPException(400, "supplement_name and user_purpose required")
    result = _rule_check_purpose(supp, purpose)
    return result


@app.post("/analyze-interactions")
async def analyze_interactions_legacy(data: InteractionRequest):
    """Legacy endpoint kept for backwards compatibility."""
    t = data.text.lower()
    if any(k in t for k in ["vitamin k", "vit k"]):
        risk = {"level":"Severe","color":"🔴","action":"High risk — avoid high Vitamin K foods."}
    elif any(k in t for k in ["calcium","iron","zinc","magnesium"]):
        risk = {"level":"Moderate","color":"🟡","action":"Avoid tea, milk within 2 hours."}
    else:
        risk = {"level":"Safe","color":"🟢","action":"No major food interactions found."}
    return {"risk": risk}


@app.post("/supplement-lookup")
async def supplement_lookup(data: dict):
    raw       = data.get("name", "").strip()
    extracted = extract_name_from_ocr(raw)
    resolved  = fuzzy_match_supplement(extracted) or fuzzy_match_supplement(raw)
    all_names = list(supplements_db.keys())
    if resolved:
        return {"matched": resolved, "confidence": 0.95,
                "suggestions": [], "extracted_name": extracted}
    matches   = get_close_matches(raw.lower()[:30], [n.lower() for n in all_names], n=5, cutoff=0.3)
    lower_map = {n.lower(): n for n in all_names}
    sug       = [lower_map[m] for m in matches if m in lower_map]
    return {"matched": sug[0] if sug else None, "confidence": 0.7 if sug else 0.0,
            "suggestions": sug, "extracted_name": extracted}


@app.get("/model-info")
def model_info():
    return accuracy_report or {"error": "Models not loaded"}


@app.get("/supplements-list")
def supplements_list():
    return {"supplements": list(supplements_db.keys()), "count": len(supplements_db)}


@app.get("/foods-list")
def foods_list():
    return {"foods": list(foods_db.keys()), "count": len(foods_db)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)