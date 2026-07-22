# VeriList — Week 5: AI Price Estimator

**Tynovate Internship Program 2026 — AI + Web Development Track**
**Owner:** Huzaifa | **Phase:** Week 5 of 8 — AI Integration

---

## 1. Week 5 Objective

By the end of this week, a seller creating or viewing a listing sees a **real, model-generated predicted price range with feature importance** — not the static placeholder shipped in Week 4. This is the first of VeriList's two core AI systems (Price Estimator + Fraud & Anomaly Detector) and the one the Week 6 fraud logic will depend on directly, since the predicted price and its confidence range become the statistical baseline against which suspiciously priced listings are later flagged.

This week is scoped to the Price Estimator only. Fraud/anomaly logic, Stripe, recommendations, and notifications are explicitly out of scope until their respective weeks.

## 2. Why This Feature Exists

Secondhand vehicles have no manufacturer-fixed price — fair value depends on interacting factors (mileage, age, condition, local demand) with no lookup table, which is exactly the class of problem a regression model is suited to. The estimator is embedded directly in the listing creation and detail flow, not bolted on as a separate analytics page, so it delivers pricing guidance at the moment sellers and buyers actually need it.

## 3. Scope This Week (Day-by-Day)

### Day 1 — Data Preparation
- Pull a public used-vehicle dataset (Kaggle) with `make`, `model`, `year`, `mileage`, `price`.
- Merge in the ~100 seeded listings from Week 2 to align the training distribution with VeriList's own schema.
- Handle missing values; encode categorical features:
  - One-hot encoding for low-cardinality fields (`condition`).
  - Label/target encoding for high-cardinality fields (`model`) to avoid feature-space blowup.
- Output: a single clean, model-ready training table, versioned under `ml-service/data/`.

### Day 2–3 — Model Training & Evaluation
- Train a **Random Forest Regressor** (scikit-learn) with `price` as target.
  - Chosen because it captures non-linear mileage/age/price interactions without manual feature-crossing, is robust to noisy/outlier listings, and produces feature importances natively.
- Evaluate on a **held-out test split** using:
  - **R²** — variance explained.
  - **MAE** — mean absolute error, in currency units.
- Record both figures — they're a required demo talking point, not optional.
- Generate a **confidence range** per prediction (spread of individual tree predictions, or a ± band from residual std. deviation) — this range is what's shown to users, never the raw point estimate.
- Extract and persist feature importances alongside the model artifact.

### Day 4 — Serve the Model
- Wrap the trained model in a FastAPI/Flask endpoint inside `ml-service/`.
- Express backend calls the endpoint at listing-creation and listing-view time.
- Persist the result to the `PricePredictions` table — **compute once, read from storage thereafter**, not on every page load.

### Day 5 — Frontend Integration
- Listing creation form: live predicted price range as the seller types specs.
- Listing detail page: predicted range + feature-importance breakdown next to the seller's asking price.
- Test edge cases: missing fields, out-of-range values, categories with no training data.

## 4. Architecture

```
React (listing form / detail page)
        │  live price range request
        ▼
Express backend  ──────────────►  ml-service (FastAPI/Flask)
        │                                │
        │  cache result                  │  Random Forest model
        ▼                                ▼
  PricePredictions table          feature_importances.pkl
```

Predictions are cached in Postgres so the ML microservice isn't hit on every page render — only on create/update.

## 5. API Contract

**`POST /predict-price`** (ml-service)

Request:
```json
{
  "category": "vehicle",
  "make": "Toyota",
  "model": "Corolla",
  "year": 2019,
  "mileage": 62000,
  "condition": "good"
}
```

Response:
```json
{
  "predicted_price": 2150000,
  "range": { "low": 1980000, "high": 2320000 },
  "feature_importance": {
    "mileage": 0.34,
    "year": 0.28,
    "make": 0.19,
    "model": 0.12,
    "condition": 0.07
  }
}
```

Response fields map directly to the `PricePredictions` table (`listing_id`, `predicted_price`, `range_low`, `range_high`, `feature_importance_json`, `created_at`).

## 6. Folder Structure Additions

```
ml-service/
├── data/
│   ├── raw/                 # Kaggle dataset, untouched
│   └── processed/           # cleaned + encoded training table
├── models/
│   ├── price_estimator.pkl
│   └── feature_importances.pkl
├── app.py                   # FastAPI/Flask app, POST /predict-price
├── train.py                 # training + evaluation script
└── requirements.txt
```

## 7. Testing & Edge Cases

Before this feature is considered integrated, it must handle, without a silent failure or a nonsensical price:

- [ ] Missing or partially filled listing fields
- [ ] Out-of-range numeric values (e.g., unrealistic mileage)
- [ ] Categories/make-model combinations with little or no training data — should widen the confidence range or flag low confidence, not guess blindly

## 8. Risks / Watch-outs

- **Model accuracy questions.** "How accurate is your model?" is the single most common review question — R² and MAE must be memorized before any demo or checkpoint, not looked up on the spot.
- **Scope creep into Week 6.** Fraud/anomaly logic depends on this week's output but does not belong in this week's build. If behind schedule, the Price Estimator is never the thing to cut — it's priority #2 on the project's overall fallback list, right after auth/DB/CRUD.

## 9. Week 5 Deliverables Checklist

- [ ] Dataset acquired, merged with seeded listings, cleaned and encoded
- [ ] Random Forest Regressor trained, R² and MAE recorded
- [ ] Confidence range generated per prediction
- [ ] Feature importances extracted and persisted
- [ ] `POST /predict-price` live in `ml-service`
- [ ] Express backend integration writing to `PricePredictions`
- [ ] Predicted range + feature importance live on listing creation form
- [ ] Predicted range + feature importance live on listing detail page
- [ ] Edge cases (missing fields, out-of-range values, sparse categories) verified

**Definition of done:** both the listing creation form and the listing detail page show a live, model-generated price range with feature importance for standard listings, degrade gracefully on the edge cases above, and the R²/MAE figures are recorded and demo-ready.

## 10. Next Up: Week 6 Preview

Week 6 builds directly on this week's output: the predicted price and confidence range become the statistical baseline the **AI Fraud & Anomaly Detector** uses to flag listings.

- **Rule-based core:** price-deviation flag (listing price far below predicted range), description/price mismatch (condition keywords vs. price percentile), new-account + high-value-listing flag.
- **Stretch (if on schedule):** image reuse detection via perceptual hashing.
- **Admin workflow:** every flag writes a risk score + reasons array to `FraudScores`; an admin review queue lists flagged listings for approve/reject/remove — flagged listings are never auto-removed.
- **Framing note carried into Week 6:** referred to as *risk scoring*, not "fraud detection," since it surfaces statistical anomalies for human review rather than confirmed fraud.

Full Week 6 scope, technical approach, and deliverables will be covered in that week's own README and report — this is a preview, not the spec.
