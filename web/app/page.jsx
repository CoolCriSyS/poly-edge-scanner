"use client";

import { useEffect, useMemo, useState } from "react";

const fmt$ = (n) =>
  n == null ? "—" : "$" + Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
const signed$ = (n) => (n == null ? "—" : (n < 0 ? "−" : "+") + fmt$(n));
const shortAddr = (a) => (a ? a.slice(0, 6) + "…" + a.slice(-4) : "—");
const polyLink = (id) => `https://polymarket.com/market/${id}`;

export default function Page() {
  const [data, setData] = useState(null);
  const [side, setSide] = useState("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetch("/data/latest.json").then((r) => r.json()).then(setData).catch(() => {});
  }, []);

  const signals = useMemo(() => {
    if (!data) return [];
    return data.signals.filter(
      (s) =>
        (side === "all" || s.side.toLowerCase() === side) &&
        (query === "" || s.question.toLowerCase().includes(query.toLowerCase()))
    );
  }, [data, side, query]);

  const maxStrength = useMemo(
    () => Math.max(1, ...(signals.map((s) => s.edge_strength || 0))),
    [signals]
  );

  if (!data) return <div className="wrap"><div className="empty">Loading scan data…</div></div>;

  const scannedAt = data.scanned_at ? new Date(data.scanned_at).toLocaleString() : "—";

  return (
    <div className="wrap">
      <div className="hero">
        <span className="kicker">Nansen Meridian Buildathon</span>
        <h1>Polymarket <span className="accent">Edge Scanner</span></h1>
        <p>
          Where the wallets that actually win on Polymarket are positioned right now.
          Every signal below is a wallet with a proven all-time prediction record holding a
          significant current position — surfaced from Nansen's onchain data.
        </p>
      </div>

      <div className="stats">
        <div className="stat"><div className="label">Edge signals</div><div className="value green">{data.signals.length}</div></div>
        <div className="stat"><div className="label">Markets scanned</div><div className="value">{data.markets_scanned ?? "—"}</div></div>
        <div className="stat"><div className="label">Nansen API calls</div><div className="value">{data.api_calls}</div></div>
        <div className="stat"><div className="label">Last scan</div><div className="value" style={{fontSize:15}}>{scannedAt}</div></div>
      </div>

      <div className="filters">
        <div className="seg">
          {["all", "yes", "no"].map((s) => (
            <button key={s} className={side === s ? "active" : ""} onClick={() => setSide(s)}>
              {s === "all" ? "All sides" : s.toUpperCase()}
            </button>
          ))}
        </div>
        <input
          type="text" placeholder="Filter markets…" value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="signals">
        {signals.map((s, i) => (
          <div className="card" key={i}>
            <p className="q">
              <span className={`side-badge ${s.side.toLowerCase()}`}>{s.side}</span>
              {s.question}
            </p>
            <div className="meta">
              Market #{s.market_id} · resolves {s.end_time} ·{" "}
              <a href={polyLink(s.market_id)} target="_blank" rel="noreferrer">Polymarket ↗</a>
            </div>
            <div className="grid2">
              <div className="kv">
                <div className="k">Smart wallet</div>
                <div className="v">{shortAddr(s.wallet)}</div>
                <div className="sub">
                  All-time <span className={s.wallet_alltime_pnl_usd >= 0 ? "pos" : "neg"}>{signed$(s.wallet_alltime_pnl_usd)}</span>
                  {" · "}{(s.wallet_win_rate * 100).toFixed(0)}% win · {s.wallet_markets_traded} markets
                </div>
              </div>
              <div className="kv">
                <div className="k">Current position</div>
                <div className="v">{fmt$(s.position_value_usd)}</div>
                <div className="sub">
                  Entry {s.avg_entry} → now {s.current_price}
                  {" · "}unrealized <span className={s.unrealized_pnl_usd >= 0 ? "pos" : "neg"}>{signed$(s.unrealized_pnl_usd)}</span>
                </div>
              </div>
            </div>
            <div className="strength">
              <div className="bar"><div className="fill" style={{ width: `${(100 * s.edge_strength / maxStrength).toFixed(1)}%` }} /></div>
              <div className="lbl">Edge strength {Math.round(s.edge_strength).toLocaleString()}</div>
            </div>
          </div>
        ))}
      </div>
      {signals.length === 0 && <div className="empty">No signals match these filters.</div>}

      <div className="method">
        <h2>How the edge is computed</h2>
        <ol>
          <li><code>prediction_market_screener</code> — top active Polymarket markets by 24h volume.</li>
          <li><code>prediction_market_top_holders</code> — current positions; keep holders above $25k.</li>
          <li><code>prediction_market_address_summary</code> — each holder's all-time record; keep wallets with positive lifetime PnL across 10+ markets.</li>
          <li>Edge strength = lifetime PnL × win rate × log(markets traded) × log(position size).</li>
        </ol>
      </div>

      <div className="footer">
        Data via <a href="https://docs.nansen.ai/mcp/overview" target="_blank" rel="noreferrer">Nansen MCP</a> ·
        Built for the Nansen Meridian Buildathon · Not financial advice
      </div>
    </div>
  );
}
