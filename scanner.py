#!/usr/bin/env python3
"""Polymarket Edge Scanner v0.1 — Nansen Meridian Buildathon prototype.

Finds Polymarket markets where wallets with a proven prediction track record
hold significant current positions. "Edge" = proven winners, big positions.

Pipeline (Nansen MCP tools):
  prediction_market_screener -> top active markets by 24h volume
  prediction_market_top_holders -> current positions per market
  prediction_market_address_summary -> each holder's all-time prediction record

Usage:
  scanner.py [--markets N] [--min-position USD] [--min-markets-traded N]
             [--out report.json]
"""
import argparse
import datetime
import json
import math
import os
import re
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
try:
    from dynamic_credentials import (  # noqa: E402
        add_surrogate_to_request,
        read_response_body,
    )
    HAS_SURROGATE = True
except ImportError:
    HAS_SURROGATE = False

ENDPOINT = "https://mcp.nansen.ai/ra/mcp"
CREDENTIAL = "custom.nansen"
ALLOWED_HOSTS = ("mcp.nansen.ai",)

CALL_COUNT = 0


def _post(payload):
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    api_key = os.environ.get("NANSEN_API_KEY")
    if api_key:
        # CI / GitHub Actions path: key from environment
        req.add_header("NANSEN-API-KEY", api_key)
    elif HAS_SURROGATE:
        add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED_HOSTS)
    else:
        raise RuntimeError("No Nansen API key: set NANSEN_API_KEY or run where the credential helper exists.")
    with urllib.request.urlopen(req, timeout=90) as resp:
        if HAS_SURROGATE:
            body = read_response_body(resp).decode("utf-8", errors="replace")
        else:
            body = resp.read().decode("utf-8", errors="replace")
    lines = [l for l in body.splitlines() if l.strip().startswith("data:")]
    if lines:
        body = lines[-1][len("data:"):].strip()
    return json.loads(body)


def rpc(method, params=None):
    global CALL_COUNT
    CALL_COUNT += 1
    payload = {"jsonrpc": "2.0", "id": CALL_COUNT, "method": method}
    if params is not None:
        payload["params"] = params
    data = _post(payload)
    contents = data.get("result", {}).get("content", [])
    texts = [c.get("text", "") for c in contents if c.get("type") == "text"]
    return "\n".join(texts)


def parse_tables(text):
    """Parse markdown pipe tables into list of {headers, rows}."""
    tables, current = [], []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            current.append(line)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    out = []
    for t in tables:
        if len(t) < 3:
            continue
        headers = [h.strip() for h in t[0].strip().strip("|").split("|")]
        for line in t[2:]:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == len(headers):
                out.append(dict(zip(headers, cells)))
    return out


def parse_money(s):
    """'136.7k' -> 136700.0 ; handles k/M/B, negatives, 'N/A'."""
    if not s:
        return 0.0
    s = s.strip().replace(",", "").replace("$", "")
    if s in ("N/A", "-", "--", ""):
        return 0.0
    m = re.fullmatch(r"(-?[\d.]+)\s*([kmbKMB])?", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return 0.0
    val = float(m.group(1))
    mult = {"k": 1e3, "m": 1e6, "b": 1e9}.get((m.group(2) or "").lower(), 1)
    return val * mult


def parse_kv(text, key):
    m = re.search(rf"\*\*{re.escape(key)}\*\*:\s*([^\n*]+)", text)
    if not m:
        m = re.search(rf"{re.escape(key)}:\s*([^\n]+)", text)
    return m.group(1).strip() if m else ""


def screener(n):
    text = rpc("tools/call", {
        "name": "prediction_market_screener",
        "arguments": {"request": {"mode": "markets", "status": "active", "page": 1}},
    })
    rows = parse_tables(text)[:n]
    markets = []
    for r in rows:
        markets.append({
            "market_id": r.get("Market ID", ""),
            "question": r.get("Question", ""),
            "end_time": r.get("End Time", ""),
            "volume_24h": parse_money(r.get("24h Volume", "")),
            "liquidity": parse_money(r.get("Liquidity", "")),
            "open_interest": parse_money(r.get("Open Interest", "")),
        })
    return markets


def top_holders(market_id):
    text = rpc("tools/call", {
        "name": "prediction_market_top_holders",
        "arguments": {"request": {"marketId": str(market_id), "page": 1}},
    })
    holders = []
    for r in parse_tables(text):
        holders.append({
            "address": r.get("Address", ""),
            "side": r.get("Side Held", ""),
            "position_value": parse_money(r.get("Position Value USD", "")),
            "avg_entry": r.get("Avg Entry Price", ""),
            "current_price": r.get("Current Price", ""),
            "unrealized_pnl": parse_money(r.get("Unrealized PnL USD", "")),
        })
    return holders


def wallet_record(address):
    text = rpc("tools/call", {
        "name": "prediction_market_address_summary",
        "arguments": {"request": {"address": address, "page": 1}},
    })
    win_rate = parse_kv(text, "Win Rate").replace("%", "")
    return {
        "address": address,
        "total_pnl": parse_money(parse_kv(text, "Total PnL USD")),
        "win_rate": float(win_rate) / 100 if win_rate.replace(".", "").isdigit() else 0.0,
        "markets_traded": int(parse_money(parse_kv(text, "Markets Traded") or "0")),
        "markets_won": int(parse_money(parse_kv(text, "Markets Won") or "0")),
    }


def scan(args):
    signals = []
    markets = screener(args.markets)
    print(f"[scan] {len(markets)} markets | api calls so far: {CALL_COUNT}", file=sys.stderr)
    for m in markets:
        if m["liquidity"] < 10_000:
            continue  # skip dust markets
        holders = [h for h in top_holders(m["market_id"])
                   if h["position_value"] >= args.min_position and h["address"]]
        for h in holders:
            rec = wallet_record(h["address"])
            if rec["total_pnl"] <= 0 or rec["markets_traded"] < args.min_markets_traded:
                continue  # not a proven winner
            strength = rec["total_pnl"] * rec["win_rate"] * math.log1p(rec["markets_traded"]) \
                * math.log1p(h["position_value"])
            signals.append({
                "market_id": m["market_id"],
                "question": m["question"],
                "end_time": m["end_time"],
                "side": h["side"],
                "wallet": h["address"],
                "position_value_usd": round(h["position_value"], 2),
                "avg_entry": h["avg_entry"],
                "current_price": h["current_price"],
                "unrealized_pnl_usd": round(h["unrealized_pnl"], 2),
                "wallet_alltime_pnl_usd": round(rec["total_pnl"], 2),
                "wallet_win_rate": round(rec["win_rate"], 3),
                "wallet_markets_traded": rec["markets_traded"],
                "edge_strength": round(strength, 2),
            })
        print(f"[scan] {m['market_id']}: {len(holders)} big holders | calls: {CALL_COUNT}",
              file=sys.stderr)
    signals.sort(key=lambda s: s["edge_strength"], reverse=True)
    return {
        "scanned_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "markets_scanned": len(markets),
        "api_calls": CALL_COUNT,
        "signals": signals,
    }


def main():
    ap = argparse.ArgumentParser(description="Polymarket Edge Scanner")
    ap.add_argument("--markets", type=int, default=10)
    ap.add_argument("--min-position", type=float, default=25_000)
    ap.add_argument("--min-markets-traded", type=int, default=10)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    report = scan(args)
    print(f"\n=== EDGE SCAN — {len(report['signals'])} signals ({report['api_calls']} API calls) ===\n")
    for s in report["signals"][:20]:
        print(f"{s['side']:4} | {s['question'][:70]}")
        print(f"     wallet {s['wallet'][:10]}… "
              f"all-time +${s['wallet_alltime_pnl_usd']:,.0f} "
              f"({s['wallet_win_rate']:.0%} win, {s['wallet_markets_traded']} mkts) "
              f"| pos ${s['position_value_usd']:,.0f} @ entry {s['avg_entry']} → now {s['current_price']} "
              f"| strength {s['edge_strength']:,.0f}")
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
