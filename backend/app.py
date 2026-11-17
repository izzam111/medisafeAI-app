"""
MediSafe AI — FastAPI Backend

Flow:
  1. Scan & Search   CLIP validates the photo is a supplement → EasyOCR reads the label
                     → brand + manufacturer identified (Claude vision only if OCR can't read them)
  2. Company check   manufacturer must be in verified_companies.json (counterfeit guard)
  3. Personal check  age, sex, periods, pregnancy vs. label + datasets (personal_check.py)
  4. AI module       profile + label + personal check + reasons → Claude → safety report
  5. Accounts + DB   Firebase: login (Authentication), profile + search_query_data + search_response (Firestore)

Datasets (modeltraining/data): supplements_db (TGA), foods_db (USDA), food_interactions_db (DrugBank),
supplement_info, brand_keywords, verified_companies. Food model: Random Forest (food_interaction_model.pkl).

Run: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import base64, datetime, io, json, os, pickle, re, time, urllib.error, urllib.parse, urllib.request, uuid
from difflib import SequenceMatcher, get_close_matches
from typing import List, Literal, Optional

import easyocr, numpy as np, torch
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from transformers import CLIPModel, CLIPProcessor

import personal_check

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR  = os.path.join(BASE_DIR, "debug")
MODEL_DIR  = os.path.join(BASE_DIR, "modeltraining", "models")
DATA_DIR   = os.path.join(BASE_DIR, "modeltraining", "data")

# AI keys (ANTHROPIC_API_KEY or GEMINI_API_KEY) from backend/.env — one KEY=value per line
_env = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env):
    with open(_env, encoding="utf-8-sig") as f:
        for line in f:
            k, sep, v = line.strip().partition("=")
            if sep and k.strip() and not k.startswith("#"):
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Firebase — service account key saved as backend/firebase-key.json (never upload it; .gitignore covers it)
FIREBASE_KEY = os.path.join(BASE_DIR, "firebase-key.json")
TESTING = os.environ.get("MEDISAFE_TESTING") == "1"      # set by tests/: no Firebase writes, no AI calls
USE_FIREBASE = os.path.exists(FIREBASE_KEY) and not TESTING
if USE_FIREBASE:
    import firebase_admin
    from firebase_admin import auth as fb_auth, credentials, firestore
    firebase_admin.initialize_app(credentials.Certificate(FIREBASE_KEY))
    fs = firestore.client()
    print("✅ Firebase connected — accounts, profiles and history are saved")
elif TESTING:
    print("🧪 Test mode — Firebase and AI are switched off")
else:
    print("⚠️  backend/firebase-key.json not found — running WITHOUT accounts and database")
_scans: dict = {}   # scan results waiting for the report (kept in memory)

app = FastAPI(title="MediSafe AI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ── CLIP + OCR ────────────────────────────────────────────────────────────────
reader     = easyocr.Reader(["en"], gpu=False)
device     = "cuda" if torch.cuda.is_available() else "cpu"
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor  = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

CLIP_VALID = [
    "a photo of a supplement bottle", "a photo of a vitamin bottle", "a photo of a medicine bottle",
    "a photo of a medicine box", "a photo of a blister pack of tablets", "a photo of a sachet of medicine",
    "a photo of a supplement facts label", "a photo of a medicine label",
]
CLIP_INVALID = [
    "a photo of a person", "a photo of a face", "a photo of an animal", "a photo of food on a plate",
    "a photo of a drink", "a photo of a computer screen", "a photo of a mobile phone",
    "a photo of a document or paper", "a photo of a book", "a photo of a room", "a photo of a landscape",
    "a photo of a vehicle", "a photo of clothing", "a photo of a toy",
    "a photo of a cosmetic or beauty product", "a photo of a household object",
]
CLIP_LABELS = CLIP_VALID + CLIP_INVALID

# ── Data + model ──────────────────────────────────────────────────────────────
def load_json(filename, folder=DATA_DIR):
    with open(os.path.join(folder, filename), encoding="utf-8") as f:
        return json.load(f)

supplements_db     = load_json("supplements_db.json")
foods_db           = load_json("foods_db.json")
food_inter_db      = load_json("food_interactions_db.json")
supplement_info    = load_json("supplement_info.json")
_keywords          = load_json("brand_keywords.json")
BRANDS             = _keywords["brands"]        # "neurobion" → {"name": "Neurobion", "dataset": "Neurobion"}
INGREDIENTS        = _keywords["ingredients"]   # "ferrous sulphate" → "Iron Supplement"
verified_companies = load_json("verified_companies.json")
accuracy_report    = load_json("model_accuracy_report.json", MODEL_DIR)
with open(os.path.join(MODEL_DIR, "food_interaction_model.pkl"), "rb") as f:
    food_model = pickle.load(f)

# Real labels from the NIH Dietary Supplement Label Database (made by modeltraining/import_dsld.py).
# Each one becomes a product the rules engine can check, with its own strength per serving.
DSLD = {}
if os.path.exists(os.path.join(DATA_DIR, "dsld_products.json")):
    for _p in load_json("dsld_products.json")["products"]:
        DSLD[_p["name"]] = _p
        personal_check.PRODUCTS.setdefault(_p["name"], {"group": _p["group"], "nutrients": _p["nutrients"],
                                                        "typical_strength": _p["strength"]})
        if _p["info_key"] in supplement_info:
            supplement_info.setdefault(_p["name"], supplement_info[_p["info_key"]])
    print(f"📚 NIH label database: {len(DSLD)} products loaded")
DSLD_LOWER = {k.lower(): k for k in DSLD}

NUTRIENT_KEYS = ["iron", "vitamin_c", "calcium", "zinc", "magnesium", "vitamin_k",
                 "vitamin_d", "vitamin_b12", "vitamin_e", "omega3", "potassium", "folate"]
CATEGORY_CODE = {"mineral": 0, "vitamin": 1, "multi": 2, "fatty_acid": 3,   # must match build_dataset.py
                 "antioxidant": 4, "herbal": 5, "hormone": 6, "other": 7}

# ── Logged-in user ────────────────────────────────────────────────────────────
def current_user(authorization: str = Header(None)) -> str:
    """The app sends 'Authorization: Bearer <Firebase ID token>'. Returns the user's Firebase uid."""
    if not USE_FIREBASE:
        return "local"
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please log in again.")
    try:
        return fb_auth.verify_id_token(authorization.split(" ", 1)[1])["uid"]
    except Exception:
        raise HTTPException(401, "Your login has expired. Please log in again.")


def thumbnail(image: Image.Image) -> str:
    """Small JPEG of the scanned pack, stored as the supervisor's Input_Image field (about 15 KB)."""
    img = image.copy()
    img.thumbnail((320, 320))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

# ═══════════════════════════════════════════════════════════════════════════════
# LABEL READING — brand, ingredients, manufacturer
# ═══════════════════════════════════════════════════════════════════════════════

def norm(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    return " ".join(re.sub(r"[^a-z0-9&]+", " ", text).split())


def fuzzy_threshold(key_len: int) -> float | None:
    """Short names must match exactly; longer ones may have 1-2 OCR errors (e.g. NEUROB1ON)."""
    if key_len <= 5:
        return None
    return 0.83 if key_len <= 7 else 0.8


OCR_DIGITS = str.maketrans("0158", "oisb")   # common OCR confusions inside words: NEUROB1ON, NEVROBI0N


def word_grams(segments: list) -> list:
    """OCR segments → candidate word n-grams (1-3 words). Each gram carries a weight:
    bigger and more confident text = more likely the product name."""
    max_h = max((s["h"] for s in segments), default=1) or 1
    words = []
    for s in segments:
        w = (0.6 + 0.4 * s["h"] / max_h) * (0.5 + 0.5 * s["conf"])
        words += [(tok.translate(OCR_DIGITS) if re.search("[a-z]", tok) else tok, w)
                  for tok in norm(s["text"]).split()]
    return [(tuple(t for t, _ in words[i:i + n]), min(w for _, w in words[i:i + n]))
            for n in (1, 2, 3) for i in range(len(words) - n + 1)]


LOOKALIKE = str.maketrans("l1i0", "iiio")   # letters OCR mixes up: FEFO1 / FEFOI / FEFOL are the same word


def similarity(gram: str, key: str) -> float:
    thr = fuzzy_threshold(len(key))
    if thr is None:
        return 1.0 if gram.translate(LOOKALIKE) == key.translate(LOOKALIKE) else 0.0
    if abs(len(gram) - len(key)) > 2:
        return 0.0
    r = SequenceMatcher(None, gram, key).ratio()
    return r if r >= thr else 0.0


def gram_match(gram: tuple, key: str) -> float:
    """Single-word key: also matches words OCR split apart ("NEURO BION").
    Multi-word key: word by word, so "SURBEX" alone never matches "surbex z"."""
    key_words = norm(key).split()
    if len(key_words) == 1:
        return similarity("".join(gram), key_words[0])
    if len(gram) != len(key_words):            # "FEFOLVIT" read as one word: must match the joined name exactly
        joined = "".join(gram).translate(LOOKALIKE)
        return 1.0 if joined == "".join(key_words).translate(LOOKALIKE) else 0.0
    scores = [similarity(g, k) for g, k in zip(gram, key_words)]
    return min(scores)


def best_fuzzy_match(grams: list, keys: list) -> tuple[str | None, float]:
    """Return the key that best matches any gram; the more specific key wins ties ("surbex z" over "surbex")."""
    found = {}
    for key in keys:
        for gram, weight in grams:
            ratio = gram_match(gram, key)
            if ratio:
                found[key] = max(found.get(key, 0), ratio * weight)
    if not found:
        return None, 0.0
    best = max(found, key=lambda k: (round(found[k], 2), len(k)))
    return best, round(found[best], 3)


def find_ingredients(text_n: str) -> list:
    """Generic actives on the label (iron, folic acid…), in label order.
    Used for dataset evidence, never as the product name."""
    hits = {}
    for key in sorted(INGREDIENTS, key=len, reverse=True):
        m = re.search(rf"\b{re.escape(norm(key))}\b", text_n)
        if m and INGREDIENTS[key] not in hits:
            hits[INGREDIENTS[key]] = m.start()
    return sorted(hits, key=hits.get)


def match_company(text: str) -> str | None:
    if not text:
        return None
    text_n = norm(text)
    grams = word_grams([{"text": text, "h": 1, "conf": 1}])
    for company, aliases in verified_companies.items():
        for alias in aliases:
            a = norm(alias)
            if len(a.replace(" ", "")) <= 5:
                if re.search(rf"\b{re.escape(a)}\b", text_n):
                    return company
            elif best_fuzzy_match(grams, [alias])[0]:
                return company
    return None


# Common medicine ingredients (generic names and drug-family endings) — so a medicine is recognised even without AI.
MEDICINE_WORDS = re.compile(
    r"\b(paracetamol|acetaminophen|ibuprofen|diclofenac|naproxen|mefenamic|aspirin|tramadol|codeine|"
    r"cetirizine|loratadine|fexofenadine|chlorpheniramine|metformin|glimepiride|gliclazide|insulin|"
    r"amlodipine|losartan|atenolol|bisoprolol|warfarin|clopidogrel|levothyroxine|prednisolone|dexamethasone|"
    r"loperamide|domperidone|ondansetron|metronidazole|ranitidine|famotidine|salbutamol|montelukast|"
    r"\w+cillin|\w+mycin|\w+floxacin|\w+prazole|\w+statin|\w+sartan|(?!april\b)\w+pril|\w+olol|\w+dipine|\w+cycline)\b", re.I)


# Common medicine brands sold in Pakistan, for packs whose generic name OCR can't read and for typed names.
MEDICINE_BRANDS = re.compile(
    r"\b(klaricid|panadol|calpol|brufen|ponstan|disprin|augmentin|amoxil|velosef|flagyl|risek|nexum|zithromax|azomax|"
    r"ciproxin|novidat|septran|zinnat|maxitrol|arinac|softin|rigix|gravinate|motilium|glucophage|concor|lipiget|ventolin|"
    r"loprin|ascard|xynosine|voltral|caflam)\b", re.I)


def is_medicine_name(text: str) -> bool:
    return bool(MEDICINE_WORDS.search(text or "") or MEDICINE_BRANDS.search(text or ""))


def find_printed_maker(raw_text: str) -> str | None:
    """Company name after 'Manufactured by' / 'Marketed by' on the label."""
    m = re.search(r"(?:manufactured|marketed|mfd|mkt|made)\.?\s*(?:by|for)\s*:?\s*([a-z][a-z&.'() -]{2,40}?)"
                  r"(?=\s*(?:,|\.\s|reg\b|pakistan|lahore|karachi|islamabad|\d|$))", raw_text, re.I)
    return m.group(1).strip() if m else None


def verify_maker(brand_key: str | None, registered: str | None, printed: str | None, licensed: bool = False,
                 brand_seen: str | None = None) -> dict:
    """verified: printed maker is registered (and matches the brand, if we know the brand's maker)
    verified_by_brand: brand is in our dataset with a known registered maker, no maker visible in the photo
    mismatch: a known brand with a DIFFERENT registered maker printed → possible counterfeit (report blocked)
    unregistered / not_found: maker printed but not in our list, or not visible → warning, report continues"""
    brand_makers = BRANDS[brand_key].get("makers") if brand_key else None
    official = brand_makers or []
    if registered:
        if brand_makers and registered not in brand_makers and licensed:   # "made under licence of …" on the pack
            return {"status": "verified", "name": registered, "official": official, "licence": True}
        if brand_makers and registered not in brand_makers:
            return {"status": "mismatch", "name": registered, "expected": brand_makers[0], "official": official}
        return {"status": "verified", "name": registered, "official": official}
    if brand_makers:
        return {"status": "verified_by_brand", "name": brand_makers[0], "official": official}
    if printed:
        return {"status": "unregistered", "name": printed, "official": official}
    if brand_seen:                                  # e.g. Nutricost: the brand is the company, no "Manufactured by" line
        return {"status": "brand_seen", "name": brand_seen, "official": official}
    return {"status": "not_found", "name": None, "official": official}


def find_registration_no(raw_text: str) -> str | None:
    """DRAP registration / enlistment number printed on Pakistani packs."""
    m = re.search(r"(?:reg(?:istration)?\.?\s*(?:no|#)|enlistment\s*no|drap)\.?\s*[:#\-]?\s*([a-z0-9][a-z0-9\-/]{3,})",
                  raw_text, re.I)
    return m.group(1).upper() if m else None


def resolve_dataset_key(name: str, ingredients: list) -> str | None:
    """Product name (from vision or typed by user) → supplement_info key, for dataset evidence."""
    if not name:
        return ingredients[0] if ingredients else None
    if name.strip().lower() in DSLD_LOWER:
        return DSLD_LOWER[name.strip().lower()]
    brand, _ = best_fuzzy_match(word_grams([{"text": name, "h": 1, "conf": 1}]), list(BRANDS))
    if brand:
        return BRANDS[brand]["dataset"]
    lower = {k.lower(): k for k in supplement_info}
    close = get_close_matches(name.lower(), list(lower), n=1, cutoff=0.75)
    if close:
        return lower[close[0]]
    found = find_ingredients(norm(name))
    return (found or ingredients or [None])[0]

# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE
# ═══════════════════════════════════════════════════════════════════════════════

# Haiku 5.5: about $0.002 per full scan. Set CLAUDE_MODEL in backend/.env to use another model.
CLAUDE_MODELS = [m for m in [os.environ.get("CLAUDE_MODEL"), "claude-haiku-5-5", "claude-haiku-4-5"] if m]


AI_STATUS = {"ok": None, "reason": None}   # last Claude result, shown in the report when AI is off


# Free option: a Google Gemini key from aistudio.google.com (GEMINI_API_KEY in backend/.env).
GEMINI_MODELS = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"] if m]


# ═══════════════════════════════════════════════════════════════════════════════
# PRIVACY — what may reach an AI model
# The AI (Claude, through Anthropic's API) only ever gets: age, sex, periods/pregnancy/breastfeeding, the reasons and
# the label text. Never the name, username, email, date of birth, photo or account id. Free text is scrubbed of
# emails, phone/ID numbers and links. Anthropic does not train its models on API data by default.
# ═══════════════════════════════════════════════════════════════════════════════
PII_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?:https?://|www\.)\S+|\S+\.(?:com|pk|org|net)/\S*", re.I), "[link]"),
    (re.compile(r"\b\d{5}-\d{7}-\d\b"), "[id number]"),                       # Pakistani CNIC
    (re.compile(r"(?:\+?\d[\d\s-]{8,}\d)"), "[number]"),                         # phone numbers, long digit runs
]


def redact(text: str) -> str:
    """Remove emails, links, CNIC and phone numbers from free text before it goes to an AI model or the database."""
    for pattern, mask in PII_PATTERNS:
        text = pattern.sub(mask, text or "")
    return text


def _ai_fail(reason):
    AI_STATUS.update(ok=False, reason=reason)
    print(f"⚠️  AI unavailable: {reason}")
    return None


def _read_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1]) if start != -1 else None
    except json.JSONDecodeError:
        return None


def call_gemini(content: list, max_tokens: int, api_key: str) -> dict | None:
    """Same content blocks as Claude (text + base64 images), sent to Google Gemini."""
    parts = [{"inline_data": {"mime_type": b["source"]["media_type"], "data": b["source"]["data"]}} if b["type"] == "image"
             else {"text": b["text"]} for b in content]
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.2,
                                 "responseMimeType": "application/json"}}
    for model in GEMINI_MODELS:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")
            if e.code == 404:          # model not available → try the next one
                continue
            if e.code in (400, 403) and "key" in msg.lower():
                return _ai_fail("The GEMINI_API_KEY in backend/.env was rejected")
            if e.code == 429:
                return _ai_fail("Gemini free limit reached for now — try again in a minute")
            if e.code == 403 and "free tier" in msg.lower():
                return _ai_fail("Gemini's free tier is not available for this Google project (it asks for billing)")
            return _ai_fail(f"Gemini API error {e.code}: {msg[:200]}")
        except Exception as e:
            return _ai_fail(f"Could not reach the Gemini API ({e.__class__.__name__}) — check the internet connection")
        text = "".join(p.get("text", "") for c in data.get("candidates", [])[:1]
                       for p in c.get("content", {}).get("parts", []))
        result = _read_json(text)
        if result is None:
            return _ai_fail("Gemini's answer could not be read")
        AI_STATUS.update(ok=True, reason=None)
        return result
    return _ai_fail("None of the Gemini models are available for this key")


# Free option 2: Groq (console.groq.com → API Keys). GROQ_API_KEY in backend/.env.
# Groq changes its model list often, so we ask it which models this key has and pick one.
GROQ_PREFER_VISION = ["llama-4-scout", "llama-4-maverick", "vision"]
GROQ_PREFER_TEXT = ["llama-3.3-70b", "gpt-oss-120b", "llama-4", "qwen", "gpt-oss-20b", "llama-3.1-8b"]
_groq_models: dict = {}


def groq_request(path: str, api_key: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"https://api.groq.com/openai/v1/{path}",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}",
                                          "User-Agent": "MediSafe-FYP/1.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read())


def groq_pick(api_key: str) -> tuple[str | None, str | None]:
    """(vision model, text model) available to this key."""
    if "ids" not in _groq_models:
        try:
            ids = [m["id"] for m in groq_request("models", api_key).get("data", []) if m.get("active", True)]
        except Exception:
            ids = []
        _groq_models["ids"] = ids
        print(f"🤖 Groq models for this key: {', '.join(ids[:12]) or 'none'}")
    ids = _groq_models["ids"]
    pick = lambda prefs: next((m for p in prefs for m in ids if p in m.lower()), None)
    forced = os.environ.get("GROQ_MODEL")
    return (forced or pick(GROQ_PREFER_VISION)), (forced or pick(GROQ_PREFER_TEXT) or pick(GROQ_PREFER_VISION))


def call_groq(content: list, max_tokens: int, api_key: str) -> dict | None:
    """Same content blocks as Claude, sent to Groq's OpenAI-style chat API. Photos only go to a vision model."""
    vision, text_model = groq_pick(api_key)
    has_images = any(b["type"] == "image" for b in content)
    model = vision if has_images and vision else text_model
    if not model:
        return _ai_fail("Groq has no models available for this key")
    parts = [{"type": "image_url", "image_url": {"url": f"data:{b['source']['media_type']};base64,{b['source']['data']}"}}
             if b["type"] == "image" else {"type": "text", "text": b["text"]}
             for b in content if b["type"] != "image" or model == vision]
    if not any(p["type"] == "image_url" for p in parts):
        parts = "\n\n".join(p["text"] for p in parts)       # text-only models take a plain string
    body = {"model": model, "max_tokens": max(max_tokens, 800), "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": "Reply with one JSON object only."},
                         {"role": "user", "content": parts}]}
    try:
        try:
            data = groq_request("chat/completions", api_key, body)
        except urllib.error.HTTPError as e:
            if e.code != 400 or "json_validate_failed" not in e.read().decode(errors="ignore"):
                raise
            body.pop("response_format")                # strict JSON mode failed: ask again, read the JSON ourselves
            data = groq_request("chat/completions", api_key, body)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="ignore")
        if e.code == 401:
            return _ai_fail("The GROQ_API_KEY in backend/.env was rejected")
        if e.code == 429:
            return _ai_fail("Groq free limit reached for now — try again in a minute")
        return _ai_fail(f"Groq API error {e.code} ({model}): {msg[:200]}")
    except Exception as e:
        return _ai_fail(f"Could not reach the Groq API ({e.__class__.__name__}) — check the internet connection")
    result = _read_json((data.get("choices") or [{}])[0].get("message", {}).get("content") or "")
    if result is None:
        return _ai_fail("Groq's answer could not be read")
    AI_STATUS.update(ok=True, reason=None)
    return result


_AI_DOWN = {"until": 0.0}


def call_claude(content: list, max_tokens: int) -> dict | None:
    """After an AI failure, skip the AI for 5 minutes so every scan isn't slowed down by a broken key."""
    if TESTING or time.time() < _AI_DOWN["until"]:
        return None
    result = _call_ai(content, max_tokens)
    if result is None:
        _AI_DOWN["until"] = time.time() + 300
    return result


def _call_ai(content: list, max_tokens: int, timeout: int = 25) -> dict | None:
    """Send content blocks to the AI (Claude if ANTHROPIC_API_KEY is set, otherwise Gemini if GEMINI_API_KEY is set).
    Returns the parsed JSON object, or None with AI_STATUS['reason'] set."""
    fail = _ai_fail
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and os.environ.get("GROQ_API_KEY"):
        return call_groq(content, max_tokens, os.environ["GROQ_API_KEY"])
    if not api_key and os.environ.get("GEMINI_API_KEY"):
        return call_gemini(content, max_tokens, os.environ["GEMINI_API_KEY"])
    if not api_key:
        return fail("No AI key: add ANTHROPIC_API_KEY to backend/.env (GROQ_API_KEY / GEMINI_API_KEY are optional backups)")
    for model in CLAUDE_MODELS:
        payload = json.dumps({"model": model, "max_tokens": max_tokens,
                              "messages": [{"role": "user", "content": content}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, headers={
            "Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": api_key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            if e.code == 404:          # model name not available on this key → try next
                continue
            if e.code == 401:
                return fail("The API key in backend/.env was rejected (invalid or deleted key)")
            if "credit" in body.lower():
                return fail("The Anthropic account has no credit left (console.anthropic.com → Billing)")
            return fail(f"Claude API error {e.code}: {body[:200]}")
        except Exception as e:
            return fail(f"Could not reach the Claude API ({e.__class__.__name__}) — check the internet connection")
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        result = _read_json(text)
        if result is None:
            return fail("Claude's answer could not be read")
        AI_STATUS.update(ok=True, reason=None)
        return result
    return fail("None of the Claude models are available for this API key")


def image_block(image: Image.Image) -> dict:
    img = image.copy()
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(buf.getvalue()).decode()}}


def claude_read_label(images: list, ocr_text: str) -> dict | None:
    """Fallback when OCR could not find the brand or manufacturer (blurry blister packs etc.)."""
    prompt = f"""These photos show ONE supplement/medicine pack (front, back or blister strip).
OCR text from the photos (may contain errors): "{redact(ocr_text)[:1500]}"

Return ONLY this JSON:
{{"product_name": "brand/product name exactly as printed, e.g. Neurobion", "brand": "the brand name alone, e.g. Nutricost", "manufacturer": "company name printed after 'Manufactured by' / 'Marketed by' / 'Distributed by'", "active_ingredients": ["each ingredient with its amount per tablet as printed, e.g. Vitamin B6 (Pyridoxine HCl) 200 mg"], "other_ingredients": ["inactive ingredients if printed, e.g. gelatin capsule, rice flour"], "warnings": "age or pregnancy warnings exactly as printed, e.g. Not recommended for children under 12 years", "directions": "dosage directions as printed, e.g. 1 tablet daily", "is_supplement": "true if this is a vitamin, mineral or herbal dietary supplement; false if it is a medicine/drug (e.g. painkiller, antibiotic)"}}

Rules: read only what is printed. If a value is not clearly readable, use null. Never guess a brand from the ingredients."""
    # Short time limit: the scan screen waits for this. A slow or failed answer is skipped, because the
    # label's own composition (read by OCR) is enough to make the report.
    if TESTING or time.time() < _AI_DOWN["until"]:
        return None
    return _call_ai([*(image_block(i) for i in images[:2]), {"type": "text", "text": prompt}], 400, timeout=12)

# ═══════════════════════════════════════════════════════════════════════════════
# DATASET EVIDENCE — DrugBank interactions + Random Forest food model
# ═══════════════════════════════════════════════════════════════════════════════

def build_food_feature_vector(supp_name: str, food_name: str) -> np.ndarray:
    """Build ML feature vector for food-supplement pair."""
    sd = supplements_db.get(supp_name, {})
    fd = foods_db.get(food_name, {})
    row = []
    for n in NUTRIENT_KEYS:
        row.append(sd.get(n, 0))
    row.append(CATEGORY_CODE.get(sd.get("category", "other"), 7))
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


def build_food_reason(supp_name: str, food_name: str, is_avoid: bool) -> str:
    """Plain explanation for a Random Forest prediction, based on the nutrients involved.
    Returns "" when there is no clear nutrient reason, so the prediction is not shown."""
    sd, fd = supplements_db.get(supp_name, {}), foods_db.get(food_name, {})
    iron, zinc, calcium = sd.get("iron", 0) > 50, sd.get("zinc", 0) > 50, sd.get("calcium", 0) > 50
    fat_soluble = sd.get("vitamin_d", 0) > 50 or sd.get("vitamin_e", 0) > 30 or sd.get("vitamin_k", 0) > 30
    if is_avoid:
        if (iron or zinc) and fd.get("tannin", 0) >= 25:
            return f"{food_name} has tannins, which bind {'iron' if iron else 'zinc'} and stop your body absorbing it."
        if (iron or calcium) and fd.get("oxalate", 0) >= 40:
            return f"{food_name} is high in oxalates, which bind {'iron' if iron else 'calcium'} so your body can't absorb it."
        return ""
    if iron and fd.get("vitamin_c", 0) >= 40:
        return f"{food_name} is rich in vitamin C, which helps your body absorb iron. Have it with your tablet."
    if fat_soluble and food_name == "Avocado":
        return f"{food_name} has healthy fat, which helps your body absorb fat-soluble vitamins like vitamin D and E."
    if (sd.get("vitamin_d", 0) > 50 or calcium) and fd.get("vitamin_k", 0) >= 100 and fd.get("oxalate", 0) < 40:
        return f"{food_name} is rich in vitamin K, which works with calcium and vitamin D to keep bones strong."
    return ""


def food_evidence(dataset_key: str) -> dict:
    """Foods to eat / avoid for a supplement from DrugBank records, Random Forest for undocumented pairs."""
    if dataset_key not in supplements_db:
        return {"eat": [], "avoid": []}
    eat, avoid = [], []
    known = {i["food"]: i for i in food_inter_db if i["supplement"] == dataset_key}
    for food, fd in foods_db.items():
        if fd.get("type") not in ("fruit", "vegetable"):
            continue
        if food in known:                                    # documented interaction: use its own reason
            is_avoid, source = known[food]["type"] == "avoid", "DrugBank"
            reason = known[food]["reason"]
        else:                                                # Random Forest prediction
            feats = build_food_feature_vector(dataset_key, food)
            proba = food_model.predict_proba(feats)[0]
            is_avoid, source = int(np.argmax(proba)) == 1, f"Random Forest ({max(proba):.0%})"
            reason = build_food_reason(dataset_key, food, is_avoid)
            if not reason:                                   # no clear nutrient reason → don't show it
                continue
        (avoid if is_avoid else eat).append({"food": food, "reason": reason, "source": source})
    by_source = lambda x: x["source"] != "DrugBank"
    return {"eat": sorted(eat, key=by_source)[:6], "avoid": sorted(avoid, key=by_source)[:6]}

# A brand we have no food records for (Fefol Vit, Sangobion…) uses the records of what is inside it.
NUTRIENT_FOOD_KEY = {"iron": "Iron Supplement", "folate": "Folic Acid", "vitamin_c": "Vitamin C", "vitamin_d": "Vitamin D3",
                     "calcium": "Calcium Supplement", "zinc": "Zinc Supplement", "magnesium": "Magnesium",
                     "vitamin_a": "Vitamin A", "vitamin_e": "Vitamin E", "vitamin_k": "Vitamin K2",
                     "potassium": "Potassium", "biotin": "Biotin", "vitamin_b12": "Vitamin B12"}
# B vitamins have no food interactions on record; these are simply good food sources of the same vitamins (USDA).
B_VITAMIN_FOODS = [
    {"food": "Banana", "reason": "Bananas are one of the best fruit sources of vitamin B6.", "source": "Nutrient content"},
    {"food": "Avocado", "reason": "Avocado gives vitamin B6 and folate, and its healthy fat suits any meal.", "source": "Nutrient content"},
    {"food": "Spinach", "reason": "Spinach is rich in folate, another B vitamin.", "source": "Nutrient content"},
]
B_VITAMINS = {"vitamin_b1", "vitamin_b6", "vitamin_b12", "niacin", "biotin", "folate"}


def foods_for(dataset_key: str | None, nutrients: list) -> dict:
    """Fruits and vegetables to eat / keep apart, for the product or, failing that, for what is inside it."""
    foods = food_evidence(dataset_key) if dataset_key else {"eat": [], "avoid": []}
    if not (foods["eat"] or foods["avoid"]) and dataset_key in DSLD:       # NIH label: use its main ingredient's records
        foods = food_evidence(DSLD[dataset_key]["info_key"])
    if foods["eat"] or foods["avoid"]:
        return foods
    eat, avoid = {}, {}
    for key in dict.fromkeys(NUTRIENT_FOOD_KEY[n] for n in nutrients if n in NUTRIENT_FOOD_KEY):
        part = food_evidence(key)
        for f in part["avoid"]:
            avoid.setdefault(f["food"], f)
        for f in part["eat"]:
            eat.setdefault(f["food"], f)
    eat = [f for name, f in eat.items() if name not in avoid]     # if one ingredient says avoid, avoid wins
    if not eat and B_VITAMINS & set(nutrients):
        eat = list(B_VITAMIN_FOODS)
    by_source = lambda x: x["source"] != "DrugBank"
    return {"eat": sorted(eat, key=by_source)[:6], "avoid": sorted(avoid.values(), key=by_source)[:6]}

# ═══════════════════════════════════════════════════════════════════════════════
# SAFETY REPORT
# ═══════════════════════════════════════════════════════════════════════════════

VERDICTS = ["Safe", "Use with caution", "Not safe"]


def describe_profile(p: dict) -> str:
    parts = [f"{p['age']}-year-old {p['sex']}"]
    if p["sex"] == "female":
        if p.get("periods"):
            parts.append("periods started" if p["periods"] == "yes" else "no periods")
        if p.get("pregnant"):
            parts.append("pregnant")
        if p.get("breastfeeding"):
            parts.append("breastfeeding")
    return ", ".join(parts)


def ai_safety_report(product: dict, company: str, profile: dict, reasons: list, ocr_text: str,
                     info: dict, foods: dict, personal: dict) -> dict | None:
    evidence = {
        "dataset_profile": {k: info.get(k) for k in ("full_name", "used_for", "pros", "cons")} if info else None,
        "fruits_and_vegetables_from_dataset": {
            "eat":   [{"food": f["food"], "reason": f["reason"][:220]} for f in foods["eat"]],
            "avoid": [{"food": f["food"], "reason": f["reason"][:220]} for f in foods["avoid"]],
        },
    }
    checks = [{"check": c["title"], "result": c["status"], "detail": c["text"]} for c in personal["checks"]]
    prompt = f"""You are a pharmacist writing a supplement safety report for a person in Pakistan. Plain, simple English.

PERSON: {describe_profile(profile)}
REASONS FOR TAKING IT: {", ".join(redact(r) for r in reasons) or "not given"}

SUPPLEMENT: {product["name"]}, maker: {company or "not confirmed"}
Ingredients found: {", ".join(product["ingredients"]) or "not listed"}
Label text (OCR, may contain errors): "{redact(ocr_text)[:1500]}"

PERSONAL CHECKS ALREADY DONE FROM OUR DATASETS (NIH daily limits, label warnings, purpose rules). These are facts: do not contradict them.
{json.dumps(checks, ensure_ascii=False)}
Reason checks: {json.dumps(personal.get("reasons", []), ensure_ascii=False)}
Dosage worked out from the label: {json.dumps(personal["dosage"], ensure_ascii=False)}

DATASET EVIDENCE: {json.dumps(evidence, ensure_ascii=False)}

Return ONLY this JSON:
{{
  "verdict": "Safe | Use with caution | Not safe (never safer than the personal checks)",
  "summary": "1-2 sentences for this person: can they take it and the main reason",
  "purpose_check": {{"explanation": "1-2 sentences on whether it helps with their reasons; agree with the reason checks above"}},
  "actual_usage": "2-3 sentences: what this supplement is really used for",
  "benefits": ["4-5 short benefits relevant to this person"],
  "dose": {{"amount": "e.g. 1 tablet", "how_often": "e.g. once a day", "when": "e.g. after breakfast"}},
  "dosage_note": "1-2 sentences adding anything the dosage above misses for this person's age/sex/pregnancy, or empty",
  "side_effects": ["4-5 side effects or warnings"],
  "recommended_foods": [{{"food": "a fruit or vegetable", "reason": "why it helps"}}],
  "foods_to_avoid": [{{"food": "a fruit or vegetable", "reason": "why to keep it 2 hours apart"}}]
}}
Rules: "dose" = the usual dose of this product for this person, never above the safe limits shown above; if the personal checks say doctor only, write "Only as your doctor prescribed".
Foods must be fruits or vegetables only (no drinks, no medicines), 3-6 each, using the dataset evidence first.
Do not invent facts."""
    report = call_claude([{"type": "text", "text": prompt}], 2000)
    if not report:
        return None
    if report.get("verdict") not in VERDICTS:
        report["verdict"] = "Use with caution"
    for key in ("benefits", "side_effects", "recommended_foods", "foods_to_avoid"):
        report[key] = [x for x in (report.get(key) or []) if x]
    return report


def build_report(personal: dict, ai: dict | None, info: dict, foods: dict) -> dict:
    """Personal checks decide the verdict; the AI may only make it stricter, never safer."""
    verdict = personal["verdict"]
    if ai and VERDICTS.index(ai["verdict"]) > VERDICTS.index(verdict):
        verdict = ai["verdict"]
    # The headline gives the most serious health problem first: stops before cautions, and the
    # health checks (age, dose, pregnancy…) before the reason, maker and label checks.
    later = {"reason": 1, "maker": 2, "label": 3}
    problems = sorted((c for c in personal["checks"] if c["status"] in ("caution", "stop")),
                      key=lambda c: (later.get(c["key"], 0) > 0, c["status"] != "stop", later.get(c["key"], 0)))
    first_problem = problems[0]["text"] if problems else None
    title, tone = None, None
    health = [c for c in problems if c["key"] not in ("reason", "maker", "label")]
    reason_row = next((c for c in problems if c["key"] == "reason"), None)
    if reason_row and not health and verdict == "Use with caution":
        title = "Not right for your reason"         # safe to take, but it won't do what they want
        tone = reason_row["status"]                  # red when it won't help, orange when it's not proven
        first_problem = reason_row["text"]
    reason = ((first_problem if title else None) or (ai or {}).get("summary") or first_problem
              or "Based on your age and profile, this supplement suits you.")
    dosage = dict(personal["dosage"] or {})
    if ai and ai.get("dosage_note"):
        dosage["note"] = ai["dosage_note"]
    summary = dict(dosage.get("summary") or {})
    ai_dose = (ai or {}).get("dose") or {}
    if summary and not summary.get("doctor_only"):     # pack directions first; AI only fills what the pack didn't say
        for k in ("amount", "how_often"):
            summary[k] = summary.get(k) or ai_dose.get(k)
        summary["when"] = ai_dose.get("when") or summary.get("when")   # AI timing is more specific than the generic tip
        dosage["summary"] = summary
    return {
        "is_safe_to_take": {"verdict": verdict, "title": title, "tone": tone, "reason": reason, "checks": personal["checks"]},
        "facts": info.get("best_known_for") or "",
        "recommended_dosage": dosage,
        "notes": personal["notes"],
        "purpose_check": {"results": personal.get("reasons", []),
                          "ai_note": ((ai or {}).get("purpose_check") or {}).get("explanation")},
        "actual_usage": (ai or {}).get("actual_usage") or info.get("used_for", ""),
        "benefits": (ai or {}).get("benefits") or info.get("pros", []),
        "side_effects": (ai or {}).get("side_effects") or info.get("cons", []),
        "recommended_foods": (ai or {}).get("recommended_foods") or [{"food": f["food"], "reason": f["reason"]} for f in foods["eat"]],
        "foods_to_avoid": (ai or {}).get("foods_to_avoid") or [{"food": f["food"], "reason": f["reason"]} for f in foods["avoid"]],
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# INPUT VALIDATION — profile and report requests are checked before anything is saved or sent to the AI
# ═══════════════════════════════════════════════════════════════════════════════
NAME_OK = re.compile(r"^[A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF .'-]{1,39}$")   # letters (English/Urdu), 2-40


def check_health_fields(m):
    """Rules every profile must follow, so the data stays realistic and nothing personal is hidden in it."""
    if m.sex == "male" and (m.pregnant or m.breastfeeding or m.periods):
        raise ValueError("Periods, pregnancy and breastfeeding only apply to females.")
    if m.sex == "female":
        if m.periods in ("yes", "irregular") and m.age < 8:
            raise ValueError("Periods can't be set for girls under 8. Please check the age.")
        if (m.pregnant or m.breastfeeding) and not 12 <= m.age <= 60:
            raise ValueError("Pregnancy and breastfeeding can only be set for ages 12 to 60.")
    return m


def clean_reasons(reasons: list) -> list:
    if len(reasons) > 5:
        raise ValueError("Choose at most 5 reasons.")
    out = []
    for r in reasons:
        r = redact(re.sub(r"[\x00-\x1f<>{}]", "", str(r))).strip()     # no emails/phone numbers kept or sent to AI
        if not r:
            continue
        if len(r) > 80:
            raise ValueError("Each reason must be 80 characters or less.")
        out.append(r)
    return out


class ReasonsRequest(BaseModel):
    scan_id: str
    name: Optional[str] = None                     # the name the user confirmed, if they changed it
    periods: Optional[Literal["yes", "irregular", "no"]] = None
    age: Optional[int] = Field(None, ge=1, le=120)
    sex: Optional[Literal["male", "female"]] = None


class ReportRequest(BaseModel):
    scan_id: str
    age: int = Field(..., ge=1, le=120)
    sex: Literal["male", "female"]
    periods: Optional[Literal["yes", "irregular", "no"]] = None      # females only: yes = regular, irregular = oligomenorrhea
    pregnant: bool = False
    breastfeeding: bool = False
    reasons: List[str] = []
    supplement_name: Optional[str] = Field(None, max_length=80)   # user's correction if the scanned name was wrong

    @field_validator("reasons")
    @classmethod
    def reasons_are_clean(cls, v: list) -> list:
        return clean_reasons(v)

    @model_validator(mode="after")
    def health_fields_agree(self):
        return check_health_fields(self)


def product_name_of(scan: dict) -> str:
    return scan["product"]["name"] or "This product"


def maker_check(company: dict, product_name: str, searched: bool = False) -> dict:
    """Manufacturer line for the report. Only 'unregistered' counts against the verdict:
    a maker we simply couldn't see is a buying tip, not a health risk."""
    official = " or ".join(company.get("official") or [])
    st = company["status"]
    if st == "verified":
        status, text = "ok", f"The pack shows {company['name']}, " + ("the official maker of this brand." if official else "a registered manufacturer.")
    elif st == "verified_by_brand":
        status, text = "ok", (f"The official maker of {product_name} is {official}. Check that your pack shows this name. "
                              "If it shows a different company, it may be fake.")
    elif st == "mismatch":
        status, text = "caution", (f"{product_name} is usually made by {company['expected']}, but this pack says {company['name']}. "
                                   "Some brands are made under licence by another company. If your pack does not say "
                                   "\"under licence\", it may not be genuine. Buy from a licensed pharmacy.")
    elif st == "brand_seen":
        status, text = "info", (f"The pack shows the brand {company['name']}, which is not in our list of verified manufacturers, "
                                "so we can't confirm it is genuine. Genuine packs show the maker's address and a DRAP "
                                "registration number (imported packs carry the importer's details). Buy from a licensed pharmacy.")
    elif st == "unregistered":
        status, text = "caution", (f"The company on the pack ({company.get('printed_name')}) is not in our list of registered "
                                   "manufacturers. Genuine packs show a registered maker and a DRAP registration number.")
    elif searched:
        status, text = "info", ("We don't have this product's maker in our data. Genuine packs show the maker and a DRAP "
                                "registration number. Check your pack and buy from a licensed pharmacy.")
    else:
        status, text = "info", ("We couldn't see the maker's name in the photo. Genuine packs show the maker and a DRAP "
                                "registration number. Check your pack and buy from a licensed pharmacy.")
    return {"key": "maker", "title": "Manufacturer", "status": status, "text": text}


def load_scan(scan_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", scan_id):
        raise HTTPException(400, "Invalid scan_id.")
    if scan_id not in _scans:
        raise HTTPException(404, "Scan not found. Please scan the supplement again.")
    return _scans[scan_id]


@app.exception_handler(RequestValidationError)
def readable_validation_error(request, exc: RequestValidationError):
    """One plain sentence the app can show, instead of FastAPI's technical list."""
    first = exc.errors()[0] if exc.errors() else {}
    msg = str(first.get("msg", "Please check the details you entered.")).removeprefix("Value error, ")
    field = first.get("loc", [""])[-1]
    if first.get("type") in ("less_than_equal", "greater_than_equal") and field == "age":
        msg = "Age must be between 1 and 120."
    return JSONResponse(status_code=422, content={"detail": msg})


@app.get("/")
def home():
    return {"status": "MediSafe AI running",
            "food_model": f"Random Forest — {accuracy_report['food_model']['test_accuracy'] * 100:.1f}% test accuracy",
            "api_key_loaded": any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY")),
            "ai": "Claude" if os.environ.get("ANTHROPIC_API_KEY") else "Groq" if os.environ.get("GROQ_API_KEY")
                  else "Gemini" if os.environ.get("GEMINI_API_KEY") else "off",
            "last_ai_problem": AI_STATUS["reason"],
            "database": "Firebase" if USE_FIREBASE else "off (firebase-key.json missing)"}


# Main nutrient on a label → the general product it belongs to (for food guidance, reasons and the safety rules).
NUTRIENT_PRODUCT = {"iron": "Iron Supplement", "calcium": "Calcium Supplement", "vitamin_c": "Vitamin C",
                    "vitamin_d": "Vitamin D3", "vitamin_k": "Vitamin K2", "vitamin_b12": "Vitamin B12",
                    "folate": "Folic Acid", "zinc": "Zinc Supplement", "magnesium": "Magnesium",
                    "vitamin_e": "Vitamin E", "vitamin_a": "Vitamin A", "biotin": "Biotin", "potassium": "Potassium"}


def label_order(amounts: dict, raw_text: str) -> list:
    """Nutrients in the order they are printed on the label (the first one is usually the main one)."""
    def where(n):
        m = re.search(personal_check.NAMES[n], raw_text or "", re.I)
        return m.start() if m else 10 ** 6
    return sorted(amounts, key=where)


def composition_key(amounts: dict, raw_text: str) -> str | None:
    """Unknown brand: decide what kind of product it is from the nutrients on its label."""
    if len(amounts) >= 4:
        return "Multivitamin"
    if "iron" in amounts:                          # iron has its own safety rules (periods, men, children)
        return "Iron Supplement"
    for n in label_order(amounts, raw_text):
        if n in NUTRIENT_PRODUCT:
            return NUTRIENT_PRODUCT[n]
    return None                                    # e.g. B1, B3, B6 only: checked with their NIH limits alone


def composition_name(amounts: dict, raw_text: str) -> str:
    names = [personal_check.LIMITS[n]["name"] for n in label_order(amounts, raw_text)]
    return "Multivitamin" if len(names) >= 4 else " + ".join(names[:3]) + " supplement"


# Words on a pack that are never the brand
NOT_BRAND = re.compile(r"^(vitamin|vitamins|supplement|supplements|dietary|capsules?|tablets?|softgels?|caplets?|gummies|"
                       r"serving|servings|per|each|contains|mg|mcg|iu|with|and|for|the|daily|value|facts|natural|extra|"
                       r"strength|high|potency|formula|complex|plus|forte|new|net|food|men|women|kids|adults?|"
                       r"pyridoxine|niacin|biotin|iron|zinc|calcium|magnesium|potassium|folic|acid|omega|fish|oil|"
                       r"hcl|hci|d3|b6|b12|b1|b3|c|d|e|k|k2|a|quality|guarantee|guaranteed)$", re.I)


def brand_on_pack(segments: list) -> str | None:
    """Unknown brand: the first word near the top of the pack that is not a vitamin, unit or common label word.
    Used only to name the company when no 'Manufactured by' line can be read."""
    for sg in segments[:6]:
        for w in re.findall(r"[A-Za-z][A-Za-z'&-]{3,20}", sg["text"]):
            if not NOT_BRAND.match(w) and not is_medicine_name(w):
                return w[:1].upper() + w[1:].lower() if w.islower() or w.isupper() else w
    return None


INGREDIENT_LINE = re.compile(r"([A-Za-z][A-Za-z0-9 ()\-/.,'%]{2,60}?)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(mg|mcg|µg|ug|iu|i\.u\.|g)\b", re.I)
SKIP_LINE = re.compile(r"^(per|each|serving|servings|net|contains|capsules?|tablets?|total|amount|daily|value|take)\b", re.I)


def all_ingredients(texts: list, other: list) -> list:
    """Every ingredient with an amount that we can read, plus inactive ingredients from the photo reading.
    checked = we have an NIH limit for it (one of the 16 nutrients), so its amount is compared with that limit."""
    out, seen = [], set()
    for text in texts:
        for m in INGREDIENT_LINE.finditer(text or ""):
            name = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-:")
            name = re.sub(r"^.*\b(?:supplement\s+facts|nutrition\s+facts|contains?|ingredients|composition)\b\s*:?\s*", "",
                          name, flags=re.I).strip()
            name = " ".join(name.split()[-5:])            # a name runs at most 5 words back from its amount
            if len(name) < 3 or SKIP_LINE.match(name):
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            checked = bool(personal_check.parse_amounts(f"{name} {m.group(2)} {m.group(3)}"))
            out.append({"name": name, "amount": f"{m.group(2)} {m.group(3)}", "checked": checked})
    for name in other or []:
        name = str(name).strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append({"name": name, "amount": None, "checked": False})
    return out[:25]


FACTS_WORDS = re.compile(r"supplement\s*facts|nutrition\s*facts|each\s+(?:tablet|capsule|caplet|softgel|sachet)\s+contains|"
                         r"composition|ingredients|contains\s*:", re.I)


def photo_is_supplement(image: Image.Image) -> tuple[bool, str]:
    """CLIP zero-shot: is this a photo of a supplement/medicine pack? (score of the 'valid' labels >= 0.5)"""
    inputs = processor(text=CLIP_LABELS, images=image, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        probs = clip_model(**inputs).logits_per_image.softmax(dim=1)[0].cpu().numpy()
    valid_score = float(probs[:len(CLIP_VALID)].sum())
    if valid_score < 0.5:
        top = CLIP_LABELS[int(np.argmax(probs))].replace("a photo of ", "")
        return False, f"looks like {top}, not a supplement ({valid_score:.0%} supplement)."
    return True, ""


@app.post("/scan-supplement")
def scan_supplement(files: List[UploadFile] = File(...)):
    """1-4 photos of ONE supplement (front, back, blister). CLIP validates each, OCR reads all."""
    if not 1 <= len(files) <= 4:
        raise HTTPException(400, "Upload 1-4 photos of the same supplement.")

    started = time.time()
    images, invalid = [], []
    for i, f in enumerate(files, 1):
        try:
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(f.file.read()))).convert("RGB")
        except Exception:
            invalid.append(f"Photo {i}: not a readable image file.")
            continue
        image.thumbnail((1024, 1024))            # sharp enough for label text, much faster to read
        ok, problem = photo_is_supplement(image)
        if not ok:
            invalid.append(f"Photo {i}: {problem}")
        images.append(image)
    if invalid:
        return {"success": False, "message": "Please upload photos of a supplement pack only.", "details": invalid}

    t_clip = time.time()

    # OCR
    segments = []
    for image in images:
        for box, text, conf in reader.readtext(np.array(image), detail=1):
            ys = [p[1] for p in box]
            segments.append({"text": text, "conf": float(conf), "h": max(ys) - min(ys)})
    brand_key, brand_score = best_fuzzy_match(word_grams(segments), list(BRANDS))
    raw_text = " ".join(s["text"] for s in segments)
    if (not brand_key and not find_ingredients(norm(raw_text)) and not is_medicine_name(raw_text)
            and not personal_check.parse_amounts(raw_text)):
        segments = []                                   # nothing useful: the pack may be sideways or upside down
        for image in images[:1]:                        # (turning every photo 3 ways is slow; the first one is enough)
            for box, text, conf in reader.readtext(np.array(image), detail=1, rotation_info=[90, 180, 270]):
                ys = [p[1] for p in box]
                segments.append({"text": text, "conf": float(conf), "h": max(ys) - min(ys)})
        brand_key, brand_score = best_fuzzy_match(word_grams(segments), list(BRANDS))
        raw_text = " ".join(s["text"] for s in segments)
    text_n   = norm(raw_text)
    t_ocr = time.time()
    if not TESTING:                                     # last scan kept in backend/debug/ to see what the server got
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            for i, image in enumerate(images, 1):
                image.save(os.path.join(DEBUG_DIR, f"last_scan_{i}.jpg"), quality=85)
            with open(os.path.join(DEBUG_DIR, "last_scan_text.txt"), "w", encoding="utf-8") as f:
                f.write(raw_text)
        except OSError:
            pass
    ingredients = find_ingredients(text_n)
    company     = match_company(raw_text)

    # The AI reads the photo only if OCR could not find the product's name. A maker we can't see is only a buying tip,
    # so it is not worth making every scan wait for the AI.
    vision = claude_read_label(images, raw_text) if not brand_key else None
    vision = vision or {}

    if brand_key:
        name, source, dataset_key = BRANDS[brand_key]["name"], "ocr", BRANDS[brand_key]["dataset"]
    elif vision.get("product_name"):
        name, source = vision["product_name"], "ai_vision"
        dataset_key = resolve_dataset_key(name, ingredients)
    elif ingredients:                               # brand unreadable (scratched, blurry) but the label shows what's in it
        parts = [re.sub(r"\s*supplement$", "", i, flags=re.I) for i in ingredients[:2]]
        name, source, dataset_key = " + ".join(parts) + " supplement", "ingredients", ingredients[0]
    else:
        name, source, dataset_key = None, "not_found", None

    # Strength per tablet, age warning, directions — from OCR; the photo reading (if any) fills gaps
    label = personal_check.read_label(raw_text)
    if vision:
        seen = personal_check.read_label(" ".join([*(vision.get("active_ingredients") or []),
                                                   vision.get("warnings") or "", vision.get("directions") or ""]))
        label["amounts"] = {**seen["amounts"], **label["amounts"]}
        for k in ("min_age", "age_text", "pregnancy_warning", "directions"):
            label[k] = label[k] or seen[k]
    label["strength"] = personal_check.strength_list(label["amounts"])
    # A product we have no data on (any brand, e.g. a Nutrifactor B3): its own label tells us what is in it and how much.
    # The checks then use THIS pack's composition, so two brands of the same vitamin get their own results.
    if label["amounts"] and not dataset_key:
        dataset_key = composition_key(label["amounts"], raw_text)
    if label["amounts"] and not name:
        name, source = composition_name(label["amounts"], raw_text), "composition"
    # Which version of the brand: Centrum Men / Women / Kids / Silver 50+ … read from the pack's words
    label["target"] = personal_check.find_target(name or "", raw_text)
    if name and label["target"] and label["target"]["label"].lower().rstrip("s") not in name.lower():
        name = f"{name} {label['target']['label']}"

    # Everything the pack lists, not only the 16 nutrients we have limits for, and whether the full list was in view
    label["all_ingredients"] = all_ingredients([*(s["text"] for s in segments), *(vision.get("active_ingredients") or [])],
                                               vision.get("other_ingredients") or [])
    label["facts_seen"] = bool(FACTS_WORDS.search(raw_text)) or len(label["all_ingredients"]) >= 3
    seen_brand = None if brand_key else (vision.get("brand") or brand_on_pack(segments))
    if seen_brand and source == "composition" and seen_brand.lower() not in (name or "").lower():
        name = f"{seen_brand} {name.replace(' supplement', '')}"
    printed_maker = find_printed_maker(raw_text) or vision.get("manufacturer")
    if not company and printed_maker:
        company = match_company(printed_maker)
    if not brand_key and name and source != "ingredients":   # name came from the photo reading: link it to a known brand
        brand_key = best_fuzzy_match(word_grams([{"text": name, "h": 1, "conf": 1}]), list(BRANDS))[0]
    maker = verify_maker(brand_key, company, printed_maker, bool(re.search(r"licen[cs]", raw_text, re.I)), seen_brand)

    # Only products we have data on (our supplement datasets / supplement ingredients on the label) can be checked.
    medicine = vision.get("is_supplement") is False or (not brand_key and is_medicine_name(raw_text))
    supported = not medicine and bool(dataset_key or ingredients or label["amounts"] or vision.get("is_supplement") is True)

    scan_id = uuid.uuid4().hex
    result = {
        "scan_id": scan_id,
        "product": {"name": name, "identified": name is not None, "source": source, "supported": supported, "medicine": medicine,
                    "match_score": brand_score if brand_key else None,
                    "from_label": bool(label["amounts"]),
                    "dataset_key": dataset_key,
                    "ingredients": ingredients or (vision.get("active_ingredients") or [])},
        "company": {**maker, "printed_name": printed_maker, "registration_no": find_registration_no(raw_text)},
        "label": label,
        "ocr_text": raw_text,
    }
    _scans[scan_id] = {**result, "thumb": thumbnail(images[0])}
    print(f"⏱  scan: photo check {t_clip - started:.1f}s, reading text {t_ocr - t_clip:.1f}s, "
          f"name + maker {time.time() - t_ocr:.1f}s → {name or 'name not found'}\n   read: {raw_text[:160]!r}")

    return {"success": True, **result}


@app.get("/products")
def products():
    """Names the user can pick from when the pack's name can't be read."""
    names = sorted({b["name"] for b in BRANDS.values()} | set(INGREDIENTS.values()) | set(DSLD), key=str.lower)
    return {"products": names}


class NameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


@app.post("/search-product")
def search_product(data: NameRequest):
    """Search on the home screen: a product picked by name goes through the same steps as a scanned one."""
    name = data.name.strip()
    brand_key = next((k for k, b in BRANDS.items() if b["name"].lower() == name.lower()), None)
    dataset_key = BRANDS[brand_key]["dataset"] if brand_key else resolve_dataset_key(name, [])
    if not dataset_key or is_medicine_name(name):
        raise HTTPException(404, f"We don't have {name} in our data.")
    nih = DSLD.get(dataset_key)
    label = personal_check.read_label(nih["label_text"] if nih else "")
    if nih:                                        # the real label: strength per serving, directions, warnings
        label["amounts"] = dict(nih["strength"])
    label["target"] = personal_check.find_target(name)
    label["strength"] = personal_check.strength_list(label["amounts"]) if nih else []
    company = verify_maker(brand_key, None, None)
    if nih and nih.get("maker") and company["status"] == "not_found":
        company = {"status": "verified_by_brand", "name": nih["maker"], "official": [nih["maker"]]}
    scan_id = uuid.uuid4().hex
    result = {
        "scan_id": scan_id,
        "product": {"name": BRANDS[brand_key]["name"] if brand_key else name, "identified": True, "source": "search",
                    "supported": True, "medicine": False, "match_score": None, "dataset_key": dataset_key, "ingredients": []},
        "company": {**company, "printed_name": None, "registration_no": None},
        "label": label,
        "ocr_text": "",
    }
    _scans[scan_id] = {**result, "thumb": None}
    return {"success": True, **result}


@app.post("/check-name")
def check_name(data: NameRequest):
    """Typed product name → can we check it? Used before the 'why do you take this' step."""
    name = data.name.strip()
    if is_medicine_name(name):
        return {"status": "medicine"}
    return {"status": "ok" if resolve_dataset_key(name, []) else "unknown"}


# ═══════════════════════════════════════════════════════════════════════════════
# FULL COMPOSITION LOOKUP — when the photo shows only the front of the pack
# 1. NIH Dietary Supplement Label Database (official US label records)  2. the brand's own website, via Claude web search
# Amounts read from the user's own pack always win; the lookup only fills in what the photo could not show.
# ═══════════════════════════════════════════════════════════════════════════════
DSLD_API = "https://api.ods.od.nih.gov/dsld/v9"


def _dsld_get(path: str, **params) -> dict | None:
    key = os.environ.get("DATA_GOV_API_KEY") or os.environ.get("USDA_API_KEY")
    if key:
        params["api_key"] = key
    url = f"{DSLD_API}/{path}?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MediSafe-FYP/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 1 and w not in ("mg", "mcg", "iu", "capsules", "tablets")}


def dsld_lookup(brand: str, product: str) -> dict | None:
    """Find this exact product (same brand, same main words) in the NIH label database and return its full label."""
    data = _dsld_get("search-filter", q=f"{brand} {product}".strip(), size=10, status=1)
    hits = (data or {}).get("hits", [])
    hits = hits.get("hits", []) if isinstance(hits, dict) else hits
    want = _words(product) - _words(brand)
    best, best_score = None, 0.0
    for h in hits:
        src = h.get("_source") or {}
        if brand and brand.lower() not in (src.get("brandName") or "").lower():
            continue                                         # a different brand's label is never used
        score = len(want & _words(src.get("fullName"))) / max(1, len(want))
        if score > best_score:
            best, best_score = h, score
    if not best or best_score < 0.5:
        return None
    label = _dsld_get(f"label/{best.get('_id')}")
    if not label:
        return None
    lines, other = [], []
    def walk(rows):
        for row in rows or []:
            q = next((q for q in row.get("quantity") or [] if q.get("quantity")), None)
            if q and row.get("name"):
                unit = str(q.get("unit") or "").split()[0] if q.get("unit") else ""
                lines.append(f"{row['name']} {q['quantity']:g} {unit}" if isinstance(q["quantity"], (int, float)) else f"{row['name']} {q['quantity']} {unit}")
            walk(row.get("nestedRows"))
    walk(label.get("ingredientRows"))
    for ing in ((label.get("otheringredients") or {}).get("ingredients") or []):
        if ing.get("name"):
            other.append(ing["name"])
    full = (label.get("fullName") or "").strip()
    return {"lines": lines, "other": other, "name": full,
            "source": "NIH Dietary Supplement Label Database", "url": f"https://dsld.od.nih.gov/label/{best.get('_id')}"}


def web_lookup(brand: str, product: str) -> dict | None:
    """Claude searches the web for the official Supplement Facts of this product (brand site or a major retailer)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if TESTING or not api_key or time.time() < _AI_DOWN["until"]:
        return None
    prompt = (f'Find the official "Supplement Facts" (ingredients and amounts per serving) of this exact product: '
              f'"{brand} {product}". Use the brand\'s own website or a large online pharmacy or retailer. '
              'Answer ONLY with JSON: {"found": true/false, "product_name": "...", "source_url": "...", '
              '"ingredients": ["each active ingredient with amount per serving, e.g. Vitamin B6 (as Pyridoxine HCl) 100 mg"], '
              '"other_ingredients": ["inactive ingredients"]}. If you are not sure it is this exact product, answer {"found": false}. '
              "Never guess amounts.")
    for model in CLAUDE_MODELS:
        body = json.dumps({"model": model, "max_tokens": 1200, "messages": [{"role": "user", "content": prompt}],
                           "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": api_key})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            print(f"⚠️  web lookup failed: HTTP {e.code} {e.read().decode(errors='ignore')[:160]}")
            return None
        except Exception as e:
            print(f"⚠️  web lookup failed: {e.__class__.__name__}")
            return None
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        found = _read_json(text[text.rfind("{\"found\""):] if "{\"found\"" in text else text)
        if not found or not found.get("found") or not found.get("ingredients"):
            return None
        return {"lines": [str(x) for x in found["ingredients"]][:30], "other": [str(x) for x in found.get("other_ingredients") or []][:20],
                "name": found.get("product_name") or "", "source": "the product's page online", "url": found.get("source_url")}
    return None


def lookup_composition(brand: str | None, product: str | None) -> dict | None:
    if not (brand or product):
        return None
    product = re.sub(r"\s*supplement$", "", product or "", flags=re.I)
    if brand and product.lower().startswith(brand.lower()):
        product = product[len(brand):].strip()
    return dsld_lookup(brand or "", product) or web_lookup(brand or "", product)


class LookupRequest(BaseModel):
    scan_id: str


@app.post("/lookup-composition")
def lookup_composition_endpoint(data: LookupRequest):
    """Front-only photo: find the full ingredient list ourselves, so the user does not have to scan or type anything."""
    scan = load_scan(data.scan_id)
    if scan["product"].get("medicine"):
        raise HTTPException(422, "This is a medicine, not a supplement.")
    company = scan.get("company", {})
    brand = company.get("name") if company.get("status") in ("brand_seen", "verified", "verified_by_brand", "unregistered") else None
    found = lookup_composition(brand, scan["product"].get("name"))
    if not found:
        raise HTTPException(404, "We couldn't find the full ingredient list for this product online.")
    text = " ".join(found["lines"])
    looked = personal_check.read_label(text)
    if not looked["amounts"]:
        raise HTTPException(404, "We couldn't find the full ingredient list for this product online.")
    label = dict(scan.get("label", {}))
    label["amounts"] = {**looked["amounts"], **label.get("amounts", {})}      # the photo's own amounts win
    label["strength"] = personal_check.strength_list(label["amounts"])
    label["all_ingredients"] = all_ingredients(found["lines"], found["other"])
    label["facts_seen"] = True
    label["composition_source"] = {"name": found["source"], "url": found.get("url"), "product": found.get("name")}
    product = dict(scan["product"])
    if not product.get("dataset_key"):
        product["dataset_key"] = composition_key(label["amounts"], text)
    if not product.get("name"):
        product.update(name=found.get("name") or composition_name(label["amounts"], text), identified=True, source="composition")
    product.update(supported=True, from_label=True)
    scan.update(label=label, product=product)
    return {"success": True, **{k: v for k, v in scan.items() if k != "thumb"}}


class LabelTextRequest(BaseModel):
    scan_id: str
    text: str = Field(..., min_length=3, max_length=600)


@app.post("/label-text")
def label_text(data: LabelTextRequest):
    """The user types what the label says (front-only photo, blurry label, loose blister strip).
    The typed amounts are checked exactly like amounts read from a photo."""
    scan = load_scan(data.scan_id)
    text = redact(re.sub(r"[\x00-\x1f<>{}]", " ", data.text))
    if is_medicine_name(text):
        raise HTTPException(422, "That looks like a medicine. MediSafe checks vitamins, minerals and herbal supplements only.")
    typed = personal_check.read_label(text)
    if not typed["amounts"]:
        raise HTTPException(422, "We couldn't find an amount. Write each ingredient with its amount, e.g. Vitamin B6 100 mg, Folic acid 400 mcg.")
    label = dict(scan.get("label", {}))
    label["amounts"] = {**label.get("amounts", {}), **typed["amounts"]}
    label["strength"] = personal_check.strength_list(label["amounts"])
    for k in ("min_age", "age_text", "pregnancy_warning", "directions"):
        label[k] = label.get(k) or typed[k]
    parts = [x.strip() for x in re.split(r"[,;\n]", text) if x.strip()]
    label["all_ingredients"] = all_ingredients(parts, [x for x in parts if not INGREDIENT_LINE.search(x)])
    label["facts_seen"] = True
    label["typed"] = True
    product = dict(scan["product"])
    if not product.get("dataset_key"):
        product["dataset_key"] = composition_key(label["amounts"], text)
    if not product.get("name"):
        name = composition_name(label["amounts"], text)
        brand = scan["company"]["name"] if scan["company"].get("status") == "brand_seen" else None
        if brand:
            name = f"{brand} {name.replace(' supplement', '')}"
        product.update(name=name, identified=True, source="composition")
    product.update(supported=True, from_label=True)
    scan.update(label=label, product=product, ocr_text=(scan.get("ocr_text", "") + " " + text).strip())
    return {"success": True, **{k: v for k, v in scan.items() if k != "thumb"}}


@app.post("/suggest-reasons")
def suggest_reasons(data: ReasonsRequest):
    """Reasons for the 'Why do you take it?' screen: only what this product is used for."""
    scan = load_scan(data.scan_id)
    p = dict(scan["product"])
    if data.name and data.name.strip() and data.name.strip() != p["name"]:
        p.update(name=data.name.strip(), dataset_key=resolve_dataset_key(data.name.strip(), p["ingredients"]))
    # Reasons come from what the product contains (reason_map.json). No AI call here: it only slowed the screen down.
    ai_reasons = []
    herbs = (DSLD.get(p["dataset_key"] or "") or {}).get("herbs", [])
    reasons = personal_check.suggested_reasons(p["name"] or "", p["dataset_key"], scan.get("label", {}).get("amounts", {}),
                                               ai_reasons or None, {"age": data.age or 30, "sex": data.sex, "periods": "yes" if data.periods == "irregular" else data.periods}, herbs)
    return {"reasons": reasons, "source": "ai" if ai_reasons else "dataset"}


@app.post("/safety-report")
def safety_report(data: ReportRequest, user: str = Depends(current_user)):
    scan    = load_scan(data.scan_id)
    company = scan["company"]

    product = dict(scan["product"])
    typed = (data.supplement_name or "").strip()
    renamed = bool(typed and typed != product["name"])
    label = dict(scan.get("label", {}))
    if renamed:
        product.update(name=typed, source="user", dataset_key=resolve_dataset_key(typed, product["ingredients"])
                       or (composition_key(label["amounts"], scan["ocr_text"]) if label.get("amounts") else None))
        label["target"] = personal_check.find_target(typed) or label.get("target")
        if company["status"] in ("not_found", "unregistered"):   # the typed brand may tell us its registered maker
            typed_brand = best_fuzzy_match(word_grams([{"text": typed, "h": 1, "conf": 1}]), list(BRANDS))[0]
            company = {**company, **verify_maker(typed_brand, None, company.get("printed_name"))}
    if not product["name"]:
        raise HTTPException(400, "Product name unknown. Please type the supplement name.")
    if renamed and is_medicine_name(typed):
        raise HTTPException(422, f"{typed} is a medicine, not a supplement. MediSafe only checks vitamins, minerals "
                                 "and herbal supplements, so we can't make a report for it.")
    known = (product["dataset_key"] or label.get("amounts")) if renamed else scan["product"].get("supported")
    if not known:
        raise HTTPException(422, f"We don't have information on {product['name']}. MediSafe checks vitamins, minerals "
                                 "and herbal supplements only, not medicines.")

    # Company verification gate — a known brand printed with a different maker may be counterfeit
    # A different maker than the brand's usual one is a warning in the report, not a stop: brands are often made under licence.


    # Oligomenorrhea (infrequent, unpredictable periods) still means periods: the iron rules treat it like regular periods
    profile = {"age": data.age, "sex": data.sex,
               "periods": ("yes" if data.periods == "irregular" else data.periods) if data.sex == "female" else None,
               "pregnant": data.sex == "female" and data.pregnant,
               "breastfeeding": data.sex == "female" and data.breastfeeding}
    info     = supplement_info.get(product["dataset_key"] or "", {})
    nutrients = list(personal_check.PRODUCTS.get(product["dataset_key"] or "", {}).get("nutrients", [])) \
                + list(scan.get("label", {}).get("amounts", {}))
    foods    = foods_for(product["dataset_key"], nutrients)
    personal = personal_check.assess(product["dataset_key"], label, profile)
    reasons  = personal_check.check_reasons(product["name"], product["dataset_key"],
                                            scan.get("label", {}).get("amounts", {}), data.reasons)
    personal["checks"].insert(0, maker_check(company, product["name"], scan["product"]["source"] == "search"))
    if scan["product"]["source"] == "search":
        nih = DSLD.get(product["dataset_key"] or "")
        personal["checks"].insert(1, {"key": "label", "title": "Label", "status": "info",
            "text": (f"Strength and directions from the product's label in the NIH Dietary Supplement Label Database. "
                     if nih else f"You searched by name, so this uses the usual strength of {product['name']}. ")
                    + "Check that they match the pack you have."})
    elif product["source"] != "ocr" and not scan.get("label", {}).get("amounts"):
        personal["checks"].insert(1, {"key": "label", "title": "Label", "status": "caution",
            "text": (f"We couldn't read the label in your photo, so this uses the usual strength of {product['name']}. "
                     "Check the age limit and directions printed on your pack.") if product.get("dataset_key") else
                    ("We couldn't read what's in this product and couldn't find its ingredient list, so the dose was NOT "
                     "checked. Only the general checks (maker, age, pregnancy) were done. Ask a pharmacist before taking it.")})
    amounts_read = scan.get("label", {}).get("strength") if scan["product"]["source"] != "search" else None
    if amounts_read:                               # say plainly that THIS pack's composition was checked
        lab = scan.get("label", {})
        extra = [x["name"] + (f" {x['amount']}" if x.get("amount") else "") for x in lab.get("all_ingredients", []) if not x["checked"]]
        src = lab.get("composition_source")
        text = (("Checked with the amounts you entered from the label: " if lab.get("typed") else
                 f"Checked with the full ingredient list from {src['name']}: " if src else
                 "Checked with the amounts printed on your pack: ")
                + "; ".join(f"{x['nutrient']} {x['amount']}" for x in amounts_read)
                + ". Each amount is compared with the NIH limits for your age and sex.")
        if extra:
            text += " Also on the label: " + ", ".join(extra[:8]) + ". These have no NIH limit, so they are listed, not checked."
        if src:
            text += " Your photo showed only the front, so we looked this product up. Check that the strength on your pack matches."
        if not lab.get("facts_seen", True):
            text += (" We only saw the front of the pack. The full ingredient list (\"Supplement Facts\") is usually on the back:"
                     " scan it too to check everything inside.")
        personal["checks"].insert(1, {"key": "composition", "title": "What's in your pack",
                                      "status": "ok" if lab.get("facts_seen", True) else "info", "text": text})
    reason_row = personal_check.reason_check_row(reasons)
    if reason_row:
        personal["checks"].insert(1, reason_row)
    personal["reasons"] = reasons
    if personal["verdict"] == "Safe" and any(c["status"] in ("caution", "stop") for c in personal["checks"]):
        personal["verdict"] = "Use with caution"
    ai       = ai_safety_report(product, company["name"], profile, data.reasons, scan["ocr_text"], info, foods, personal)
    report   = build_report(personal, ai, info, foods)
    ai_info  = {"used": ai is not None, "problem": None if ai else AI_STATUS["reason"]}

    response = {"query_id": None, "product": product, "company": company, "profile": profile,
                "reasons": data.reasons, "report": report, "ai": ai_info}
    if not USE_FIREBASE:
        return response

    # Save in the supervisor's two collections. Both documents share one id, which links them.
    female_status = ({**{k: profile[k] for k in ("periods", "pregnant", "breastfeeding")}, "periods": data.periods}
                     if data.sex == "female" else None)
    query = fs.collection("search_query_data").document()
    query.set({
        "user_id": user, "input_image": scan["thumb"], "supplement_name": product["name"],
        "company": company["name"], "age": data.age, "sex": data.sex, "female_status": female_status,
        "reason_to_taking": [redact(r) for r in data.reasons], "timestamp": firestore.SERVER_TIMESTAMP,
    })
    fs.collection("search_response").document(query.id).set({
        "query_id": query.id, "user_id": user,
        "is_safe_to_take": report["is_safe_to_take"], "actual_supplement_usage": report["actual_usage"],
        "benefits": report["benefits"], "recommended_dosage": report["recommended_dosage"],
        "side_effects": report["side_effects"], "recommended_foods": report["recommended_foods"],
        "foods_to_avoid": report["foods_to_avoid"], "full_report": {**response, "query_id": query.id},
        "timestamp": firestore.SERVER_TIMESTAMP,
    })
    response["query_id"] = query.id
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNT: profile + history (Firestore)
# ═══════════════════════════════════════════════════════════════════════════════

USERNAME_OK = re.compile(r"^[a-z0-9_.]{3,20}$")


def age_from_dob(dob: str) -> int:
    """Age in whole years today, so it goes up by itself on every birthday."""
    born = datetime.date.fromisoformat(dob)
    today = datetime.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def check_dob(v):
    if not v:
        return None
    try:
        born = datetime.date.fromisoformat(v)
    except ValueError:
        raise ValueError("Date of birth must be a real date (DD/MM/YYYY).")
    if born > datetime.date.today():
        raise ValueError("Date of birth can't be in the future.")
    if not 1 <= age_from_dob(v) <= 120:
        raise ValueError("Age must be between 1 and 120.")
    return v


class Profile(BaseModel):
    name: str = Field("", max_length=40)
    username: Optional[str] = Field(None, max_length=20)
    dob: Optional[str] = None                      # YYYY-MM-DD; when given, age is worked out from it
    age: Optional[int] = Field(None, ge=1, le=120)
    sex: Literal["male", "female"]
    periods: Optional[Literal["yes", "irregular", "no"]] = None
    pregnant: bool = False
    breastfeeding: bool = False

    @field_validator("username")
    @classmethod
    def username_ok(cls, v):
        if v in (None, ""):
            return None
        v = v.strip().lower()
        if not USERNAME_OK.match(v):
            raise ValueError("Username must be 3-20 characters: small letters, numbers, dot or underscore.")
        return v

    @field_validator("dob")
    @classmethod
    def dob_ok(cls, v):
        return check_dob(v)

    @model_validator(mode="before")
    @classmethod
    def age_from_birthday(cls, d):
        if isinstance(d, dict) and d.get("dob"):
            try:
                d = {**d, "age": age_from_dob(d["dob"])}
            except (ValueError, TypeError):
                pass                                # dob_ok reports the bad date
        if isinstance(d, dict) and d.get("age") is None and not d.get("dob"):
            raise ValueError("Please enter your date of birth.")
        return d

    @field_validator("name")
    @classmethod
    def name_is_a_name(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v or "").strip()
        if v and not NAME_OK.match(v):
            raise ValueError("Name can only have letters and spaces (2-40). Don't put a phone number or email in it.")
        return v

    @model_validator(mode="after")
    def health_fields_agree(self):
        return check_health_fields(self)


class EmailRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)


@app.post("/account-exists")
def account_exists(data: EmailRequest):
    """Forgot password: tell the user if no account uses this email, instead of a silent 'we sent it'."""
    if not USE_FIREBASE:
        return {"exists": None}
    try:
        fb_auth.get_user_by_email(data.email.strip())
        return {"exists": True}
    except fb_auth.UserNotFoundError:
        return {"exists": False}
    except Exception:
        return {"exists": None}


class AvailableRequest(BaseModel):
    email: Optional[str] = Field(None, max_length=120)
    username: Optional[str] = Field(None, max_length=20)


def username_owner(username: str) -> str | None:
    """Account id that uses this username, if any."""
    found = fs.collection("users").where(filter=firestore.FieldFilter("username", "==", username.lower())).limit(1).get()
    return found[0].id if found else None


@app.post("/auth/available")
def available(data: AvailableRequest):
    """Sign up: is this email or username already used by another account?"""
    out = {"email_taken": None, "username_taken": None}
    if not USE_FIREBASE:
        return out
    if data.email:
        try:
            fb_auth.get_user_by_email(data.email.strip())
            out["email_taken"] = True
        except fb_auth.UserNotFoundError:
            out["email_taken"] = False
        except Exception:
            pass
    if data.username:
        out["username_taken"] = username_owner(data.username.strip()) is not None
    return out


class LoginLookup(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=120)


_lookups: dict = {}


@app.post("/auth/login-email")
def login_email(data: LoginLookup, request: Request):
    """Sign in with a username: find the account's email so the app can sign in with Firebase.
    Limited to 10 tries a minute per phone, so usernames can't be used to collect emails."""
    ip = request.client.host if request.client else "?"
    now = time.time()
    _lookups[ip] = [t for t in _lookups.get(ip, []) if now - t < 60] + [now]
    if len(_lookups[ip]) > 10:
        raise HTTPException(429, "Too many tries. Wait a minute and try again.")
    ident = data.identifier.strip()
    if "@" in ident:
        return {"email": ident}
    if not USE_FIREBASE:
        raise HTTPException(404, "No account with this username.")
    owner = username_owner(ident)
    if not owner:
        raise HTTPException(404, "No account with this username. Check it, or sign up.")
    return {"email": fb_auth.get_user(owner).email}


def profile_out(d: dict) -> dict:
    if d.get("dob"):
        try:
            d["age"] = age_from_dob(d["dob"])          # always today's age
        except ValueError:
            pass
    d.pop("updated", None)
    return d


@app.get("/profile")
def get_profile(user: str = Depends(current_user)):
    if not USE_FIREBASE:
        return {"profile": None}
    doc = fs.collection("users").document(user).get()
    if not doc.exists:
        return {"profile": None}
    d = profile_out(doc.to_dict())
    if user != "local":
        try:
            d["email"] = fb_auth.get_user(user).email
        except Exception:
            pass
    return {"profile": d}


@app.put("/profile")
def save_profile(data: Profile, user: str = Depends(current_user)):
    if USE_FIREBASE:
        if data.username and username_owner(data.username) not in (None, user):
            raise HTTPException(409, "This username is already taken. Try another one.")
        fs.collection("users").document(user).set({**data.model_dump(), "updated": firestore.SERVER_TIMESTAMP}, merge=True)
    return {"saved": USE_FIREBASE}


class PhotoRequest(BaseModel):
    image: str = Field(..., max_length=400_000)       # data:image/jpeg;base64,... (the app shrinks it to 300 px first)


@app.put("/profile/photo")
def save_photo(data: PhotoRequest, user: str = Depends(current_user)):
    """Profile picture, kept small (about 20 KB) in the user's own record."""
    m = re.match(r"^data:image/(jpeg|png);base64,([A-Za-z0-9+/=]+)$", data.image)
    if not m:
        raise HTTPException(422, "Please choose a JPEG or PNG photo.")
    try:
        Image.open(io.BytesIO(base64.b64decode(m.group(2)))).verify()
    except Exception:
        raise HTTPException(422, "That file is not a photo we can read.")
    if USE_FIREBASE:
        fs.collection("users").document(user).set({"photo": data.image}, merge=True)
    return {"saved": USE_FIREBASE}


@app.delete("/profile/photo")
def delete_photo(user: str = Depends(current_user)):
    if USE_FIREBASE:
        fs.collection("users").document(user).set({"photo": firestore.DELETE_FIELD}, merge=True)
    return {"deleted": USE_FIREBASE}


@app.get("/history")
def history(user: str = Depends(current_user)):
    """This user's past checks, newest first."""
    if not USE_FIREBASE:
        return {"history": []}
    queries = [d for d in fs.collection("search_query_data").where(filter=firestore.FieldFilter("user_id", "==", user)).stream()]
    stamp = lambda d: d.to_dict().get("timestamp")
    queries.sort(key=lambda d: (stamp(d) is not None, stamp(d) or 0), reverse=True)
    queries = queries[:30]
    responses = {r.id: r for r in fs.get_all([fs.collection("search_response").document(q.id) for q in queries])} if queries else {}
    items = []
    for q in queries:
        qd, r = q.to_dict(), responses.get(q.id)
        verdict = (r.get("is_safe_to_take") or {}).get("verdict") if r and r.exists else None
        items.append({"id": q.id, "name": qd.get("supplement_name"), "verdict": verdict,
                      "date": qd["timestamp"].isoformat() if qd.get("timestamp") else None,
                      "for": f"{'Female' if qd.get('sex') == 'female' else 'Male'}, {qd.get('age')}"})
    return {"history": items}


@app.get("/report/{query_id}")
def saved_report(query_id: str, user: str = Depends(current_user)):
    """Open a past report from history."""
    if not USE_FIREBASE:
        raise HTTPException(404, "Reports are not saved without the database.")
    doc = fs.collection("search_response").document(query_id).get()
    if not doc.exists or doc.get("user_id") != user:
        raise HTTPException(404, "Report not found.")
    return {**doc.get("full_report"), "thumb": fs.collection("search_query_data").document(query_id).get().get("input_image")}


def _warm_up():
    """The first OCR / CLIP run after starting is slow (the models get ready). Do it once now, not on the user's scan."""
    try:
        from PIL import ImageDraw
        img = Image.new("RGB", (400, 160), "white")
        ImageDraw.Draw(img).text((20, 60), "Vitamin C 500 mg", fill="black")
        reader.readtext(np.array(img))
        photo_is_supplement(img)
        print("✓ OCR and photo check ready")
    except Exception as e:
        print(f"Warm-up skipped: {e}")


if not TESTING:
    import threading
    threading.Thread(target=_warm_up, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
