"""
MediSafe AI - Model Training Script
Trains two Random Forest Classifiers:
  1. supplement_interaction_model.pkl  → predicts severity (0-3) for supplement pairs
  2. food_interaction_model.pkl        → predicts avoid/safe (0/1) for food-supplement pairs

Also saves:
  - feature_importance.json           → for SHAP-style explanations in the app
  - model_accuracy_report.json        → shown to FYP panel
"""
#train_model.py
import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import (classification_report, confusion_matrix,
                              accuracy_score, f1_score)
from sklearn.preprocessing import LabelEncoder

# ── import dataset builder ────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(__file__))
from build_dataset import (build_supplement_dataset, build_food_dataset,
                            SUPPLEMENTS, FOODS,
                            SUPPLEMENT_INTERACTIONS, FOOD_INTERACTIONS)

os.makedirs("data", exist_ok=True)
os.makedirs("models", exist_ok=True)

SUPP_FEATURES = [
    "s1_iron","s1_vitamin_c","s1_calcium","s1_zinc","s1_magnesium",
    "s1_vitamin_k","s1_vitamin_d","s1_vitamin_b12","s1_vitamin_e",
    "s1_omega3","s1_potassium","s1_folate","s1_category",
    "s2_iron","s2_vitamin_c","s2_calcium","s2_zinc","s2_magnesium",
    "s2_vitamin_k","s2_vitamin_d","s2_vitamin_b12","s2_vitamin_e",
    "s2_omega3","s2_potassium","s2_folate","s2_category",
    "calcium_iron_compete","zinc_iron_compete","vit_d_k_synergy",
    "fat_soluble_pair","both_minerals","vit_c_iron_synergy"
]

FOOD_FEATURES = [
    "supp_iron","supp_vitamin_c","supp_calcium","supp_zinc","supp_magnesium",
    "supp_vitamin_k","supp_vitamin_d","supp_vitamin_b12","supp_vitamin_e",
    "supp_omega3","supp_potassium","supp_folate","supp_category",
    "food_iron","food_vitamin_c","food_calcium","food_zinc","food_magnesium",
    "food_vitamin_k","food_vitamin_d","food_vitamin_b12","food_vitamin_e",
    "food_omega3","food_potassium","food_folate","food_oxalate","food_tannin",
    "food_is_fruit","food_is_veg","food_is_dairy",
    "tannin_iron_block","oxalate_block","vit_c_iron_enhance",
    "calcium_interference","fat_soluble_helper"
]

SEVERITY_LABELS = {0: "None / Beneficial", 1: "Mild", 2: "Moderate", 3: "Severe"}

# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("  MediSafe AI — Model Training")
print("=" * 60)

# ── 1. SUPPLEMENT-SUPPLEMENT MODEL ───────────────────────────────────────────
print("\n[1/2] Training Supplement Interaction Classifier...")
supp_df = build_supplement_dataset()
supp_df.to_csv("data/supplement_interactions.csv", index=False)
print(f"  Dataset: {len(supp_df)} supplement pairs")

X_s = supp_df[SUPP_FEATURES].values
y_s = supp_df["severity"].values

print(f"  Class distribution: { {SEVERITY_LABELS[k]: int(v) for k,v in zip(*np.unique(y_s, return_counts=True))} }")

X_s_train, X_s_test, y_s_train, y_s_test = train_test_split(
    X_s, y_s, test_size=0.20, random_state=42, stratify=y_s
)

# GridSearchCV for best hyperparameters (as described in proposal)
param_grid = {
    "n_estimators": [100, 200],
    "max_depth": [None, 10, 20],
    "min_samples_split": [2, 5],
    "class_weight": ["balanced"]
}
print("  Running GridSearchCV (this takes ~30s)...")
grid_search_s = GridSearchCV(
    RandomForestClassifier(random_state=42),
    param_grid, cv=5, scoring="f1_weighted", n_jobs=-1, verbose=0
)
grid_search_s.fit(X_s_train, y_s_train)
supp_model = grid_search_s.best_estimator_
print(f"  Best params: {grid_search_s.best_params_}")

# 5-fold cross-validation (as stated in proposal)
cv_scores_s = cross_val_score(supp_model, X_s, y_s, cv=5, scoring="accuracy")
print(f"  5-fold CV accuracy: {cv_scores_s.mean():.3f} ± {cv_scores_s.std():.3f}")

y_s_pred = supp_model.predict(X_s_test)
supp_accuracy = accuracy_score(y_s_test, y_s_pred)
supp_f1 = f1_score(y_s_test, y_s_pred, average="weighted")
print(f"  Test Accuracy : {supp_accuracy:.3f} ({supp_accuracy*100:.1f}%)")
print(f"  Test F1 Score : {supp_f1:.3f}")
print("\n  Classification Report:")
print(classification_report(y_s_test, y_s_pred,
      target_names=[SEVERITY_LABELS[i] for i in sorted(np.unique(y_s))],
      zero_division=0))

# Feature importance (SHAP-equivalent for Random Forest)
supp_importances = dict(zip(SUPP_FEATURES,
                            supp_model.feature_importances_.tolist()))
top_supp_features = sorted(supp_importances.items(), key=lambda x: x[1], reverse=True)[:10]
print("  Top 10 features by importance:")
for feat, imp in top_supp_features:
    bar = "█" * int(imp * 200)
    print(f"    {feat:30s} {imp:.4f}  {bar}")

# ── 2. FOOD-SUPPLEMENT MODEL ──────────────────────────────────────────────────
print("\n[2/2] Training Food-Supplement Interaction Classifier...")
food_df = build_food_dataset()
food_df.to_csv("data/food_interactions.csv", index=False)
print(f"  Dataset: {len(food_df)} food-supplement pairs")

X_f = food_df[FOOD_FEATURES].values
y_f = food_df["is_avoid"].values

print(f"  Class distribution: avoid={int((y_f==1).sum())}  safe={int((y_f==0).sum())}")

X_f_train, X_f_test, y_f_train, y_f_test = train_test_split(
    X_f, y_f, test_size=0.20, random_state=42, stratify=y_f
)

grid_search_f = GridSearchCV(
    RandomForestClassifier(random_state=42),
    param_grid, cv=5, scoring="f1_weighted", n_jobs=-1, verbose=0
)
grid_search_f.fit(X_f_train, y_f_train)
food_model = grid_search_f.best_estimator_
print(f"  Best params: {grid_search_f.best_params_}")

cv_scores_f = cross_val_score(food_model, X_f, y_f, cv=5, scoring="accuracy")
print(f"  5-fold CV accuracy: {cv_scores_f.mean():.3f} ± {cv_scores_f.std():.3f}")

y_f_pred = food_model.predict(X_f_test)
food_accuracy = accuracy_score(y_f_test, y_f_pred)
food_f1 = f1_score(y_f_test, y_f_pred, average="weighted")
print(f"  Test Accuracy : {food_accuracy:.3f} ({food_accuracy*100:.1f}%)")
print(f"  Test F1 Score : {food_f1:.3f}")
print("\n  Classification Report:")
print(classification_report(y_f_test, y_f_pred,
      target_names=["Safe / Beneficial", "Avoid"],
      zero_division=0))

food_importances = dict(zip(FOOD_FEATURES,
                            food_model.feature_importances_.tolist()))
top_food_features = sorted(food_importances.items(), key=lambda x: x[1], reverse=True)[:10]
print("  Top 10 features by importance:")
for feat, imp in top_food_features:
    bar = "█" * int(imp * 200)
    print(f"    {feat:35s} {imp:.4f}  {bar}")

# ── 3. SAVE MODELS ────────────────────────────────────────────────────────────
print("\n[Saving models...]")
with open("models/supplement_interaction_model.pkl","wb") as f:
    pickle.dump(supp_model, f)
with open("models/food_interaction_model.pkl","wb") as f:
    pickle.dump(food_model, f)

# Save feature lists for prediction API
with open("models/supp_features.json","w") as f:
    json.dump(SUPP_FEATURES, f)
with open("models/food_features.json","w") as f:
    json.dump(FOOD_FEATURES, f)

# ── 4. SAVE ACCURACY REPORT (shown to panel) ─────────────────────────────────
report = {
    "supplement_model": {
        "algorithm": "Random Forest Classifier",
        "dataset_size": len(supp_df),
        "test_accuracy": round(supp_accuracy, 4),
        "test_f1_weighted": round(supp_f1, 4),
        "cv_accuracy_mean": round(float(cv_scores_s.mean()), 4),
        "cv_accuracy_std": round(float(cv_scores_s.std()), 4),
        "best_hyperparams": grid_search_s.best_params_,
        "top_features": [{"feature": k, "importance": round(v, 4)}
                         for k, v in top_supp_features],
        "confusion_matrix": confusion_matrix(y_s_test, y_s_pred).tolist()
    },
    "food_model": {
        "algorithm": "Random Forest Classifier",
        "dataset_size": len(food_df),
        "test_accuracy": round(food_accuracy, 4),
        "test_f1_weighted": round(food_f1, 4),
        "cv_accuracy_mean": round(float(cv_scores_f.mean()), 4),
        "cv_accuracy_std": round(float(cv_scores_f.std()), 4),
        "best_hyperparams": grid_search_f.best_params_,
        "top_features": [{"feature": k, "importance": round(v, 4)}
                         for k, v in top_food_features],
        "confusion_matrix": confusion_matrix(y_f_test, y_f_pred).tolist()
    },
    "data_sources": [
        "Australian Therapeutic Goods Administration (TGA) supplement database",
        "DrugBank open drug interaction database",
        "USDA FoodData Central nutritional profiles",
        "FooDB food composition database",
        "Clinical literature (IEEE, MDPI, NIH)"
    ]
}
with open("models/model_accuracy_report.json","w") as f:
    json.dump(report, f, indent=2)

# ── 5. SAVE KNOWLEDGE BASE JSONs ──────────────────────────────────────────────
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

# ── DONE ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  TRAINING COMPLETE")
print("=" * 60)
print(f"  Supplement model accuracy : {supp_accuracy*100:.1f}%")
print(f"  Food model accuracy       : {food_accuracy*100:.1f}%")
print(f"\n  Files saved:")
print(f"    models/supplement_interaction_model.pkl")
print(f"    models/food_interaction_model.pkl")
print(f"    models/model_accuracy_report.json")
print(f"    models/supp_features.json")
print(f"    models/food_features.json")
print(f"    data/supplement_interactions.csv")
print(f"    data/food_interactions.csv")
print(f"    data/supplements_db.json")
print(f"    data/foods_db.json")
print(f"    data/supplement_interactions_db.json")
print(f"    data/food_interactions_db.json")
