import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.limiter import limiter

from app.core.config import settings
from app.api.routes import (
    auth, workspaces, google_oauth, search_console, youtube,
    meta_oauth, meta, tiktok_oauth, tiktok,
    seo, content, backlinks, rank_tracking, websites,
    admin, billing, growth, public,
    crm, reputation, competitors, social_analytics, marketing,
    automation, analytics, ai_chat, wallet, white_label, marketplace, site_builder, advertising, ad_network,
    geo_visibility, notifications, webhooks, templates, cro, media_studio, trending, campaign_wizard, media, tracking,
    feature_flags, support, ecommerce, email_sequences,
)

# Error tracking (spec section 46: audit logs / error visibility). No-op if DSN is blank.
if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2, environment=settings.APP_ENV)

app = FastAPI(title="GrowthPro API", version="0.3.0")

# Rate limiting — protects auth + AI-generation endpoints (the expensive ones) from abuse.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in [
    auth.router, workspaces.router,
    google_oauth.router, search_console.router, youtube.router,
    meta_oauth.router, meta.router, tiktok_oauth.router, tiktok.router,
    seo.router, content.router, backlinks.router, rank_tracking.router, websites.router,
    admin.router, billing.router, growth.router, public.router,
    crm.router, reputation.router, competitors.router, social_analytics.router, marketing.router,
    automation.router, analytics.router, ai_chat.router, wallet.router, white_label.router, marketplace.router, site_builder.router, advertising.router, ad_network.router,
    geo_visibility.router, notifications.router, webhooks.router, templates.router, cro.router, media_studio.router, trending.router, campaign_wizard.router, media.router, tracking.router,
    feature_flags.router, support.router, ecommerce.router, email_sequences.router,
]:
    app.include_router(r)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Never leak internal error details (stack traces, DB errors) to the client
    in production — log the full error server-side (Sentry catches it above),
    return a generic message to the caller.
    """
    if settings.APP_ENV == "development":
        raise exc
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health():
    return {"status": "ok", "env": settings.APP_ENV}
