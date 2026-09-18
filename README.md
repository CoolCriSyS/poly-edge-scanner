# Polymarket Edge Scanner

Where the wallets that actually win on Polymarket are positioned right now — surfaced from [Nansen](https://www.nansen.ai/) onchain data. Built for the **Nansen Meridian Buildathon** (Sept 14–27, 2026).

## What it does

Most Polymarket analytics show you the crowd. This shows you the *winners*: wallets with a proven all-time prediction track record holding significant current positions.

1. **`prediction_market_screener`** — top active Polymarket markets by 24h volume
2. **`prediction_market_top_holders`** — current positions; keep holders above $25k
3. **`prediction_market_address_summary`** — each holder's all-time record; keep wallets with positive lifetime PnL across 10+ markets
4. **Edge strength** = lifetime PnL × win rate × log(markets traded) × log(position size)

## Run the scanner

```bash
python3 scanner.py --markets 15 --min-position 25000 --out scan.json
```

In CI the Nansen key comes from the `NANSEN_API_KEY` environment variable; locally it can use a stored credential. The scanner talks to Nansen's MCP server (`https://mcp.nansen.ai/ra/mcp`) — same key, same credits as the Nansen API.

## Web UI

`web/` is a Next.js app (deploys free on Vercel) rendering the latest scan from `web/public/data/latest.json`.

```bash
cd web && npm install && npm run dev
```

## Automated scans

`.github/workflows/scan.yml` runs the scanner every 6 hours and commits fresh data. Add your Nansen API key as the `NANSEN_API_KEY` repo secret. Each scan logs ~150–250 real API calls, keeping the dashboard fresh.

## Disclaimer

Not financial advice. Prediction markets are risky; wallet track records don't guarantee future results.
