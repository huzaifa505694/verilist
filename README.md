# VeriList — Week 3: Core Backend APIs & CRUD Operations

Tynovate Internship Program 2026 — AI + Web Development Track
Author: Huzaifa | CFD Campus, National University (NU)

## Week 3 Goal

Every core entity in VeriList has a complete, tested set of REST endpoints for Create, Read, Update, and Delete (CRUD) — the functional foundation that the dashboards (Week 4), AI Price Estimator (Week 5), and Fraud Detector (Week 6) are all built on top of.

Status: **Completed**, on schedule.

## What Was Built

### Listings CRUD
- `POST /listings` — create a listing, with category-specific field validation
- `GET /listings` — paginated listing feed with filters (category, price range, condition)
- `GET /listings/:id` — single listing detail
- `PUT /listings/:id` — update a listing, restricted to the owning seller
- `DELETE /listings/:id` — soft delete (status set to `removed`, no hard delete)

### Supporting Entities
- Reviews — create and read endpoints
- Notifications — read and mark-as-read endpoints
- Admin endpoints — list all users, list all listings including flagged ones

### Validation, Error Handling & Rate Limiting
- Input validation on all write endpoints (e.g. negative prices and invalid mileage are rejected at the API level, not just the frontend)
- Centralized error-handling middleware with a consistent error response shape
- Basic rate limiting on authentication and listing-creation endpoints

### Testing
- Postman collection covering every endpoint, with at least one success and one failure case each
- Bugs found during testing were fixed
- Postman collection exported to `docs/` for the final submission package

## Endpoint Summary

| Method | Route | Purpose | Access |
|---|---|---|---|
| POST | /listings | Create a new listing | Seller |
| GET | /listings | Paginated listing feed with filters | Public |
| GET | /listings/:id | Single listing detail | Public |
| PUT | /listings/:id | Update an owned listing | Seller (owner) |
| DELETE | /listings/:id | Soft-delete a listing | Seller (owner) |
| GET/POST | /reviews | Create / read reviews | Buyer / Public |
| GET/PATCH | /notifications | Read / mark-as-read | User |
| GET | /admin/users, /admin/listings | Admin oversight views | Admin |

## Key Decisions

- Soft-delete over hard-delete for listings, to keep historical data intact for future analytics.
- Validation was kept strict at this stage, since clean input now prevents downstream issues for the Week 5 pricing model and Week 6 fraud detector, both of which assume clean data.
- Every endpoint was verified individually in Postman before being marked complete.

## Next Up — Week 4

Wiring the Listings, Listing Detail, Seller Dashboard, and Admin Dashboard pages to this live API, followed by a full responsive pass across mobile, tablet, and desktop.
