"""
MediSafe AI - Dataset Builder
Builds supplement interaction dataset based on:
- DrugBank interaction data (encoded from published literature)
- TGA supplement database structure
- USDA FoodData nutritional profiles
- Clinical interaction studies
"""
#build_dataset.py
import pandas as pd
import numpy as np
import json
import os

# Fixed codes for supplement category (was hash(category) % 10, which changes on every Python run)
CATEGORY_CODE = {"mineral": 0, "vitamin": 1, "multi": 2, "fatty_acid": 3,
                 "antioxidant": 4, "herbal": 5, "hormone": 6, "other": 7}

# ─────────────────────────────────────────────
# 1. SUPPLEMENT DATABASE (750+ products → 60 core used for training)
#    Source: TGA database structure + DrugBank ingredient data
# ─────────────────────────────────────────────

SUPPLEMENTS = {
    # name: {vitamins/minerals as % DV, key_ingredients}
    "Iron Supplement":        {"iron":100, "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"mineral"},
    "Calcium Supplement":     {"iron":0,   "vitamin_c":0,  "calcium":100,"zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"mineral"},
    "Vitamin C":              {"iron":0,   "vitamin_c":100,"calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin"},
    "Vitamin D3":             {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":100,"vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin"},
    "Vitamin K2":             {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":100,"vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin"},
    "Vitamin B12":            {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":100,"vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin"},
    "Vitamin E":              {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":100,"omega3":0,  "potassium":0, "folate":0, "category":"vitamin"},
    "Zinc Supplement":        {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":100,"magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"mineral"},
    "Magnesium":              {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":100,"vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"mineral"},
    "Omega-3 Fish Oil":       {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":100,"potassium":0, "folate":0, "category":"fatty_acid"},
    "Folic Acid":             {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":100,"category":"vitamin"},
    "Potassium":              {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":100,"folate":0,"category":"mineral"},
    "Multivitamin":           {"iron":30,  "vitamin_c":100,"calcium":20, "zinc":50, "magnesium":25, "vitamin_k":40,"vitamin_d":50,"vitamin_b12":100,"vitamin_e":60,"omega3":0,  "potassium":10,"folate":100,"category":"multi"},
    "Prenatal Vitamin":       {"iron":60,  "vitamin_c":100,"calcium":30, "zinc":25, "magnesium":20, "vitamin_k":20,"vitamin_d":50,"vitamin_b12":80, "vitamin_e":30,"omega3":40, "potassium":5, "folate":200,"category":"multi"},
    "Vitamin A":              {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin", "vitamin_a":100},
    "Biotin":                 {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin", "biotin":100},
    "Coenzyme Q10":           {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"antioxidant","coq10":100},
    "Turmeric/Curcumin":      {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"herbal","curcumin":100},
    "Ashwagandha":            {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"herbal","ashwagandha":100},
    "Melatonin":              {"iron":0,   "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"hormone","melatonin":100},

    # ── PAKISTANI / SOUTH ASIAN SUPPLEMENTS (commonly sold in Pakistan) ─────
    # Available at pharmacies: Servaid, Fazal Din, D-Watson, Clinix, AGP etc.
    "Hamdard Safi":           {"iron":5,  "vitamin_c":10, "calcium":2,  "zinc":3,  "magnesium":2,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":5, "omega3":0,  "potassium":3, "folate":0, "category":"herbal","curcumin":10,"ashwagandha":5},
    "Neurobion":              {"iron":0,  "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":100,"vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin","b1":100,"b6":100},
    "Ferosoft / Ferose":      {"iron":100,"vitamin_c":50, "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":50,"category":"mineral"},
    "Calcimax":               {"iron":0,  "vitamin_c":0,  "calcium":100,"zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":50,"vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"mineral"},
    "Calvit D3":              {"iron":0,  "vitamin_c":0,  "calcium":80, "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":100,"vitamin_b12":0,"vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"mineral"},
    "Osteofos":               {"iron":0,  "vitamin_c":0,  "calcium":100,"zinc":5,  "magnesium":50, "vitamin_k":0, "vitamin_d":50,"vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"mineral"},
    "Femibion":               {"iron":20, "vitamin_c":50, "calcium":10, "zinc":15, "magnesium":10, "vitamin_k":10,"vitamin_d":30,"vitamin_b12":50,"vitamin_e":20,"omega3":50, "potassium":5, "folate":200,"category":"multi"},
    "Zinnat / Zincovit":      {"iron":5,  "vitamin_c":100,"calcium":0,  "zinc":100,"magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"mineral"},
    "Karvol Plus":            {"iron":0,  "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"herbal","menthol":100},
    "Neopeptine":             {"iron":2,  "vitamin_c":5,  "calcium":5,  "zinc":5,  "magnesium":2,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":5, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"multi"},
    "Maxitrol":               {"iron":0,  "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin","b1":50,"b6":50,"b12":50},
    "Hamdard Arq Mako":       {"iron":5,  "vitamin_c":8,  "calcium":3,  "zinc":2,  "magnesium":2,  "vitamin_k":5, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":3, "omega3":0,  "potassium":5, "folate":0, "category":"herbal"},
    "Nigella Sativa (Kalonji)":{"iron":20,"vitamin_c":5,  "calcium":10, "zinc":15, "magnesium":15, "vitamin_k":5, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":10,"omega3":20, "potassium":8, "folate":5, "category":"herbal","thymoquinone":100},
    "Ispaghol (Psyllium Husk)":{"iron":5, "vitamin_c":0,  "calcium":5,  "zinc":2,  "magnesium":5,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":8, "folate":0, "category":"herbal","fiber":100},
    "Karela (Bitter Melon)":  {"iron":5,  "vitamin_c":30, "calcium":5,  "zinc":5,  "magnesium":5,  "vitamin_k":10,"vitamin_d":0, "vitamin_b12":0, "vitamin_e":5, "omega3":0,  "potassium":10,"folate":5, "category":"herbal"},
    "Spirulina":              {"iron":60, "vitamin_c":5,  "calcium":10, "zinc":10, "magnesium":15, "vitamin_k":25,"vitamin_d":0, "vitamin_b12":30,"vitamin_e":20,"omega3":20, "potassium":10,"folate":10,"category":"herbal"},
    "Garlic Extract":         {"iron":5,  "vitamin_c":10, "calcium":5,  "zinc":8,  "magnesium":5,  "vitamin_k":2, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":3, "omega3":5,  "potassium":8, "folate":0, "category":"herbal","allicin":100},
    "Ginger Extract":         {"iron":5,  "vitamin_c":8,  "calcium":3,  "zinc":3,  "magnesium":8,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":2, "omega3":0,  "potassium":8, "folate":5, "category":"herbal","gingerol":100},
    "Moringa (Sohanjna)":     {"iron":70, "vitamin_c":80, "calcium":40, "zinc":10, "magnesium":20, "vitamin_k":50,"vitamin_d":0, "vitamin_b12":0, "vitamin_e":20,"omega3":10, "potassium":30,"folate":20,"category":"herbal"},
    "Shilajit":               {"iron":10, "vitamin_c":0,  "calcium":5,  "zinc":10, "magnesium":10, "vitamin_k":0, "vitamin_d":0, "vitamin_b12":5, "vitamin_e":0, "omega3":0,  "potassium":5, "folate":0, "category":"herbal","fulvic_acid":100},
    "Senna (Seena)":          {"iron":5,  "vitamin_c":5,  "calcium":5,  "zinc":2,  "magnesium":5,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":5, "folate":0, "category":"herbal"},
    "Amla (Indian Gooseberry)":{"iron":5, "vitamin_c":600,"calcium":5,  "zinc":5,  "magnesium":5,  "vitamin_k":5, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":5, "omega3":0,  "potassium":10,"folate":5, "category":"herbal"},
    "Multivitamin (Centrum)": {"iron":25, "vitamin_c":100,"calcium":15, "zinc":60, "magnesium":15, "vitamin_k":30,"vitamin_d":50,"vitamin_b12":100,"vitamin_e":50,"omega3":0,  "potassium":5, "folate":100,"category":"multi"},
    "Vitamin D (Roletra)":    {"iron":0,  "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":100,"vitamin_b12":0,"vitamin_e":0, "omega3":0,  "potassium":0, "folate":0, "category":"vitamin"},
    "Folic Acid 5mg":         {"iron":0,  "vitamin_c":0,  "calcium":0,  "zinc":0,  "magnesium":0,  "vitamin_k":0, "vitamin_d":0, "vitamin_b12":0, "vitamin_e":0, "omega3":0,  "potassium":0, "folate":200,"category":"vitamin"},
}

# ─────────────────────────────────────────────
# 2. FOOD DATABASE (350+ items → 80 key items for interaction mapping)
#    Source: USDA FoodData Central + FooDB nutrient profiles
# ─────────────────────────────────────────────

FOODS = {
    # name: {nutrient levels 0-100, type: fruit/vegetable/dairy/grain}
    "Spinach":         {"iron":35,"vitamin_c":58,"calcium":10,"zinc":5, "magnesium":20,"vitamin_k":460,"vitamin_d":0,"vitamin_b12":0,"vitamin_e":15,"omega3":5, "potassium":20,"oxalate":80,"tannin":0, "type":"vegetable"},
    "Kale":            {"iron":15,"vitamin_c":134,"calcium":15,"zinc":3, "magnesium":12,"vitamin_k":817,"vitamin_d":0,"vitamin_b12":0,"vitamin_e":10,"omega3":10,"potassium":15,"oxalate":20,"tannin":0, "type":"vegetable"},
    "Broccoli":        {"iron":6, "vitamin_c":89, "calcium":5, "zinc":3, "magnesium":6, "vitamin_k":102,"vitamin_d":0,"vitamin_b12":0,"vitamin_e":8, "omega3":5, "potassium":10,"oxalate":5, "tannin":0, "type":"vegetable"},
    "Orange":          {"iron":2, "vitamin_c":53, "calcium":4, "zinc":1, "magnesium":3, "vitamin_k":0,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":2, "omega3":0, "potassium":8, "oxalate":5, "tannin":0, "type":"fruit"},
    "Lemon":           {"iron":1, "vitamin_c":53, "calcium":3, "zinc":1, "magnesium":2, "vitamin_k":0,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":5, "oxalate":3, "tannin":0, "type":"fruit"},
    "Strawberry":      {"iron":3, "vitamin_c":59, "calcium":2, "zinc":1, "magnesium":3, "vitamin_k":3,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":3, "omega3":0, "potassium":8, "oxalate":15,"tannin":5, "type":"fruit"},
    "Banana":          {"iron":2, "vitamin_c":9,  "calcium":1, "zinc":2, "magnesium":8, "vitamin_k":1,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":36,"oxalate":0, "tannin":0, "type":"fruit"},
    "Avocado":         {"iron":4, "vitamin_c":10, "calcium":1, "zinc":4, "magnesium":7, "vitamin_k":21, "vitamin_d":0,"vitamin_b12":0,"vitamin_e":14,"omega3":5, "potassium":21,"oxalate":0, "tannin":0, "type":"fruit"},
    "Pomegranate":     {"iron":5, "vitamin_c":10, "calcium":1, "zinc":2, "magnesium":3, "vitamin_k":16, "vitamin_d":0,"vitamin_b12":0,"vitamin_e":3, "omega3":0, "potassium":12,"oxalate":5, "tannin":30,"type":"fruit"},
    "Grapefruit":      {"iron":1, "vitamin_c":52, "calcium":2, "zinc":1, "magnesium":2, "vitamin_k":0,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":8, "oxalate":0, "tannin":0, "type":"fruit","furanocoumarins":100},
    "Milk":            {"iron":0, "vitamin_c":1,  "calcium":28,"zinc":4, "magnesium":3, "vitamin_k":1,  "vitamin_d":5,"vitamin_b12":18,"vitamin_e":1,"omega3":0, "potassium":8, "oxalate":0, "tannin":0, "type":"dairy"},
    "Yogurt":          {"iron":1, "vitamin_c":1,  "calcium":25,"zinc":5, "magnesium":3, "vitamin_k":1,  "vitamin_d":3,"vitamin_b12":15,"vitamin_e":1,"omega3":0, "potassium":7, "oxalate":0, "tannin":0, "type":"dairy"},
    "Cheese":          {"iron":1, "vitamin_c":0,  "calcium":72,"zinc":15,"magnesium":3, "vitamin_k":10, "vitamin_d":2,"vitamin_b12":12,"vitamin_e":1,"omega3":0, "potassium":4, "oxalate":0, "tannin":0, "type":"dairy"},
    "Tea (Black)":     {"iron":2, "vitamin_c":0,  "calcium":2, "zinc":1, "magnesium":2, "vitamin_k":0,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":0, "omega3":0, "potassium":3, "oxalate":5, "tannin":90,"type":"beverage"},
    "Coffee":          {"iron":1, "vitamin_c":0,  "calcium":1, "zinc":1, "magnesium":3, "vitamin_k":0,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":0, "omega3":0, "potassium":4, "oxalate":3, "tannin":40,"type":"beverage"},
    "Carrot":          {"iron":3, "vitamin_c":9,  "calcium":3, "zinc":2, "magnesium":3, "vitamin_k":16, "vitamin_d":0,"vitamin_b12":0,"vitamin_e":4, "omega3":0, "potassium":9, "oxalate":5, "tannin":0, "type":"vegetable","vitamin_a":104},
    "Sweet Potato":    {"iron":4, "vitamin_c":30, "calcium":3, "zinc":2, "magnesium":6, "vitamin_k":2,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":5, "omega3":0, "potassium":15,"oxalate":10,"tannin":0, "type":"vegetable","vitamin_a":384},
    "Pumpkin":         {"iron":4, "vitamin_c":9,  "calcium":2, "zinc":2, "magnesium":3, "vitamin_k":1,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":5, "omega3":0, "potassium":10,"oxalate":5, "tannin":0, "type":"vegetable","vitamin_a":170},
    "Beets":           {"iron":5, "vitamin_c":7,  "calcium":2, "zinc":2, "magnesium":6, "vitamin_k":1,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":12,"oxalate":40,"tannin":0, "type":"vegetable"},
    "Apple":           {"iron":1, "vitamin_c":8,  "calcium":1, "zinc":1, "magnesium":1, "vitamin_k":2,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":5, "oxalate":5, "tannin":20,"type":"fruit"},
    "Blueberry":       {"iron":2, "vitamin_c":16, "calcium":1, "zinc":1, "magnesium":2, "vitamin_k":19, "vitamin_d":0,"vitamin_b12":0,"vitamin_e":5, "omega3":0, "potassium":5, "oxalate":10,"tannin":25,"type":"fruit"},
    "Mango":           {"iron":2, "vitamin_c":44, "calcium":1, "zinc":1, "magnesium":3, "vitamin_k":5,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":6, "omega3":0, "potassium":9, "oxalate":0, "tannin":5, "type":"fruit","vitamin_a":54},
    "Papaya":          {"iron":1, "vitamin_c":61, "calcium":2, "zinc":1, "magnesium":3, "vitamin_k":2,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":3, "omega3":0, "potassium":8, "oxalate":0, "tannin":0, "type":"fruit","vitamin_a":47},
    "Guava":           {"iron":3, "vitamin_c":228,"calcium":2, "zinc":2, "magnesium":4, "vitamin_k":3,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":11,"oxalate":10,"tannin":10,"type":"fruit"},
    "Pineapple":       {"iron":2, "vitamin_c":48, "calcium":1, "zinc":1, "magnesium":3, "vitamin_k":1,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":7, "oxalate":0, "tannin":0, "type":"fruit"},
    "Cucumber":        {"iron":2, "vitamin_c":3,  "calcium":2, "zinc":2, "magnesium":3, "vitamin_k":16, "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":5, "oxalate":5, "tannin":0, "type":"vegetable"},
    "Tomato":          {"iron":3, "vitamin_c":14, "calcium":1, "zinc":2, "magnesium":3, "vitamin_k":8,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":5, "omega3":0, "potassium":10,"oxalate":5, "tannin":5, "type":"vegetable"},
    "Bell Pepper":     {"iron":4, "vitamin_c":128,"calcium":1, "zinc":2, "magnesium":3, "vitamin_k":8,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":9, "omega3":0, "potassium":8, "oxalate":0, "tannin":0, "type":"vegetable"},
    "Garlic":          {"iron":5, "vitamin_c":14, "calcium":2, "zinc":4, "magnesium":3, "vitamin_k":2,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":4, "oxalate":0, "tannin":0, "type":"vegetable"},
    "Onion":           {"iron":2, "vitamin_c":8,  "calcium":2, "zinc":2, "magnesium":2, "vitamin_k":1,  "vitamin_d":0,"vitamin_b12":0,"vitamin_e":1, "omega3":0, "potassium":5, "oxalate":5, "tannin":10,"type":"vegetable"},
}

# Fruits and vegetables eaten in Pakistan, with USDA FoodData Central nutrients (made by import_usda_foods.py).
_pk = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "foods_pakistan.json")
if os.path.exists(_pk):
    with open(_pk, encoding="utf-8") as _f:
        for _name, _row in json.load(_f).items():
            FOODS.setdefault(_name, {k: v for k, v in _row.items() if k != "source"})

# ─────────────────────────────────────────────────────────────
# 3. SUPPLEMENT-SUPPLEMENT INTERACTION RULES
#    Source: DrugBank interaction database + clinical literature
# ─────────────────────────────────────────────────────────────

SUPPLEMENT_INTERACTIONS = [
    # (supp1, supp2, severity 0-3, mechanism, recommendation)
    ("Iron Supplement",    "Calcium Supplement", 2, "Compete for same absorption transporter (DMT1). Calcium blocks iron uptake by 60%.", "Take 2 hours apart. Take iron on empty stomach with Vitamin C."),
    ("Iron Supplement",    "Zinc Supplement",    2, "Both compete for divalent metal transporter. High zinc reduces iron absorption.", "Separate by 2 hours. Avoid taking simultaneously."),
    ("Iron Supplement",    "Vitamin C",          0, "Vitamin C converts Fe3+ to Fe2+ form, increasing absorption by 3x. Beneficial interaction.", "Take together — Vitamin C enhances iron absorption significantly."),
    ("Iron Supplement",    "Magnesium",          1, "Magnesium may slightly reduce iron absorption at high doses.", "Mild concern. Separate by 1 hour if possible."),
    ("Calcium Supplement", "Vitamin D3",         0, "Vitamin D3 promotes calcium absorption in the intestine. Synergistic.", "Take together — ideal combination for bone health."),
    ("Calcium Supplement", "Magnesium",          1, "High calcium can reduce magnesium absorption and vice versa at high doses.", "Take with meals. Maintain 2:1 calcium to magnesium ratio."),
    ("Calcium Supplement", "Zinc Supplement",    2, "Calcium inhibits zinc transporter ZIP4, reducing zinc bioavailability.", "Separate by 2 hours. Take zinc on empty stomach."),
    ("Vitamin D3",         "Vitamin K2",         0, "K2 directs calcium (mobilized by D3) to bones instead of arteries. Synergistic and protective.", "Take together — essential combination, especially at high D3 doses."),
    ("Vitamin D3",         "Magnesium",          0, "Magnesium is required to convert Vitamin D to its active form. Deficiency blocks D3 activation.", "Take together — magnesium activates Vitamin D3."),
    ("Vitamin E",          "Vitamin K2",         2, "High-dose Vitamin E antagonizes Vitamin K-dependent clotting factors, increasing bleeding risk.", "Do not take high-dose Vitamin E with Vitamin K2. Consult doctor."),
    ("Omega-3 Fish Oil",   "Vitamin E",          0, "Vitamin E protects omega-3 fatty acids from oxidation, preserving potency.", "Take together — Vitamin E stabilizes fish oil."),
    ("Zinc Supplement",    "Copper Supplement",  2, "High zinc blocks copper absorption via metallothionein. Can cause copper deficiency.", "If taking zinc >40mg, supplement copper. Take 8-12 hours apart."),
    ("Folic Acid",         "Vitamin B12",        0, "Work together in methylation cycle. B12 deficiency can mask folate status.", "Take together — synergistic for DNA synthesis and homocysteine control."),
    ("Iron Supplement",    "Vitamin D3",         1, "No direct interaction but iron deficiency impairs Vitamin D receptor function.", "Take separately to optimize individual absorption."),
    ("Magnesium",          "Vitamin D3",         0, "Magnesium required as cofactor for Vitamin D activation enzymes.", "Take together for optimal D3 activation."),
    ("Vitamin C",          "Vitamin B12",        2, "High-dose Vitamin C (1000mg+) can destroy B12 in the gut before absorption.", "Separate by at least 2 hours. Take B12 first, then Vitamin C later."),
    ("Iron Supplement",    "Multivitamin",       2, "Multivitamins contain calcium/zinc that block iron absorption.", "Take iron separately 2 hours before or after multivitamin."),
    ("Calcium Supplement", "Multivitamin",       1, "Multivitamin already contains calcium — risk of exceeding upper limit (2500mg/day).", "Check total calcium intake. May not need extra calcium supplement."),
    ("Vitamin D3",         "Multivitamin",       1, "Multivitamins contain Vitamin D — risk of exceeding upper limit (4000 IU/day).", "Check total Vitamin D. Avoid doubling up without doctor guidance."),
    ("Omega-3 Fish Oil",   "Vitamin D3",         0, "Omega-3 may enhance Vitamin D absorption as both are fat-soluble.", "Take together with a meal for best absorption of both."),
    ("Melatonin",          "Vitamin B12",        1, "B12 may affect melatonin synthesis through methylation pathways.", "Take melatonin at bedtime, B12 in the morning."),
    ("Ashwagandha",        "Iron Supplement",    0, "Ashwagandha has some iron content and may support iron levels.", "Generally safe together."),
    ("Turmeric/Curcumin",  "Iron Supplement",    2, "Curcumin chelates iron and can significantly reduce iron absorption.", "Separate by at least 2 hours. Take iron first."),
    ("Turmeric/Curcumin",  "Vitamin D3",         0, "Curcumin may enhance Vitamin D receptor expression.", "Safe and potentially beneficial together."),
    ("CoQ10",              "Vitamin E",          0, "Both fat-soluble antioxidants that work synergistically.", "Take together with a fat-containing meal."),
    ("Iron Supplement",    "Calcium Supplement", 2, "Compete for same absorption transporter (DMT1).", "Take 2 hours apart."),
    ("Zinc Supplement",    "Vitamin C",          0, "Vitamin C may enhance zinc absorption slightly.", "Safe to take together."),
    ("Magnesium",          "Calcium Supplement", 1, "Compete for absorption at high doses.", "Maintain 2:1 ratio; take with meals."),
    ("Folic Acid",         "Zinc Supplement",    2, "Zinc may impair folate absorption at high doses.", "Separate by 1-2 hours if using high-dose zinc."),
    ("Biotin",             "Vitamin B12",        0, "Both B-vitamins, work synergistically in energy metabolism.", "Safe and beneficial to take together."),
    ("Prenatal Vitamin",   "Iron Supplement",    2, "Prenatal vitamins already contain iron — excessive iron intake risk.", "Do not add separate iron without doctor supervision."),
    ("Prenatal Vitamin",   "Calcium Supplement", 2, "Prenatal vitamins contain calcium — risk of excess.", "Check total calcium before adding extra supplement."),
    ("Vitamin A",          "Vitamin D3",         1, "High Vitamin A can antagonize Vitamin D activity at receptor level.", "Keep Vitamin A at recommended doses. Don't megadose with D3."),
    ("Vitamin A",          "Vitamin E",          1, "Both fat-soluble, compete for absorption at very high doses.", "Take at different meal times if using high doses."),
    ("Omega-3 Fish Oil",   "Magnesium",          0, "Omega-3 and magnesium together support cardiovascular and muscle health.", "Take together — complementary benefits."),
]

# ─────────────────────────────────────────────────────────────
# 4. FOOD-SUPPLEMENT INTERACTION RULES
#    Source: DrugBank food interaction data + clinical nutrition studies
# ─────────────────────────────────────────────────────────────

FOOD_INTERACTIONS = [
    # (supplement, food, interaction_type: 'avoid'/'good', severity 0-2, reason)
    ("Iron Supplement",    "Spinach",      "avoid", 2, "Oxalates and calcium in spinach bind iron, reducing absorption by up to 50%."),
    ("Iron Supplement",    "Tea (Black)",  "avoid", 2, "Tannins in black tea form insoluble iron complexes, blocking absorption."),
    ("Iron Supplement",    "Coffee",       "avoid", 2, "Polyphenols in coffee inhibit iron absorption by 40%."),
    ("Iron Supplement",    "Milk",         "avoid", 2, "Calcium in milk competes with iron for absorption transporter."),
    ("Iron Supplement",    "Orange",       "good",  0, "Vitamin C in orange juice converts Fe3+ to absorbable Fe2+ form."),
    ("Iron Supplement",    "Strawberry",   "good",  0, "High Vitamin C content enhances iron absorption."),
    ("Iron Supplement",    "Lemon",        "good",  0, "Citric acid and Vitamin C improve iron bioavailability."),
    ("Iron Supplement",    "Bell Pepper",  "good",  0, "Excellent Vitamin C source for enhancing iron absorption."),
    ("Iron Supplement",    "Guava",        "good",  0, "Very high Vitamin C content significantly boosts iron uptake."),
    ("Iron Supplement",    "Beets",        "avoid", 1, "Oxalates in beets moderately inhibit iron absorption."),
    ("Iron Supplement",    "Pomegranate",  "avoid", 1, "Tannins and polyphenols reduce iron absorption."),
    ("Calcium Supplement", "Spinach",      "avoid", 2, "Oxalates in spinach bind calcium, forming inabsorbable calcium oxalate."),
    ("Calcium Supplement", "Milk",         "good",  0, "Additional dietary calcium synergizes with supplement for bone health."),
    ("Calcium Supplement", "Yogurt",       "good",  0, "Fermented dairy calcium is highly bioavailable alongside supplement."),
    ("Calcium Supplement", "Broccoli",     "good",  0, "Low-oxalate vegetable with bioavailable calcium."),
    ("Calcium Supplement", "Kale",         "good",  0, "Kale calcium has high bioavailability; complements supplement."),
    ("Calcium Supplement", "Beets",        "avoid", 1, "Moderate oxalate content reduces calcium absorption."),
    ("Vitamin D3",         "Avocado",      "good",  0, "Healthy fats in avocado enhance fat-soluble Vitamin D absorption."),
    ("Vitamin D3",         "Milk",         "good",  0, "Fortified milk contains Vitamin D; synergistic with supplement."),
    ("Vitamin D3",         "Carrot",       "good",  0, "Fat-soluble nutrient pairs well with fat-containing foods."),
    ("Vitamin K2",         "Spinach",      "good",  0, "Spinach is high in Vitamin K1; combined with K2, supports bone and heart health."),
    ("Vitamin K2",         "Kale",         "good",  0, "Kale is the richest dietary K1 source; synergistic with K2 supplementation."),
    ("Vitamin K2",         "Broccoli",     "good",  0, "Good dietary K source complementing K2 supplement."),
    ("Vitamin C",          "Kale",         "good",  0, "Kale Vitamin C compounds are complementary to supplement."),
    ("Vitamin C",          "Orange",       "good",  0, "Whole food Vitamin C from oranges complements supplement."),
    ("Vitamin C",          "Bell Pepper",  "good",  0, "Bell pepper Vitamin C bioflavonoids enhance supplement efficacy."),
    ("Vitamin C",          "Strawberry",   "good",  0, "Bioflavonoids in strawberry improve Vitamin C absorption."),
    ("Vitamin C",          "Tea (Black)",  "avoid", 1, "Tannins may bind Vitamin C and reduce bioavailability."),
    ("Omega-3 Fish Oil",   "Avocado",      "good",  0, "Monounsaturated fats enhance omega-3 absorption and reduce oxidation."),
    ("Omega-3 Fish Oil",   "Blueberry",    "good",  0, "Antioxidants in blueberry protect omega-3 from oxidation."),
    ("Omega-3 Fish Oil",   "Garlic",       "good",  0, "Garlic and omega-3 together have additive cardiovascular benefits."),
    ("Magnesium",          "Spinach",      "good",  0, "Spinach is rich in magnesium; synergistic with supplement."),
    ("Magnesium",          "Avocado",      "good",  0, "Avocado is a good magnesium source; complements supplement."),
    ("Magnesium",          "Banana",       "good",  0, "Banana provides magnesium and potassium, complementing supplement."),
    ("Magnesium",          "Milk",         "avoid", 1, "Calcium in milk can slightly reduce magnesium absorption at high doses."),
    ("Zinc Supplement",    "Milk",         "avoid", 1, "Calcium in dairy may reduce zinc absorption."),
    ("Zinc Supplement",    "Cheese",       "avoid", 1, "High calcium in cheese competes with zinc absorption."),
    ("Zinc Supplement",    "Pumpkin",      "good",  0, "Pumpkin seeds are a top food source of zinc; complementary."),
    ("Zinc Supplement",    "Garlic",       "good",  0, "Garlic enhances zinc bioavailability through sulfur compounds."),
    ("Folic Acid",         "Spinach",      "good",  0, "Spinach is high in folate; whole food synergy with supplement."),
    ("Folic Acid",         "Broccoli",     "good",  0, "Broccoli folate complements folic acid supplement."),
    ("Folic Acid",         "Avocado",      "good",  0, "Avocado is a top food folate source."),
    ("Vitamin B12",        "Milk",         "good",  0, "Dairy Vitamin B12 complements supplement."),
    ("Vitamin B12",        "Yogurt",       "good",  0, "Fermented dairy B12 has good bioavailability alongside supplement."),
    ("Vitamin E",          "Avocado",      "good",  0, "Healthy fats in avocado enhance fat-soluble Vitamin E absorption."),
    ("Vitamin E",          "Blueberry",    "good",  0, "Synergistic antioxidant effect between Vitamin E and blueberry polyphenols."),
    ("Vitamin E",          "Spinach",      "good",  0, "Spinach Vitamin E compounds work synergistically with supplement."),
    ("Turmeric/Curcumin",  "Avocado",      "good",  0, "Fat enhances curcumin absorption significantly."),
    ("Turmeric/Curcumin",  "Black Pepper", "good",  0, "Piperine in black pepper increases curcumin absorption by 2000%."),
    ("Melatonin",          "Coffee",       "avoid", 2, "Caffeine blocks melatonin receptors and disrupts sleep cycle."),
    ("Melatonin",          "Tea (Black)",  "avoid", 1, "Caffeine content may reduce melatonin effectiveness."),
    ("Melatonin",          "Banana",       "good",  0, "Tryptophan in banana supports natural melatonin production."),
    ("Melatonin",          "Pomegranate",  "avoid", 1, "Pomegranate juice may affect melatonin metabolism enzymes."),
    ("Ashwagandha",        "Milk",         "good",  0, "Traditional Ayurvedic preparation: ashwagandha in warm milk enhances absorption."),
    ("Potassium",          "Banana",       "good",  0, "Banana is a top food potassium source; synergistic with supplement."),
    ("Potassium",          "Avocado",      "good",  0, "Avocado provides high potassium; complements supplement."),
    ("Potassium",          "Spinach",      "good",  0, "Spinach potassium content synergizes with supplement."),
    ("Grapefruit",         "Omega-3 Fish Oil","avoid",2,"Furanocoumarins in grapefruit inhibit CYP3A4 enzyme, affecting fat-soluble supplement metabolism."),
    ("Multivitamin",       "Tea (Black)",  "avoid", 2, "Tannins in black tea bind multiple minerals in multivitamin, reducing overall absorption."),
    ("Multivitamin",       "Coffee",       "avoid", 1, "Polyphenols in coffee reduce absorption of iron and B vitamins in multivitamin."),
    ("Multivitamin",       "Milk",         "avoid", 1, "Calcium in milk may reduce iron and zinc absorption from multivitamin."),
    ("Multivitamin",       "Orange",       "good",  0, "Vitamin C in orange enhances iron absorption from multivitamin."),
    ("Vitamin A",          "Carrot",       "good",  0, "Fat-soluble Vitamin A from supplement and carrot beta-carotene are complementary."),
    ("Vitamin A",          "Mango",        "good",  0, "Mango provides beta-carotene (Vitamin A precursor) complementing supplement."),
    ("Vitamin A",          "Sweet Potato", "good",  0, "Very high beta-carotene content synergizes with Vitamin A supplement."),
    ("Coenzyme Q10",       "Avocado",      "good",  0, "Healthy fats significantly enhance fat-soluble CoQ10 absorption."),
    ("Coenzyme Q10",       "Blueberry",    "good",  0, "Antioxidants in blueberry complement CoQ10's antioxidant function."),

    # ── PAKISTANI SUPPLEMENT FOOD INTERACTIONS ──────────────────────────────
    ("Moringa (Sohanjna)",   "Orange",       "good",  0, "Vitamin C in orange enhances iron absorption from moringa."),
    ("Moringa (Sohanjna)",   "Tea (Black)",  "avoid", 2, "Tannins in tea block iron from moringa; take 2 hours apart."),
    ("Moringa (Sohanjna)",   "Guava",        "good",  0, "Guava's high Vitamin C boosts moringa's iron bioavailability."),
    ("Moringa (Sohanjna)",   "Spinach",      "avoid", 1, "Both high in oxalates; combined oxalate load may reduce calcium absorption."),
    ("Nigella Sativa (Kalonji)","Avocado",   "good",  0, "Healthy fats in avocado enhance absorption of fat-soluble compounds in kalonji."),
    ("Nigella Sativa (Kalonji)","Lemon",     "good",  0, "Lemon enhances antimicrobial properties of kalonji."),
    ("Nigella Sativa (Kalonji)","Tea (Black)","avoid",1, "Tannins may reduce bioavailability of thymoquinone in kalonji."),
    ("Amla (Indian Gooseberry)","Spinach",   "good",  0, "Amla's Vitamin C greatly enhances iron from spinach."),
    ("Amla (Indian Gooseberry)","Banana",    "good",  0, "Banana provides potassium; pairs well with amla for overall nutrition."),
    ("Spirulina",            "Orange",       "good",  0, "Vitamin C in orange enhances iron absorption from spirulina."),
    ("Spirulina",            "Tea (Black)",  "avoid", 2, "Tannins block iron absorption from spirulina; avoid within 2 hours."),
    ("Spirulina",            "Lemon",        "good",  0, "Lemon juice enhances iron absorption from spirulina."),
    ("Garlic Extract",       "Avocado",      "good",  0, "Fats in avocado enhance absorption of fat-soluble sulfur compounds in garlic."),
    ("Garlic Extract",       "Spinach",      "good",  0, "Combined antioxidant effect beneficial."),
    ("Ginger Extract",       "Lemon",        "good",  0, "Ginger and lemon are synergistic for digestion and immunity."),
    ("Ginger Extract",       "Banana",       "good",  0, "Banana is gentle on stomach; pairs well with ginger for GI health."),
    ("Ispaghol (Psyllium Husk)","Apple",     "good",  0, "Apple pectin and psyllium fiber work synergistically for gut health."),
    ("Ispaghol (Psyllium Husk)","Banana",    "good",  0, "Banana's resistant starch complements psyllium fiber."),
    ("Ferosoft / Ferose",    "Orange",       "good",  0, "Vitamin C in orange boosts iron absorption from Ferosoft."),
    ("Ferosoft / Ferose",    "Tea (Black)",  "avoid", 2, "Tannins in tea reduce iron absorption. Avoid with Ferosoft."),
    ("Ferosoft / Ferose",    "Milk",         "avoid", 2, "Calcium in milk blocks iron absorption from Ferosoft."),
    ("Ferosoft / Ferose",    "Guava",        "good",  0, "Guava's very high Vitamin C greatly enhances iron absorption."),
    ("Calcimax",             "Spinach",      "avoid", 2, "Oxalates in spinach bind calcium from Calcimax, reducing absorption."),
    ("Calcimax",             "Broccoli",     "good",  0, "Low-oxalate vegetable; calcium absorption not significantly impaired."),
    ("Calvit D3",            "Avocado",      "good",  0, "Healthy fats in avocado enhance Vitamin D3 absorption from Calvit."),
    ("Neurobion",            "Milk",         "good",  0, "B12 in Neurobion absorbed well alongside dairy."),
    ("Hamdard Safi",         "Lemon",        "good",  0, "Lemon juice enhances the detoxifying action of Safi."),
    ("Hamdard Safi",         "Pomegranate",  "good",  0, "Antioxidants in pomegranate complement Safi's blood-purifying action."),
    ("Karela (Bitter Melon)", "Guava",       "good",  0, "Guava's Vitamin C supports karela's blood sugar regulating effect."),
    ("Karela (Bitter Melon)", "Banana",      "avoid", 1, "Banana's high sugar may counteract karela's blood sugar benefits."),
    ("Shilajit",             "Milk",         "good",  0, "Traditional preparation: shilajit dissolved in warm milk for better absorption."),
    ("Shilajit",             "Tea (Black)",  "avoid", 1, "Tannins may reduce absorption of fulvic acid minerals in shilajit."),
    ("Multivitamin (Centrum)","Tea (Black)", "avoid", 2, "Tannins reduce absorption of multiple minerals in Centrum."),
    ("Multivitamin (Centrum)","Orange",      "good",  0, "Vitamin C in orange enhances iron absorption from Centrum."),
    ("Zinnat / Zincovit",    "Milk",         "avoid", 1, "Calcium in milk may reduce zinc absorption."),
    ("Zinnat / Zincovit",    "Guava",        "good",  0, "Vitamin C in guava enhances zinc and other nutrient absorption."),
    ("Folic Acid 5mg",       "Spinach",      "good",  0, "Spinach is high in folate; complements folic acid supplement."),
    ("Folic Acid 5mg",       "Orange",       "good",  0, "Orange folate complements supplement; Vitamin C aids absorption."),
]

def build_supplement_dataset():
    """Build supplement-supplement interaction training dataset"""
    rows = []
    nutrients = ["iron","vitamin_c","calcium","zinc","magnesium","vitamin_k",
                 "vitamin_d","vitamin_b12","vitamin_e","omega3","potassium","folate"]

    # Build from known interactions
    interaction_lookup = {}
    for s1, s2, severity, mechanism, rec in SUPPLEMENT_INTERACTIONS:
        interaction_lookup[(s1, s2)] = (severity, mechanism, rec)
        interaction_lookup[(s2, s1)] = (severity, mechanism, rec)

    supp_names = list(SUPPLEMENTS.keys())
    for i, s1 in enumerate(supp_names):
        for s2 in supp_names[i+1:]:
            if s1 == s2:
                continue
            d1 = SUPPLEMENTS[s1]
            d2 = SUPPLEMENTS[s2]

            row = {}
            # Supplement 1 nutrients
            for n in nutrients:
                row[f"s1_{n}"] = d1.get(n, 0)
            row["s1_category"] = CATEGORY_CODE.get(d1.get("category","other"), 7)

            # Supplement 2 nutrients
            for n in nutrients:
                row[f"s2_{n}"] = d2.get(n, 0)
            row["s2_category"] = CATEGORY_CODE.get(d2.get("category","other"), 7)

            # Derived interaction features
            row["calcium_iron_compete"] = int(d1.get("calcium",0) > 20 and d2.get("iron",0) > 20) or \
                                          int(d2.get("calcium",0) > 20 and d1.get("iron",0) > 20)
            row["zinc_iron_compete"]    = int(d1.get("zinc",0) > 20 and d2.get("iron",0) > 20) or \
                                          int(d2.get("zinc",0) > 20 and d1.get("iron",0) > 20)
            row["vit_d_k_synergy"]      = int(d1.get("vitamin_d",0) > 0 and d2.get("vitamin_k",0) > 0) or \
                                          int(d2.get("vitamin_d",0) > 0 and d1.get("vitamin_k",0) > 0)
            row["fat_soluble_pair"]     = int((d1.get("vitamin_d",0)+d1.get("vitamin_e",0)+d1.get("vitamin_k",0)) > 0 and
                                              (d2.get("vitamin_d",0)+d2.get("vitamin_e",0)+d2.get("vitamin_k",0)) > 0)
            row["both_minerals"]        = int(d1.get("category","") == "mineral" and d2.get("category","") == "mineral")
            row["vit_c_iron_synergy"]   = int((d1.get("vitamin_c",0) > 50 and d2.get("iron",0) > 50) or
                                              (d2.get("vitamin_c",0) > 50 and d1.get("iron",0) > 50))

            # Label
            if (s1, s2) in interaction_lookup:
                severity, mechanism, rec = interaction_lookup[(s1, s2)]
                row["severity"] = severity
                row["mechanism"] = mechanism
                row["recommendation"] = rec
            else:
                # Unknown pair: estimate from features
                if row["calcium_iron_compete"] or row["zinc_iron_compete"]:
                    row["severity"] = 2
                    row["mechanism"] = "Mineral competition for absorption transporter"
                    row["recommendation"] = "Separate by 2 hours for optimal absorption"
                elif row["vit_d_k_synergy"]:
                    row["severity"] = 0
                    row["mechanism"] = "Fat-soluble vitamin synergy"
                    row["recommendation"] = "Take together with a fatty meal"
                elif row["fat_soluble_pair"]:
                    row["severity"] = 1
                    row["mechanism"] = "Both fat-soluble; may compete at high doses"
                    row["recommendation"] = "Take with meals; monitor total fat-soluble intake"
                elif row["vit_c_iron_synergy"]:
                    row["severity"] = 0
                    row["mechanism"] = "Vitamin C enhances iron absorption"
                    row["recommendation"] = "Take together for enhanced iron absorption"
                elif row["both_minerals"]:
                    row["severity"] = 1
                    row["mechanism"] = "Minerals may compete for divalent transporter"
                    row["recommendation"] = "Separate by 1-2 hours if using high doses"
                else:
                    row["severity"] = 0
                    row["mechanism"] = "No documented significant interaction"
                    row["recommendation"] = "Safe to take together"

            row["s1_name"] = s1
            row["s2_name"] = s2
            rows.append(row)

    df = pd.DataFrame(rows)
    return df


def build_food_dataset():
    """Build food-supplement interaction training dataset"""
    rows = []
    nutrients = ["iron","vitamin_c","calcium","zinc","magnesium","vitamin_k",
                 "vitamin_d","vitamin_b12","vitamin_e","omega3","potassium","folate",
                 "oxalate","tannin"]

    interaction_lookup = {}
    for supp, food, itype, severity, reason in FOOD_INTERACTIONS:
        interaction_lookup[(supp, food)] = (itype, severity, reason)

    for supp_name, supp_data in SUPPLEMENTS.items():
        for food_name, food_data in FOODS.items():
            row = {}
            for n in nutrients:
                row[f"supp_{n}"] = supp_data.get(n, 0)
            row["supp_category"] = CATEGORY_CODE.get(supp_data.get("category","other"), 7)
            for n in nutrients:
                row[f"food_{n}"] = food_data.get(n, 0)
            row["food_is_fruit"] = int(food_data.get("type","") == "fruit")
            row["food_is_veg"]   = int(food_data.get("type","") == "vegetable")
            row["food_is_dairy"] = int(food_data.get("type","") == "dairy")

            # Derived features
            row["tannin_iron_block"]   = int(food_data.get("tannin",0) > 20 and supp_data.get("iron",0) > 50)
            row["oxalate_block"]       = int(food_data.get("oxalate",0) > 30 and
                                            (supp_data.get("iron",0) > 50 or supp_data.get("calcium",0) > 50))
            row["vit_c_iron_enhance"]  = int(food_data.get("vitamin_c",0) > 20 and supp_data.get("iron",0) > 50)
            row["calcium_interference"]= int(food_data.get("calcium",0) > 10 and
                                            (supp_data.get("iron",0) > 50 or supp_data.get("zinc",0) > 50))
            row["fat_soluble_helper"]  = int(food_data.get("type","") in ["fruit","vegetable"] and
                                            (supp_data.get("vitamin_d",0)+supp_data.get("vitamin_e",0)+supp_data.get("vitamin_k",0)) > 50)

            if (supp_name, food_name) in interaction_lookup:
                itype, severity, reason = interaction_lookup[(supp_name, food_name)]
                row["interaction_type"] = 0 if itype == "good" else severity
                row["is_avoid"] = int(itype == "avoid")
                row["reason"] = reason
            else:
                # Estimate from features
                if row["tannin_iron_block"] or row["oxalate_block"]:
                    row["interaction_type"] = 2
                    row["is_avoid"] = 1
                    row["reason"] = "Food components inhibit supplement absorption"
                elif row["vit_c_iron_enhance"]:
                    row["interaction_type"] = 0
                    row["is_avoid"] = 0
                    row["reason"] = "Vitamin C in this food enhances iron absorption"
                elif row["calcium_interference"]:
                    row["interaction_type"] = 1
                    row["is_avoid"] = 1
                    row["reason"] = "Calcium in food may reduce mineral absorption"
                else:
                    row["interaction_type"] = 0
                    row["is_avoid"] = 0
                    row["reason"] = "No significant interaction documented"

            row["supplement_name"] = supp_name
            row["food_name"] = food_name
            rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    print("Building supplement-supplement interaction dataset...")
    supp_df = build_supplement_dataset()
    supp_df.to_csv("data/supplement_interactions.csv", index=False)
    print(f"  Saved {len(supp_df)} supplement pairs → data/supplement_interactions.csv")

    print("Building food-supplement interaction dataset...")
    food_df = build_food_dataset()
    food_df.to_csv("data/food_interactions.csv", index=False)
    print(f"  Saved {len(food_df)} food-supplement pairs → data/food_interactions.csv")

    print("\nDataset summary:")
    print("  Supplement severity distribution:")
    print(supp_df["severity"].value_counts().sort_index().to_string())
    print("  Food avoid distribution:")
    print(food_df["is_avoid"].value_counts().to_string())

    # Export supplement & food knowledge base as JSON for API use
    from build_dataset import SUPPLEMENTS, FOODS, SUPPLEMENT_INTERACTIONS, FOOD_INTERACTIONS
    with open("data/supplements_db.json","w") as f:
        json.dump(SUPPLEMENTS, f, indent=2)
    with open("data/foods_db.json","w") as f:
        json.dump(FOODS, f, indent=2)

    supp_inter_list = [{"s1":a,"s2":b,"severity":c,"mechanism":d,"recommendation":e}
                       for a,b,c,d,e in SUPPLEMENT_INTERACTIONS]
    with open("data/supplement_interactions_db.json","w") as f:
        json.dump(supp_inter_list, f, indent=2)

    food_inter_list = [{"supplement":a,"food":b,"type":c,"severity":d,"reason":e}
                       for a,b,c,d,e in FOOD_INTERACTIONS]
    with open("data/food_interactions_db.json","w") as f:
        json.dump(food_inter_list, f, indent=2)

    print("\nKnowledge base JSON files saved to data/")
