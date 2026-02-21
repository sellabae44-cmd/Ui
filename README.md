# SpyTON Ops Bot (BuyBot + Ads + Trending hooks) — Python (aiogram v3)

This repo is a **SpyTON-styled** Telegram bot framework that includes:
- 🛰️ **Ops Center UI** (inline keyboard, 2-column layout) — unique branding, not a Maziton clone
- 🔎 **Track Tokens**: add/view/toggle/delete tokens per group/chat
- 📢 **Intel Ads**: create adverts, enable/disable ads per group, simple rotation
- 🧾 **Logs**: admin action log
- ✅ **Reliability core**: DB-backed dedupe + cursor storage (restart-safe)
- 🔌 **Sources plugins**: stubs for TON DEX / indexers + a **Mock Source** to test posting right away

> Real buy tracking requires an external data source (indexer / DEX API).
> Included:
> - `sources/mock_source.py` (works immediately for testing)
> - `sources/tonapi_source.py` (optional; needs `TONAPI_KEY` and endpoint mapping)

## Deploy on Railway (phone-friendly)

1. Create Railway project and deploy this repo.
2. Add **PostgreSQL** plugin (Railway sets `DATABASE_URL`).
3. Set env vars:
   - `BOT_TOKEN`
   - `DATABASE_URL` (auto)
   Optional:
   - `POLL_INTERVAL` (default 6)
   - `MOCK_TRADES=1` (to test posting)
   - `TONAPI_KEY` (to enable tonapi source)
4. Start command:
   ```bash
   python -m app.main
   ```

Recommended:
- Serverless OFF (for real-time bots)
- Restart policy On Failure

## Quick test (no real trade source)
Set `MOCK_TRADES=1`, then in group:
- `/setup` → Track Tokens → Add Token → paste any EQ... address
You should see mock buy posts.

## Structure
See `app/` folder. Add real DEX sources in `app/sources/`.
