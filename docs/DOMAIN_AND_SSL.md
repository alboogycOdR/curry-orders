# Domain & SSL Setup

**Status: Pending — to be done before go-live.**

Clean URL and HTTPS are both achievable on Clawsrv at zero or near-zero cost. They depend on each other — SSL requires a domain name; hiding the port requires Caddy, which is already on the server.

---

## The dependency

Let's Encrypt (the free SSL authority trusted by all browsers) does not issue certificates for bare IP addresses — only domain names. So both goals require a domain first.

---

## Option A — Free subdomain via DuckDNS (recommended starting point)

1. Go to [duckdns.org](https://www.duckdns.org) and sign in with Google
2. Create a subdomain — e.g. `roticonnect.duckdns.org`
3. Point it at `204.168.249.99`
4. Add a Caddy site block on Clawsrv (see below)
5. Result: `https://roticonnect.duckdns.org` — no port, green padlock, free forever

**Upside:** Zero cost, works immediately.
**Downside:** URL contains `.duckdns.org` — fine for testing and Brandon's sign-off, less ideal for customer-facing launch.

---

## Option B — Proper .co.za domain (~R100–R150/year)

Register `roticonnect.co.za` (or similar) through a South African registrar. Same Caddy setup as Option A, but the URL is clean and professional. Right answer for go-live.

Suggested registrars: [Afrihost](https://www.afrihost.com), [Hetzner SA](https://www.hetzner.co.za), [Xneelo](https://xneelo.co.za).

---

## Caddy config change (applies to both options)

Clawsrv already runs Caddy as a shared reverse proxy for other tenants. The change is a single site block appended to the host Caddyfile — Caddy fetches and renews the Let's Encrypt cert automatically.

```caddy
roticonnect.duckdns.org {
    reverse_proxy localhost:8102
}
```

Replace `roticonnect.duckdns.org` with the chosen domain. Caddy handles:
- Automatic HTTPS (Let's Encrypt cert, 90-day auto-renewal)
- HTTP → HTTPS redirect
- Hiding port 8102 from the public URL

**Important:** Edit the host Caddyfile carefully — other tenants (`skulcozm`, `osiris`, etc.) share it. Only append; never touch existing site blocks. Reload with `systemctl reload caddy` and verify other tenant sites still respond before declaring done.

---

## Implementation steps (when ready)

1. Choose Option A or B and register/configure the domain
2. SSH into Clawsrv: `ssh clawusr@100.78.70.2`
3. Find the Caddyfile: `caddy environ | grep -i config` or `sudo find / -name Caddyfile 2>/dev/null`
4. Append the site block above (with the correct domain)
5. `sudo systemctl reload caddy`
6. Verify: `curl -I https://<your-domain>/` — expect `200 OK` and `server: Caddy`
7. Update `DEPLOYMENTS.md` with the new URL
8. Update `CLAUDE.md` with the new URL
9. If `.co.za` domain: update any customer-facing copy that references the old IP:port URL

---

## After this is done

- Remove the interim media proxy (`/media/<path:key>` in `public/urls.py`) once MinIO is exposed publicly via Caddy with a separate subdomain or path — or keep the proxy if MinIO stays internal (simpler, slightly more server load).
- See `docs/RUNBOOK.md` for the first-deploy section which references this same Caddy step.
