# White-label custom domains — DNS/SSL setup

The app can already TRACK and RESOLVE white-label domains (see
`app/services/white_label_service.py`). What's a one-time infrastructure
step per domain — not something code alone can finish — is making that
domain actually reach your server with valid HTTPS.

## Easiest path: Caddy (automatic HTTPS, handles unlimited domains)

If you're self-hosting (not Vercel/Render), put Caddy in front of your app:

```
# Caddyfile
{$AGENCY_DOMAIN_1}, {$AGENCY_DOMAIN_2} {
    reverse_proxy localhost:3000
}

growthpro.yourdomain.com {
    reverse_proxy localhost:3000
}
```

Caddy auto-provisions Let's Encrypt certificates for every domain listed —
you (or your agency customer) just needs to point a CNAME at your server's
IP, and add the domain to this file (or generate it dynamically from the
`organizations.white_label_domain` column — Caddy supports on-demand TLS
for exactly this multi-tenant-domain case: https://caddyserver.com/docs/automatic-https#on-demand-tls).

## If hosting on Vercel (frontend) + Render/Railway (backend)

Both platforms support adding custom domains per project through their
dashboards, but that's a manual add-per-domain action in their UI/API —
not something that happens automatically when an agency configures a
domain in GrowthPro. You'd call Vercel's Domains API
(https://vercel.com/docs/rest-api/endpoints/domains) from your backend
when `POST /api/white-label/configure` succeeds, to automate that step.

## Bottom line

The branding LOGIC is done. The DNS+SSL PROVISIONING per customer domain
is an infrastructure decision (Caddy on-demand TLS is the simplest,
fully-automatable option) — pick one and wire the last step above.
