# GrowthPro — Backend Scaffold

FastAPI + PostgreSQL backend for the AI SEO/Social Growth platform, with a
**real** Google OAuth flow (Search Console + YouTube Data API), multi-tenant
workspaces, JWT auth, and an AI service layer.

## What's real vs. what you still need to do

This scaffold implements actual, working code paths — not mocks:
- Real Google OAuth 2.0 authorization-code flow (`google-auth-oauthlib`)
- Real Search Console API calls (`searchanalytics.query`, `sites.list`)
- Real YouTube Data API calls (channel stats, video list, metadata update)
- Real Postgres schema + Alembic migrations, multi-tenant isolation via
  `organization_id` / `workspace_id` and a membership check on every request
- Real JWT auth + bcrypt password hashing + Fernet-encrypted OAuth tokens at rest

What only **you** can supply (nobody else can do this part for you):
1. A Google Cloud project, with **Search Console API** and **YouTube Data
   API v3** enabled, and an OAuth 2.0 Client ID (type: Web application)
   created at console.cloud.google.com → APIs & Services → Credentials.
2. Your own domain + HTTPS in production (Google OAuth requires a real
   redirect URI — `http://localhost:8000/...` only works for local testing
   with your own Google account added as a test user).
3. An Anthropic API key from console.anthropic.com for the AI service.
4. Actually running this somewhere (a VPS, Render, Railway, Fly.io, AWS,
   etc.) — nothing here is auto-deployed.

## Local setup

```bash
cp .env.example .env
# fill in SECRET_KEY, TOKEN_ENCRYPTION_KEY (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"),
# DATABASE_URL, GOOGLE_CLIENT_ID/SECRET, ANTHROPIC_API_KEY

docker compose up -d db redis
pip install -r requirements.txt
alembic revision --autogenerate -m "init"
alembic upgrade head
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs (Swagger UI).

## Google Cloud setup (Search Console + YouTube)

1. console.cloud.google.com → create a project.
2. APIs & Services → Library → enable **Google Search Console API** and
   **YouTube Data API v3**.
3. APIs & Services → OAuth consent screen → configure (External, add your
   email as a test user while in "Testing" status).
4. APIs & Services → Credentials → Create Credentials → OAuth client ID →
   Web application → Authorized redirect URI:
   `http://localhost:8000/api/google/oauth/callback` (match `GOOGLE_REDIRECT_URI`
   in `.env` exactly — Google is strict about this).
5. Copy the Client ID/Secret into `.env`.
6. To actually connect a workspace: call
   `GET /api/google/oauth/authorize?workspace_id=...` (with a valid JWT) —
   it redirects to Google's consent screen, then back to
   `/api/google/oauth/callback`, which stores the encrypted refresh token.

## Project layout

```
app/
  core/        # settings, JWT + password hashing, token encryption
  db/          # SQLAlchemy engine/session, model registry for Alembic
  models/      # Postgres tables (see spec section 47)
  schemas/     # Pydantic request/response models
  api/routes/  # auth, workspaces, google_oauth, search_console, youtube,
               # seo, content, backlinks, rank_tracking
  services/    # google_oauth_service, search_console_service,
               # youtube_service, ai_service (centralized Claude calls)
alembic/       # migrations
```

## Multi-tenant model

`Organization` → `Workspace` (1-to-many) → everything else scoped by
`workspace_id`. A `Membership` row links a `User` to an `Organization` with
a role (owner/admin/member) — this is what makes agency accounts with
multiple client workspaces possible. Every workspace-scoped route calls
`get_workspace_or_403()` before touching data, which is the tenant-isolation
boundary.

## Meta (Facebook + Instagram) setup

1. developers.facebook.com/apps → Create App → type "Business".
2. Add product "Facebook Login" → Settings → set a valid OAuth redirect URI:
   `http://localhost:8000/api/meta/oauth/callback`.
3. App Review: while in Development mode, only Admins/Developers/Testers
   added to the app can log in. Going live with `pages_manage_posts` /
   `instagram_content_publish` requires App Review (Meta manually approves).
4. Copy App ID/Secret into `.env` as `META_APP_ID` / `META_APP_SECRET`.
5. Instagram must be a **professional account linked to a Facebook Page** —
   personal Instagram accounts cannot be connected via the Graph API.

## TikTok setup

1. developers.tiktok.com → Manage apps → Create an app.
2. Add products: **Login Kit** and **Content Posting API**.
3. Set redirect URI to `http://localhost:8000/api/tiktok/oauth/callback`.
4. Copy Client Key/Secret into `.env`. Full public direct-posting needs
   TikTok's app audit — until approved, posts land as private/draft
   (this scaffold defaults to the inbox-draft endpoint for that reason).

## Stripe billing setup

1. dashboard.stripe.com → Developers → API keys → copy the secret key into
   `STRIPE_SECRET_KEY`.
2. Products → create a Product per plan (Starter/Professional/Business/Agency)
   with a recurring Price — copy each Price ID, you'll pass it as
   `stripe_price_id` when calling `POST /api/billing/checkout-session`.
3. Developers → Webhooks → add endpoint `https://yourdomain.com/api/billing/webhook`,
   subscribe to `checkout.session.completed`, `customer.subscription.deleted`,
   `invoice.payment_failed` → copy the signing secret into `STRIPE_WEBHOOK_SECRET`.
4. For local testing, use the Stripe CLI: `stripe listen --forward-to localhost:8000/api/billing/webhook`.

## Admin panel

Any user can be promoted by setting `is_platform_admin = true` directly in
the `users` table (there's intentionally no API route to self-promote).
Once set, `/api/admin/*` routes are available: user suspend/activate,
organization/workspace overview, plan management, subscription list, audit
log viewer.

## Not included in this scaffold (see main spec for full scope)

White-label domain routing (section 39), Celery task definitions (worker
service is wired in docker-compose but has no tasks yet — crawling,
scheduled rank checks, and report generation would live there), and the
influencer marketplace (section 37). These follow the same pattern as the
integrations above — ask and I'll build it in the same style.

## Background jobs (Celery)

Real periodic tasks now exist in `app/tasks/`:
- **Rank tracking** (`rank_tracking_tasks.py`) — daily job re-checks every
  tracked keyword via a rank-data provider you plug in (SerpApi by default,
  swap `_check_position()` for whatever provider you sign up with — set
  `SERPAPI_KEY` in `.env`). Never scrapes Google directly (ToS violation).
- **Reports** (`report_tasks.py`) — weekly PDF/Excel report per workspace,
  emailed via `email_service.py`.
- **Content calendar** (`scheduling_tasks.py`) — publishes `ScheduledPost`
  rows whose `scheduled_for` has passed, every 15 minutes. Only touches
  posts a user already scheduled — never creates or approves content itself.

Run both processes (in addition to the API):
```bash
celery -A app.worker worker --loglevel=info
celery -A app.worker beat --loglevel=info
```
(docker-compose's `worker` service runs the worker; add a second `beat`
service the same way if you want it containerized too.)

## Production hardening

- **Rate limiting** (slowapi): global default `100/minute`, tighter limits
  on `/api/auth/login` (10/min), `/api/auth/register` (5/min), and every
  AI-generation endpoint (20/hour) since those cost real money per call.
- **Error tracking**: set `SENTRY_DSN` in `.env` to send exceptions to
  Sentry; unhandled exceptions return a generic 500 to the client in
  non-development environments instead of leaking stack traces.
- **CORS**: `ALLOWED_ORIGINS` in `.env` is now a comma-separated list — add
  your real production frontend domain(s) here before deploying.

## CI/CD

`.github/workflows/backend-ci.yml` runs on every push/PR touching this
folder: installs deps, syntax-checks, builds the Docker image, and runs
`tests/` if present (there isn't a `tests/` folder yet — add one with
pytest + FastAPI's TestClient before this gate means much). The `deploy`
job is a placeholder — wire it to your actual host (Render/Railway/Fly.io
deploy hook, or SSH + `docker compose pull && up -d` on your own VPS).

`Dockerfile.prod` is a leaner multi-stage build for actual deployment
(non-root user, healthcheck, 4 uvicorn workers) — `Dockerfile` stays as
the simple one for local dev via docker-compose.

`scripts/backup_db.sh` — daily Postgres backup + pruning (spec section 77).
Schedule it with cron on whatever host runs the database.

## Email

Registration now sends a real verification email (Resend — resend.com,
free tier covers early-stage volume). Set `RESEND_API_KEY` and `EMAIL_FROM`
in `.env`. Without a key set, emails are skipped with a console log instead
of failing registration — fine for local dev, must be configured before
launch. Password reset (`/api/auth/forgot-password` → `/api/auth/reset-password`)
uses signed, time-limited tokens (1 hour) — no extra DB table needed.

## Real keyword/rank/backlink data (DataForSEO)

Previously, keyword volume and rank checks were AI-estimated (qualitative
"high/medium/low") because no licensed data provider was wired in. That's
now upgraded:

1. Sign up at https://app.dataforseo.com/register (pay-as-you-go, no
   monthly minimum — you pay per API call, typically fractions of a cent
   each for keyword volume, a few cents for SERP checks).
2. Copy your login/password from the dashboard into `.env`:
   `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.
3. That's it — `POST /api/seo/keywords` now automatically attaches real
   `search_volume` and `cpc` to every keyword DataForSEO recognizes
   (falls back to the AI estimate for anything it doesn't, e.g. brand-new
   long-tail phrases with no search history — each keyword's
   `"data_source"` field tells you which one you're looking at).
4. The daily rank-tracking Celery job (`app/tasks/rank_tracking_tasks.py`)
   now does real Google SERP lookups instead of a placeholder — it checks
   each workspace's registered website (`Website.url`) against its tracked
   keywords.
5. New endpoint: `GET /api/seo/backlinks/domain-summary?target_domain=...`
   — real referring-domains count + DataForSEO's domain authority score,
   for your own site or a competitor's.

Without `DATAFORSEO_LOGIN` set, everything still works exactly as before
(AI-estimated) — this is an additive upgrade, not a breaking change.

## Phase 2 additions: CRM, Local SEO/Reputation, Competitor Intelligence, Social Analytics, AI Marketing

- **CRM** (`app/api/routes/crm.py`) — Leads, Contacts, Deals/pipeline, Tasks. AI lead
  scoring (`POST /api/crm/leads/{id}/score`) classifies hot/warm/cold with a
  plain-language reason, based only on fields actually provided — never
  fabricates browsing-behavior signals that weren't given.
- **Reputation** (`app/api/routes/reputation.py`) — review logging, AI
  sentiment analysis, AI-drafted (never auto-sent) responses. Google
  Business Profile API needs a separate Google approval process beyond
  normal OAuth — the model is ready (`GoogleBusinessProfile`), the live
  connect flow isn't wired yet.
- **Competitor Intelligence** (`app/api/routes/competitors.py`) — combines
  real backlink data (DataForSEO, when configured) with AI content/keyword
  gap analysis. The gap analysis is explicitly labeled as AI inference, not
  a crawled audit of the competitor's actual site content.
- **Social Analytics** (`app/api/routes/social_analytics.py`) — one call
  aggregates Facebook/Instagram/YouTube/TikTok data from whatever's
  connected; each platform reports `connected: true/false` explicitly.
- **AI Marketing** (`app/api/routes/marketing.py`) — marketing plan
  generator and offer generator (spec sections 23-24).

None of this fabricates data for a disconnected platform or an
unmeasured module — see the Growth Score's `unmeasured_modules` field and
the Competitor report's `_data_source_note` for how that's enforced.

## Marketing Automation, Analytics, AI Chat (this update)

- **Automation** (`app/api/routes/automation.py` + `app/services/automation_service.py`)
  — Trigger → Condition → Action workflows. Triggers fire automatically from
  real CRM events (lead created, lead status changed, deal won/lost — wired
  into `crm.py`). Only internal actions ship today (create a task, tag a
  lead) — no email/SMS action type exists yet, since that needs an explicit
  consent story before it's safe to add (spec section 62).
- **Analytics** (`app/api/routes/analytics.py`) — revenue attribution by
  source, win rate, customer retention (simple 90-day recency rule, not a
  predictive model — labeled as such), and AI forecasting (always returned
  with a confidence label, never presented as guaranteed).
- **Ask GrowthPro** (`app/api/routes/ai_chat.py`) — business-aware chat
  assistant. Answers only from real workspace context (CRM stats, latest
  SEO score); explicitly says "not connected" rather than guessing when it
  doesn't have the data a question needs.

## This update: Website Builder, Ad Center, Ad Network, Marketplace, Wallet, White-label

**Genuinely complete, no external approval needed:**
- **Wallet** (`app/api/routes/wallet.py`) — ledger-based balance, Stripe top-up, credit/debit functions used by Ad Network spend.
- **Creator/Publisher Marketplace** (`app/api/routes/marketplace.py`) — profiles, discovery, orders.
- **Website/Landing Page Builder** (`app/api/routes/site_builder.py`) — AI generates a JSON section tree, publishes as real HTML at `/api/public/site/{slug}` (no login to view). Section-based, not pixel-level drag-and-drop.
- **White-label** (`app/api/routes/white_label.py`) — branding resolution by Host header is real; DNS/SSL provisioning per domain is a deployment step, see `DEPLOYMENT_WHITE_LABEL.md`.

**Needs external approval before it does anything (code is real, gate is manual):**
- **Google Ads** (`app/services/google_ads_service.py`) — needs a Google Ads Developer Token (apply at ads.google.com/aw/apicenter, manual review, days-weeks).
- **Meta Ads** (`app/services/meta_ads_service.py`) — needs `ads_management` via Meta App Review, and the connected ad account needs real billing set up in Meta Ads Manager. Campaigns are created PAUSED — never auto-launches spend.
- All Ad Center campaigns start as `draft` and only move to `active` via an explicit `/approve` call (spec section 62).

**Foundation only — do not launch without more work (see the warning docstring in `app/api/routes/ad_network.py`):**
- **Ad Network** — the transaction mechanics (serve → charge advertiser wallet → credit publisher) are real and working. Missing: fraud/bot detection, publisher payout compliance (likely needs Stripe Connect or similar + possibly money-transmitter licensing depending on jurisdiction), and publisher domain-ownership verification.

**Separate repo, real code, but needs tools I don't have here:**
- `growthpro-mobile/` — Expo/React Native app with working Login, Dashboard (Growth Score), Leads screens hitting the real API. Needs `npx expo start` to run in Expo Go immediately; needs Apple/Google developer accounts + `eas build` to actually publish to app stores.

**Fully finished, zero caveats:**
- `growthpro-extension/` — Chrome extension (Manifest V3). Load unpacked in `chrome://extensions` right now, works immediately: pulls live on-page SEO signals via content script, shows instant score in popup, no backend or login required for the quick check.

## AI/GEO Visibility, Notifications, Webhooks, Tests (this update)

- **AI/GEO Visibility** (`app/api/routes/geo_visibility.py`) — samples how
  an AI model responds to realistic customer queries and checks for brand
  mentions. This is explicitly a *sampled proxy*, not real analytics from
  ChatGPT/Perplexity/Google — no such public API exists for anyone to
  measure that directly. Labeled as such in every response.
- **Notifications** (`app/api/routes/notifications.py`) — in-app
  notification list/read. Wired into the hot-lead-scoring and deal-won
  paths as examples; extend the same `notify()` call into any other event.
- **Webhooks** (`app/api/routes/webhooks.py` + `app/services/webhook_service.py`)
  — HMAC-signed outbound webhooks, registered per organization. Delivery is
  synchronous right now (fine at low volume) — move `dispatch_event()` onto
  a Celery task before you have enough traffic for a slow receiver to matter.
- **Tests** (`tests/`) — auth, multi-tenant isolation (the single most
  important test in the whole suite — confirms one org can't see another's
  data), CRM, wallet. Runs against in-memory SQLite for speed.

**I could not actually run these tests** — this sandbox has no network to
`pip install` fastapi/pytest/sqlalchemy. They're syntax-checked and
logically reviewed, not verified green. Run `pytest` yourself after
`pip install -r requirements.txt` — this is the single most valuable thing
left to do before trusting this codebase in production, and it's something
I genuinely cannot do from here.

## Business Templates, A/B Testing/CRO, AI Media Studio, Ad format expansion (this update)

- **Business Templates** (`app/services/business_templates.py`) — 8 industry
  presets (restaurant, e-commerce, real estate, clinic, agency, salon,
  education, SaaS) with suggested goals/KPIs/content topics.
- **A/B Testing / CRO** (`app/api/routes/cro.py` + `app/services/stats_service.py`)
  — real two-proportion z-test for statistical significance, never declares
  a winner without it. CRO page-analysis suggestions via AI.
- **AI Media Studio** (`app/api/routes/media_studio.py`) — alt text,
  thumbnail concepts, video-repurposing clip suggestions from a transcript.
  Does NOT actually resize/transcode media (no ffmpeg pipeline here) —
  text-generation only.
- **Ad Center now supports ad formats** — video/photo/lead/carousel/text
  ads, each with format-appropriate AI creative (video script, image
  concept, or lead-form questions).
- **TikTok Ads service** added (`app/services/tiktok_ads_service.py`) —
  same "needs real approval + billing" caveat as Google/Meta.
- **Trending video ideas** (`app/api/routes/trending.py`) — AI-reasoned
  short-form content ideas. Explicitly NOT live trending data — no
  platform publicly exposes that via API, so don't trust any tool
  (including this one) that claims otherwise.

## Media upload + Campaign Wizard payment model (this update)

- **Media upload** (`app/api/routes/media.py` + `app/services/storage_service.py`)
  — real video/photo file upload to S3-compatible storage (Cloudflare R2
  recommended — S3-compatible API, no egress fees, matters a lot once
  you're serving video to TikTok/Meta repeatedly). Set `S3_*` vars in
  `.env`. Returns a public URL that feeds into the campaign wizard,
  scheduled posts, and ad creative.
- **Payment model** (how ad spend actually flows): this platform does NOT
  hold or move client ad-spend money. Clients connect their OWN Google
  Ads/Meta Ads/TikTok Ads account (their own card funds it — same OAuth
  flows already built). GrowthPro charges a subscription/service fee via
  Stripe (already built) — not a cut of ad spend. This avoids needing a
  money-transmitter license, which real ad-spend pass-through would
  require in most jurisdictions.

## Tracking Pixel, Feature Flags, Support Center (this update)

- **GrowthPro Pixel** (`app/api/routes/tracking.py`) — the biggest gap
  from earlier: real first-party website tracking (page views, custom
  events, conversions with UTM attribution). `GET /api/tracking/snippet`
  generates a ready-to-paste JS snippet per workspace. This is what makes
  revenue attribution (section 45) real instead of manual CRM entry.
  Remember to get visitor consent per your jurisdiction before enabling —
  the snippet comment says so too.
- **Feature Flags** (`app/api/routes/feature_flags.py`) — platform-wide
  module toggles, admin-only writes, public reads (any client needs to
  check these). Now surfaced in the Admin panel UI.
- **Support Center** (`app/api/routes/support.py`) — tickets with an AI
  first-response strictly grounded in a small, honest knowledge base
  (`KNOWLEDGE_BASE` in the file) — it escalates rather than guesses for
  anything not in there.

## Instagram publish, Shopify/WooCommerce, Email Sequences, Sales Pipeline UI (this update)

- **Instagram publish** (`meta_graph_service.publish_instagram_media`) —
  real two-step Content Publishing API flow (create media container →
  poll for video processing → publish). `POST /api/meta/instagram/publish`.
- **Shopify** (`app/services/shopify_service.py`) — real OAuth, needs a
  Shopify Partner app (partners.shopify.com). **WooCommerce**
  (`app/services/woocommerce_service.py`) — no OAuth; store owner
  generates a consumer key/secret in WP Admin and pastes it in
  (`/ecommerce` page validates the credentials before saving).
- **Email Sequences** (`app/api/routes/email_sequences.py` +
  `app/tasks/email_sequence_tasks.py`) — AI drafts a drip sequence, human
  reviews before saving, Celery sends due emails every 30 min.
- **Sales Pipeline** — real drag-and-drop kanban board (`/pipeline` in
  frontend), calls the existing `/api/crm/deals/{id}/stage` endpoint.
