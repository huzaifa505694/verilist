# VeriList — Week 4: Dashboard & Responsive Frontend

> AI-Verified Pricing & Trust for Secondhand Marketplaces
> Tynovate Internship Program 2026 — AI + Web Development Track

This README covers **Week 4 only**. For the full project overview, problem statement, and 8-week roadmap, see the main project documentation in `docs/`.

---

## 🎯 Week 4 Goal

Deliver a working, data-driven frontend: a real user can browse listings, view full listing details, and see seller/admin dashboards populated with **live data from the backend** — fully responsive across desktop, tablet, and mobile.

---

## ✅ Scope Completed This Week

### Core Pages
- **Listings Page** — grid/list view, category and price-range filters, pagination, wired to the live `GET /listings` API.
- **Listing Detail Page** — full listing info, seller details, and a placeholder section for the AI price estimate and risk score (to be wired live in Weeks 5–6).
- **Loading & error states** implemented on every API call — no silent failures, no blank screens.

### Seller Dashboard
- **My Listings** view — status, placeholder view count, edit/delete actions.
- **Stats cards** — total listings, active listings, sold listings.

### Admin Dashboard
- **Platform overview** — user count, listing count, category breakdown chart (Recharts).
- **Flagged listings table** — placeholder UI, to be connected to real fraud-scoring data in Week 6.

### Responsive & Accessibility Pass
- Verified layout at **375px (mobile)**, **768px (tablet)**, and **1440px (desktop)**.
- Fixed common breakpoints issues: non-scrolling tables on mobile, fixed-width elements, non-collapsing navigation.
- Basic accessibility check completed — keyboard navigation, image alt text, color contrast.

---

## 🧱 Tech Stack (Frontend, Week 4 scope)

| Layer | Technology |
|---|---|
| Framework | React (Vite) |
| Charts | Recharts |
| API Layer | REST calls to Express backend (`/listings`, `/users`, `/admin`) |
| Styling | Responsive CSS, mobile-first breakpoints |
| Data Source | Live PostgreSQL-backed API — **no hardcoded/mock JSON** |

---

## 🔌 API Integration

All dashboard and listing views consume the real backend endpoints built in Week 3 (Listings, Users, Admin CRUD). Fake/hardcoded data was deliberately avoided this week — the seeded database from Week 2 is the single source of truth, so no rework is needed when AI features are wired in during Weeks 5–6.

---

## ⚠️ Known Limitations / Deferred to Later Weeks

- AI price estimate and risk score on the Listing Detail page are **placeholders** — real predictions arrive in Week 5 (Price Estimator) and Week 6 (Fraud & Anomaly Detector).
- Admin flagged-listings table is **not yet populated** with real fraud data — pending Week 6.
- Seller "views count" is a placeholder pending analytics instrumentation (Week 7).

---

## 📋 Testing Checklist

- [x] Listings page renders and filters correctly at all three breakpoints
- [x] Listing detail page loads live data, handles missing/loading states
- [x] Seller dashboard reflects real seeded data per logged-in user
- [x] Admin dashboard reflects real aggregate platform data
- [x] Navigation collapses correctly on mobile
- [x] Keyboard navigation and alt text verified

---

## Next Up — Week 5

AI Price Estimator: train a regression model on vehicle listing data and integrate real predicted price ranges into the listing creation flow.
