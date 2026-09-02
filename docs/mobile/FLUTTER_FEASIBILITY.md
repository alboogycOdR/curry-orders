# Flutter Mobile App — Feasibility Assessment

**Status:** Pre-planning (no work started)  
**Date assessed:** 2026-09-02  
**Decision:** Hold — build REST API layer and Caddy/TLS first (see Prerequisites)

---

## Summary

A Flutter customer app is technically feasible and strategically worthwhile as the
business scales. The Django backend stays unchanged; Flutter is a new mobile frontend
that consumes a REST API. The staff dashboard (`/manage/`) stays on the web browser —
it is a dense information screen that suits a tablet/desktop better than a phone.

---

## What Flutter adds (vs the current web app)

| Capability | Web today | Flutter |
|---|---|---|
| Push notifications (order ready, status change) | ✗ | ✓ FCM |
| Native camera proof upload | Clunky | ✓ |
| Reliable offline cart | Fragile (localStorage) | ✓ shared_preferences |
| Home screen icon / repeat-customer habit | ✗ | ✓ |
| App Store / Play Store discoverability | ✗ | ✓ |
| Native gestures + haptics | ✗ | ✓ |
| Google Sign-In (native SDK) | Web OAuth redirect | ✓ Native SDK |

Push notifications — "Your order is ready for collection" — are the single most
impactful feature for a collection-only business. They change the customer experience
more than anything else in this list.

---

## Architecture

```
┌─────────────────────┐     JSON REST API     ┌─────────────────────┐
│   Flutter app       │ ◄───────────────────► │   Django backend    │
│   (iOS + Android)   │                       │   (unchanged)       │
└─────────────────────┘                       └─────────────────────┘
                                                        │
                                              ┌─────────────────────┐
                                              │  Web browser        │
                                              │  /manage/ (staff)   │
                                              └─────────────────────┘
```

- **Backend**: Django 5.0 — stays as-is. Models are clean; no structural changes needed.
- **API layer**: Django REST Framework (DRF) serialisers + viewsets on top of existing models.
- **Auth in Flutter**: `google_sign_in` package (native) → Django validates Google ID token
  server-side and issues a session/JWT. Replaces the `httpx` OAuth redirect flow used on web.
- **Push**: Firebase Cloud Messaging (FCM) — `firebase_messaging` Flutter package.
  Django sends notifications via the Firebase Admin SDK when order status transitions.

---

## The API Gap — primary work item

The current backend is server-rendered (Django templates → HTML). Flutter needs JSON.
Today only 4–5 JSON endpoints exist (checkout, proof upload, availability, order status,
staff transitions). The following REST endpoints would need to be built:

### Customer endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/menu/` | GET | Dishes + options for a given date |
| `/api/v1/availability/` | GET | Open days + slots (already exists, may need cleanup) |
| `/api/v1/orders/` | POST | Place order (checkout — already exists) |
| `/api/v1/orders/{token}/` | GET | Order status |
| `/api/v1/orders/{token}/proof/` | POST | Upload EFT proof (already exists) |
| `/api/v1/account/` | GET | Customer profile |
| `/api/v1/account/orders/` | GET | Order history |
| `/api/v1/auth/google/` | POST | Exchange Google ID token for session |
| `/api/v1/auth/magic-link/` | POST | Request magic-link email |
| `/api/v1/lookup/` | POST | Find order by number + mobile |

Most of the business logic already exists in `core/`; DRF adds serialisation on top.

---

## Scope estimate

| Phase | Work | Duration |
|---|---|---|
| 1 | DRF REST API (all customer endpoints, auth) | 2–3 weeks |
| 2 | Flutter app: menu → basket → checkout → order status → account | 4–6 weeks |
| 3 | Push notifications (FCM), native Google Sign-In | 1–2 weeks |
| 4 | App Store + Play Store submission + review | 1–2 weeks |
| **Total** | | **~3 months to shippable v1** |

Staff Flutter app (kitchen desk, collection board) is a future v2 consideration.

---

## Prerequisites (must be done first)

### 1. Caddy/TLS + real domain (BLOCKER for App Store)
Apple App Store review requires HTTPS. The raw-IP:port deploy
(`http://204.168.249.99:8102/`) will be rejected. This is already in the M10 backlog
(`docs/DOMAIN_AND_SSL.md`). Move this up before any App Store submission.

### 2. Privacy policy + Terms & conditions
Apple is strict about food-ordering apps. Required before App Store submission:
- Privacy policy (data collected, POPIA compliance for SA customers)
- Terms & conditions
- Allergen/dietary disclaimer

### 3. REST API layer
Build and stabilise the DRF API before starting the Flutter app. Building Flutter
against an unstable API produces churn and rework.

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| App Store rejection (missing policy/HTTPS) | High if unprepared | Address prerequisites first |
| Maintenance burden (two frontends) | Medium | Web stays for staff; Flutter is customer-only |
| Push notification delivery reliability | Low–Medium | FCM is mature; test on both platforms |
| Customer adoption (vs just using the web link) | Unknown | Promote app at collection point; push notifications drive retention |

---

## Decision log

- **2026-09-02**: Feasibility assessed. Decision: hold until Caddy/TLS and DRF API
  layer are complete. Flutter is the right direction as the business scales; the
  prerequisites are the bottleneck, not the Flutter work itself.
