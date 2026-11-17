# MediSafe AI

A mobile app that tells you whether a dietary supplement is safe **for you**. Take one photo of the pack (or search by name) and get a personal safety report: who made it, whether the dose suits your age and sex, which foods to eat with it or keep apart, and a clear verdict — **Safe**, **Use with caution** or **Not safe**.

> For information only. Always follow your doctor's advice.

## How it works

1. **Validate the photo** – CLIP (ViT-B/32) checks the photo really shows a supplement pack.
2. **Read the label** – EasyOCR reads the brand, ingredients, strengths, directions and maker.
3. **Identify the product** – brand keywords and fuzzy matching tolerate OCR mistakes. A brand that is not in the data is checked from the **composition printed on its own label**, so two brands of the same vitamin get their own results.
4. **Verify the manufacturer** – compared with a list of verified companies; a different maker from the brand's known one is flagged as a possible fake.
5. **Personal checks** – a rules engine compares every amount on the label with the NIH Office of Dietary Supplements limits for the user's age and sex (16 nutrients), plus pregnancy, breastfeeding, periods, who the product is made for, and the user's reasons for taking it.
6. **Food guidance** – a Random Forest model (99.1% test accuracy) predicts which fruits and vegetables to eat with the supplement or keep apart from it.
7. **Explain** – Claude writes a plain-language explanation. The AI can only make a verdict stricter, never more lenient.

## Tech stack

| Part | Technology |
|---|---|
| Mobile app | React Native, Expo, Formik + Yup |
| Backend | Python, FastAPI, Pydantic |
| Vision | EasyOCR, CLIP (Hugging Face Transformers, PyTorch) |
| Machine learning | scikit-learn Random Forest |
| Accounts and data | Firebase Authentication, Cloud Firestore |
| AI | Claude (Anthropic API), with Groq / Gemini as backups |
| Tests | pytest — 129 automated tests |

## Run it

**Backend**

```
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Create `backend/.env` with `ANTHROPIC_API_KEY=...`, and put your Firebase service-account file at `backend/firebase-key.json`. Both are git-ignored and must never be committed.

**Mobile app**

```
cd frontend
npm install
npx expo start
```

Set `API_BASE` in `frontend/config.js` to your computer's address (e.g. `http://192.168.x.x:8000`) and open the app in Expo Go.

**Tests**

```
cd backend
python -m pytest tests -v
```

## Data sources

NIH Office of Dietary Supplements (nutrient limits), NIH Dietary Supplement Label Database (718 product labels), USDA FoodData Central (food composition).

## Author

Izza Maryam — [github.com/izza-m1](https://github.com/izza-m1)
