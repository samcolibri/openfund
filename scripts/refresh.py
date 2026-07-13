#!/usr/bin/env python3.12
"""
NSE Value Radar — data refresher.

Reads data/fundamentals.json (hand-verified from screener.in),
pulls fresh prices/technicals from Yahoo Finance (.NS tickers),
recomputes IVQM composite scores, and writes data/stocks.js
for the 3D dashboard (index.html).

Usage:
    python3.12 scripts/refresh.py            # full refresh (needs internet)
    python3.12 scripts/refresh.py --offline  # rescore only, keep old technicals

Scoring = adapted IVQM-100 (Value 30 / Quality 30 / Momentum 25 / Safety 15).
Evidence base: Magic Formula India backtest (SSRN 3945468), Piotroski F-Score
India (IJEF 2015), AQR Value & Momentum Everywhere (JF 2013), Capitalmind
Trending Value NSE backtest, George & Hwang 52-week-high momentum.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUND = ROOT / "data" / "fundamentals.json"
OUT = ROOT / "data" / "stocks.js"
NIFTY = "^NSEI"


def _rsi14(close):
    """Wilder RSI: RS = avg gain / avg loss over 14 periods; RSI = 100 - 100/(1+RS)."""
    diff = close.diff()
    gain = diff.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-diff.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    return float((100 - 100 / (1 + rs)).iloc[-1])


def _macd(close):
    """MACD = EMA12 - EMA26; signal = EMA9 of MACD; histogram = MACD - signal."""
    e12 = close.ewm(span=12, adjust=False).mean()
    e26 = close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(sig.iloc[-1]), float((macd - sig).iloc[-1])


def fetch_technicals(symbols):
    import yfinance as yf
    tech = {}
    for s in symbols + [NIFTY]:
        ticker = s if s.startswith("^") else s + ".NS"
        try:
            h = yf.Ticker(ticker).history(period="1y", auto_adjust=True)
            if h.empty:
                tech[s] = None
                continue
            close, vol = h["Close"], h["Volume"]
            last = float(close.iloc[-1])
            d20 = float(close.rolling(20).mean().iloc[-1])
            d200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
            d50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
            hi52, lo52 = float(close.max()), float(close.min())
            n = len(close)
            ret6 = (last / float(close.iloc[max(0, n - 126)]) - 1) * 100 if n > 20 else None
            ret12 = (last / float(close.iloc[0]) - 1) * 100 if n > 200 else None
            macd, sig, hist = _macd(close)
            # Bollinger (20, 2): position of price inside the band, 0=lower 100=upper
            std20 = float(close.rolling(20).std().iloc[-1])
            bb_pos = (last - (d20 - 2 * std20)) / (4 * std20) * 100 if std20 else None
            # 20d volume vs 90d average — is money flowing in?
            v20 = float(vol.tail(20).mean()) if len(vol) >= 20 else None
            v90 = float(vol.tail(90).mean()) if len(vol) >= 90 else None
            # annualized daily volatility, %
            dret = close.pct_change().dropna()
            vol_ann = float(dret.tail(120).std()) * (252 ** 0.5) * 100 if len(dret) > 30 else None
            tech[s] = {
                "price": round(last, 1),
                "ret_6m": round(ret6, 1) if ret6 is not None else None,
                "ret_12m": round(ret12, 1) if ret12 is not None else None,
                "above_200dma": round((last / d200 - 1) * 100, 1) if d200 else None,
                "above_50dma": round((last / d50 - 1) * 100, 1) if d50 else None,
                "dma50_gt_dma200": bool(d50 and d200 and d50 > d200),
                "pct_off_52w_high": round((last / hi52 - 1) * 100, 1),
                "pct_above_52w_low": round((last / lo52 - 1) * 100, 1),
                "rsi14": round(_rsi14(close), 1),
                "macd": round(macd, 2), "macd_signal": round(sig, 2),
                "macd_hist": round(hist, 2), "macd_bull": hist > 0,
                "bb_pos": round(bb_pos, 0) if bb_pos is not None else None,
                "vol_ratio_20_90": round(v20 / v90, 2) if v20 and v90 else None,
                "volatility_ann": round(vol_ann, 1) if vol_ann else None,
                "dma200": round(d200, 1) if d200 else None,
                "dma50": round(d50, 1) if d50 else None,
            }
        except Exception as e:
            print(f"  ! {s}: {e}", file=sys.stderr)
            tech[s] = None
    return tech


def tier(v, bands):
    """bands = [(threshold, points), ...] descending; v below all -> 0."""
    if v is None:
        return None
    for th, pts in bands:
        if v >= th:
            return pts
    return 0


def score_stock(s, t, nifty_ret6):
    is_bank = s["sector"] in ("PSU Bank", "Private Bank", "Insurance", "Power Financier",
                              "NBFC", "Housing Finance")

    # VALUE (30)
    pe = s.get("pe")
    v_pe = tier(-pe, [(-6, 10), (-10, 8), (-14, 6), (-18, 4), (-25, 2)]) if pe else 0
    pb = s.get("pb")
    v_pb = tier(-pb, [(-1, 6), (-2, 4.5), (-3, 3), (-4, 1.5)]) if pb else 3
    v_dy = tier(s.get("div_yield"), [(5, 7), (3, 5), (2, 3), (1, 1)]) or 0
    off_high = t.get("pct_off_52w_high") if t else None
    v_entry = tier(-(off_high or 0), [(25, 7), (15, 5), (8, 3)]) or 1
    value = min(30, (v_pe or 0) + v_pb + v_dy + v_entry)

    # QUALITY (30)
    prof = s.get("roce") if not is_bank else s.get("roe")
    q_ret = tier(prof, [(30, 12), (20, 10), (15, 7), (10, 4)]) or 0
    q_gr = tier(s.get("profit_growth"), [(40, 10), (20, 8), (10, 6), (0, 3)]) or 0
    de = s.get("de")
    q_de = 4 if is_bank or de is None else (tier(-de, [(-0.1, 8), (-0.3, 6), (-0.6, 4), (-1.0, 2)]) or 0)
    quality = min(30, q_ret + q_gr + q_de)

    # MOMENTUM (25)
    momentum = 0
    if t:
        a200 = t.get("above_200dma")
        momentum += 8 if (a200 or -99) > 0 else (4 if (a200 or -99) > -5 else 0)
        momentum += 5 if t.get("dma50_gt_dma200") else 0
        r6 = t.get("ret_6m")
        if r6 is not None and nifty_ret6 is not None:
            momentum += 7 if r6 > nifty_ret6 + 10 else (4 if r6 > nifty_ret6 else 0)
        r12 = t.get("ret_12m")
        momentum += 5 if (r12 or -99) > 15 else (3 if (r12 or -99) > 0 else 0)

    # SAFETY (15)
    safety = 4 if (s.get("pledged") or 0) == 0 else 0
    ph = s.get("promoter_holding") or 0
    safety += 5 if ph >= 50 else (4 if ph >= 40 else 3)  # <40 = MNC/professional waiver
    mc = s.get("market_cap_cr") or 0
    safety += 3 if mc >= 100000 else (2 if mc >= 20000 else 1)
    safety += 3 if (is_bank or de is None or de <= 0.5) else 1

    return {
        "value": round(value), "quality": round(quality),
        "momentum": round(momentum), "safety": round(safety),
        "composite": round(value + quality + momentum + safety),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip yfinance, reuse old technicals")
    args = ap.parse_args()

    fund = json.loads(FUND.read_text())
    stocks = fund["stocks"]
    symbols = [s["symbol"] for s in stocks]

    old = {}
    if OUT.exists():
        raw = OUT.read_text()
        old_data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        old = {s["symbol"]: s for s in old_data.get("stocks", [])}

    if args.offline:
        _KEYS = ("price", "ret_6m", "ret_12m", "above_200dma", "above_50dma", "dma50_gt_dma200",
                 "pct_off_52w_high", "pct_above_52w_low", "rsi14", "macd", "macd_signal",
                 "macd_hist", "macd_bull", "bb_pos", "vol_ratio_20_90", "volatility_ann",
                 "dma200", "dma50")
        tech = {sym: {k: old.get(sym, {}).get(k) for k in _KEYS} for sym in symbols}
        nifty_ret6 = old.get("_nifty_ret6", -7.5) if isinstance(old.get("_nifty_ret6"), (int, float)) else -7.5
    else:
        print("Fetching technicals from Yahoo Finance...")
        tech = fetch_technicals(symbols)
        nifty_t = tech.get(NIFTY) or {}
        nifty_ret6 = nifty_t.get("ret_6m")

    out_stocks = []
    for s in stocks:
        t = tech.get(s["symbol"]) or {}
        merged = dict(s)
        merged.update({k: t.get(k) for k in
                       ("ret_6m", "ret_12m", "above_200dma", "above_50dma", "dma50_gt_dma200",
                        "pct_off_52w_high", "pct_above_52w_low", "rsi14", "macd", "macd_signal",
                        "macd_hist", "macd_bull", "bb_pos", "vol_ratio_20_90", "volatility_ann",
                        "dma200", "dma50")})
        merged["price"] = t.get("price") or s.get("price")
        merged["scores"] = score_stock(s, t, nifty_ret6)
        # Upside model: implied price = anchor (EPS or BVPS) x (1 + growth) x target multiple.
        # Expected return = price gain to implied + ~6 months of dividends.
        m = s.get("math")
        if m and merged["price"]:
            implied = m["anchor"] * (1 + m["growth_pct"] / 100) * m["target_multiple"]
            gain = (implied / merged["price"] - 1) * 100
            merged["math"] = dict(m)
            merged["math"]["implied_price"] = round(implied)
            merged["math"]["price_gain_pct"] = round(gain, 1)
            merged["math"]["expected_total_pct"] = round(gain + m.get("div_6m_pct", 0), 1)
            # Risk-reward: upside vs fall-to-support. Support = 200-DMA when price is
            # above it, else the 52-week low. Downside floored at 5% (nothing falls 0%).
            a200 = t.get("above_200dma")
            if a200 is not None and a200 > 0:
                downside, ref = max(5.0, a200), "200-DMA"
            else:
                downside, ref = max(5.0, t.get("pct_above_52w_low") or 15.0), "52w low"
            merged["math"]["downside_pct"] = round(downside, 1)
            merged["math"]["downside_ref"] = ref
            merged["math"]["risk_reward"] = round(merged["math"]["expected_total_pct"] / downside, 1)
        out_stocks.append(merged)

    out_stocks.sort(key=lambda x: -x["scores"]["composite"])
    payload = {
        "as_of": datetime.date.today().isoformat(),
        "universe": "NIFTY 500 — H1 2026 value screen",
        "method": "IVQM composite: Value 30 · Quality 30 · Momentum 25 · Safety 15. Gold ring = top pick.",
        "nifty_ret_6m": nifty_ret6,
        "stocks": out_stocks,
    }
    OUT.write_text("// generated by scripts/refresh.py — do not edit by hand\n"
                   "window.STOCK_DATA = " + json.dumps(payload, indent=1) + ";\n")
    print(f"Wrote {OUT} — {len(out_stocks)} stocks, as of {payload['as_of']}")
    for s in out_stocks:
        flag = "★" if s.get("top_pick") else " "
        print(f"  {flag} {s['symbol']:<12} composite {s['scores']['composite']:>3}  "
              f"(V{s['scores']['value']} Q{s['scores']['quality']} "
              f"M{s['scores']['momentum']} S{s['scores']['safety']})")


if __name__ == "__main__":
    main()
