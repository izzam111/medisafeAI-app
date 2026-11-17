# MediSafe AI — automated tests

139 test cases, written in code with **pytest**. No GUI is needed: each test calls the backend directly.

## Run them

From the `backend` folder, with the venv active:

```
pip install pytest httpx
python -m pytest tests -v
```

The tests run in **test mode** (`MEDISAFE_TESTING=1`, set in `conftest.py`):

- Firebase is switched off, so the tests never write to the real database.
- The AI is switched off, so no data is sent to any model.
- The camera/OCR step is given fixed label text, so every run gives the same answer.

Everything else is the real code: the CLIP model, the datasets (NIH limits, NIH label database, USDA foods),
the rules engine and the trained Random Forest food model.

## Test cases

| ID | File | What it checks | Cases |
|---|---|---|---|
| TC-1 | `test_1_profile_validation.py` | Valid profiles are saved; a phone number or email as a name, a wrong age, a pregnant male, a pregnant 9-year-old, a future or impossible date of birth, a bad username etc. are refused with a clear message; age is worked out from the date of birth; sign-in by username | 35 |
| TC-2 | `test_2_privacy.py` | Emails, phone numbers, CNIC numbers and links are removed from text; the AI (Claude) never gets the name, username, email, date of birth or photo | 10 |
| TC-3 | `test_3_scan.py` | Non-supplement photo rejected (CLIP); brand read by OCR; OCR mistakes tolerated; product versions (Men, Kids) detected; scratched name identified from ingredients; medicines recognised; maker verified | 10 |
| TC-4 | `test_4_safety_rules.py` | Verdict colour (green/orange/red) for 13 products × men, boys, girls, women with periods, pregnant, breastfeeding, after menopause, elderly | 45 |
| TC-5 | `test_5_reasons.py` | Reasons offered only fit the supplement; women-only reasons hidden for men; an illness or unrelated reason turns the report red; "Everyday nutrition" only offered when it fits | 11 |
| TC-6 | `test_6_food_and_dose.py` | Fruits/vegetables to eat with it and keep apart; never both; only fruits and vegetables; dose and short course; strength compared with the NIH limit; '10,000 IU' read as ten thousand | 7 |
| TC-7 | `test_7_search_and_medicines.py` | Search list (local + NIH); NIH label data; medicines and unknown names are refused | 6 |
| TC-8 | `test_8_unknown_brands.py` | A brand not in our data (e.g. a Nutrifactor B3) is checked from the composition printed on its own label; two brands of the same vitamin with different strengths get different results; a child is stopped by a strong pack; an unknown iron product follows the iron rules; the report says the pack's own amounts were used; a brand with no 'Manufactured by' line is shown as the company; every ingredient on the label is listed; the report asks for the back when only the front was seen; amounts the user types from the label are checked the same way; a front-only photo gets the full ingredient list by lookup (NIH database or the brand's site) without overriding the pack's own amounts; a product with no composition found is never called safe | 15 |

## For the documentation

Take a screenshot of the terminal after `python -m pytest tests -v`, or run one section at a time,
for example `python -m pytest tests/test_4_safety_rules.py -v`, and screenshot each.
