# VeriList — Week 2: Authentication & Database Design

**AI-Verified Pricing & Trust for Secondhand Marketplaces**
*Tynovate Internship Program 2026 — AI + Web Development Track*

**Status:** In Progress&nbsp;&nbsp;|&nbsp;&nbsp;**Stack:** Next.js · Prisma · PostgreSQL · NextAuth.js&nbsp;&nbsp;|&nbsp;&nbsp;**Week:** 2 of 8

---

## 🎯 Week 2 Goal

> A user can register, log in (via credentials **or** Google), log out, and stay logged in across page refreshes. The full database schema is migrated and seeded with realistic fake data.

---

## 📦 What This Week Covers

| Area | Deliverable |
|---|---|
| Database Schema | Full Prisma schema migrated to PostgreSQL, indexed for query performance |
| Seed Data | ~30–50 fake users and ~100 fake vehicle listings (Faker.js) for downstream AI training |
| Credentials Auth | Registration, login, logout — bcrypt hashing, JWT via httpOnly cookies |
| **Google OAuth** | Sign-in with Google via **NextAuth.js + Prisma Adapter** |
| Role-Based Access | `buyer` / `seller` / `admin` roles with middleware enforcement |
| Frontend Integration | Login/Register forms wired to backend, full register → login → protected route → logout loop verified |

---

## 🗄️ 1. Database Schema & Seeding

- [x] Migrate full Prisma schema to PostgreSQL
- [x] `Role` enum: `BUYER` / `SELLER` / `ADMIN`
- [x] Core models: `User`, `Listing` (+ relations for future `PricePredictions`, `FraudScores`)
- [x] Seed script (Faker.js): ~30–50 users, ~100 vehicle listings with varied mileage / year / price
- [x] Indexes on `seller_id`, `category`, `status`, `created_at`

```bash
npx prisma migrate dev --name week2_auth_schema
npx prisma db seed
```

> **Why seed now?** The AI Price Estimator (Week 5) needs realistic training data. Generating it in Week 2 avoids losing time later.

---

## 🔐 2. Authentication

VeriList supports **two sign-in paths** that converge on the same `User` table and JWT session model:

1. **Credentials path** — email + password → bcrypt hash/verify → `User` (Prisma)
2. **Google OAuth path** — Google Cloud OAuth client → NextAuth.js → `User` (Prisma)

Both paths write to the same `User` record, then issue a JWT session stored in an httpOnly cookie, which is what role-based middleware checks on every protected route. The sign-in method used has no effect on downstream authorization logic.

### 2.1 Credentials Flow

- [x] `POST /api/auth/register` — bcrypt password hashing
- [x] `POST /api/auth/login` — issues JWT
- [x] Middleware verifies JWT on protected routes
- [x] Logout — clears httpOnly cookie (server-side blacklist optional)
- [x] `role` field enforced via role-based middleware

### 2.2 Google OAuth (NextAuth.js)

- [x] Google Cloud Console → OAuth Client (Web Application) created
- [x] Authorized redirect URI configured:
  `http://localhost:3000/api/auth/callback/google`
- [x] `GoogleProvider` added to NextAuth config
- [x] `PrismaAdapter` linked so Google sign-ins create/reuse the same `User` model as credentials auth
- [x] `Account` and `Session` models added to Prisma schema (NextAuth requirement)
- [x] New Google sign-ups default to `role: BUYER`, upgradeable to `SELLER` post-registration

```env
# .env — never commit real values
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
NEXTAUTH_SECRET=your_generated_secret
NEXTAUTH_URL=http://localhost:3000
```

```ts
// pages/api/auth/[...nextauth].ts (or app/api/auth/[...nextauth]/route.ts)
providers: [
  GoogleProvider({
    clientId: process.env.GOOGLE_CLIENT_ID!,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
  }),
  CredentialsProvider({ /* bcrypt-verified login */ }),
],
adapter: PrismaAdapter(prisma),
session: { strategy: "jwt" },
```

> **Why both methods matter:** Google OAuth removes signup friction for buyers browsing casually; credentials auth stays essential for sellers who need a persistent, portfolio-style identity with password recovery. Both converge on the same `User` and JWT session model, so downstream role checks don't need to know which path was used.

---

## ✅ End-to-End Verification Checklist

- [ ] Register with email/password → succeeds, password stored hashed
- [ ] Login with credentials → JWT issued, session persists on refresh
- [ ] Sign in with Google → new `User` + `Account` row created, session persists
- [ ] Returning Google user → no duplicate `User` row created
- [ ] Access protected route while logged out → rejected (401/redirect)
- [ ] Access protected route while logged in → allowed
- [ ] Logout → session cleared, protected route now rejects access
- [ ] Role middleware blocks `buyer` from admin-only routes

---

## ⚠️ Known Tradeoffs / Risks

| Risk | Mitigation / Note |
|---|---|
| JWT storage in `localStorage` is XSS-vulnerable | Using **httpOnly cookies** instead — documented as deliberate choice |
| Google OAuth users have no password | Handled by NextAuth's `Account` model; password field nullable for OAuth-only users |
| Redirect URI mismatch is the #1 Google OAuth failure | Verify **exact** match (including trailing slash / http vs https) in Google Cloud Console |
| Seed data must stay realistic | Directly feeds Week 5 AI Price Estimator — garbage data here breaks the model later |

---

## 📁 Relevant Structure

```
server/ (or app/api if using Next.js API routes)
├── prisma/
│   ├── schema.prisma        # User, Account, Session, Listing, Role enum
│   └── seed.ts               # Faker.js seed script
├── api/auth/
│   ├── register.ts
│   ├── login.ts
│   └── [...nextauth].ts      # Google + Credentials providers
├── middleware/
│   ├── verifyJWT.ts
│   └── requireRole.ts
└── .env                       # GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, NEXTAUTH_SECRET
```

---

## ➡️ Next: Week 3

Core Backend APIs & CRUD — full Create/Read/Update/Delete for Listings, with input validation strict enough that the Week 6 Fraud Detector can trust clean data downstream.

---
*Internal working document — VeriList, Tynovate Internship Program 2026*
