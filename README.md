# NSE Value Radar — H1 2026 NIFTY 500 Value Screen + 3D Dashboard

Local-only (no git). Screens NIFTY 500 for value stocks with credible 20–30% upside
over 6–18 months, visualized as a 3D Value × Quality × Momentum scatter.

## Open the dashboard

```bash
open ~/projects/nse-value-screener/index.html
```

Needs internet once per load (Three.js from cdnjs). Data loads from `data/stocks.js` (works on `file://`).

## Update from this laptop

```bash
cd ~/projects/nse-value-screener
python3.12 scripts/refresh.py        # re-pulls prices/technicals from Yahoo Finance, rescores, rewrites data/stocks.js
```

- **Technicals** (price, 6m/12m return, 200-DMA, 52w-high proximity): automatic via yfinance (`.NS` tickers — verified working July 2026).
- **Fundamentals** (PE, ROCE, D/E, promoter holding…): hand-verified from screener.in — edit `data/fundamentals.json` when quarterly results land, then rerun refresh. (screener.in CSV export needs a logged-in browser; per-company pages are the source of truth.)
- To add/remove stocks: edit `data/fundamentals.json` (copy an existing entry, fill from `screener.in/company/SYMBOL/consolidated/`), rerun refresh.
- NIFTY 500 universe list: `https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv` (needs a browser User-Agent header).

## Methodology — IVQM composite (0–100)

Weights: **Value 30 · Quality 30 · Momentum 25 · Safety 15** — implemented in `scripts/refresh.py`.

Evidence base (full research saved in `docs/RESEARCH.md`):
- Magic Formula works in India: 13.9% CAGR vs 9.3% Sensex, FY12–20 (SSRN 3945468)
- Piotroski F-Score is the best value-trap filter in India (IJEF 2015, top-500 NSE study)
- Value + momentum combined ≈ doubles value-only Sharpe (AQR, Journal of Finance 2013); Capitalmind's Trending Value NSE backtest: ₹100 → ₹1,921 vs ₹448 Nifty (2007–23)
- 52-week-high proximity momentum (George & Hwang, JF 2004)
- India-specific hard gates: promoter pledging ≤5%, D/E <1, positive PAT, liquidity (NIFTY 500 membership)

**Realistic expectations:** screens like this beat the index in ~59% of 1-year windows and ~70% of
3-year windows historically, with 50–60% individual winners. +20–30% in 6 months happens in trending
markets, not guaranteed. Position ≤5% per name. Sell rules: score decay below ~55, 15+ sessions below
200-DMA, any pledge appears, promoter sells >2%, auditor resigns.

## H1 2026 context (why these picks)

Nifty peaked 26,373 on Jan 5, crashed to 22,182 (−16%) on the Strait-of-Hormuz oil shock (March worst),
record FPI outflow ~₹2.2 lakh cr, INR hit 96.84 (May 20), then Iran–Israel ceasefire collapsed crude and
the index recovered to 24,271 by Jul 3 (−7.1% H1). June rotation: banks +6.4%, IT −9.6% (TCS/INFY/WIPRO
at 52-week lows Jul 1). Setup: low-PE high-ROCE cash generators + record ₹32,000 cr/month SIP flows.

## The systematic universe screen

`python3.12 scripts/screen_universe.py` runs the ENTIRE NIFTY 500 (not a curated list):
downloads constituents from niftyindices.com, batch-fetches 1y prices, computes RSI-14 /
MACD / DMA trend filters (270 of 500 survived on 2026-07-05), then pulls valuation via
yfinance and keeps PE < 16, ROE > 12%, mcap > ₹1,500 cr → 43 candidates saved to
`data/universe_screen.json`. New names get hand-verified on screener.in before entering
`fundamentals.json`. This is how PFC, NATIONALUM and GESHIP were found.

## Current picks (scored 2026-07-05, 18 screened, 12 picks)

| Rank | Stock | Composite | Style |
|------|-------|-----------|-------|
| 1 | NATIONALUM | 88 | Quality-value + momentum (universe screen find) |
| 2 | COALINDIA | 85 | Value + trend intact |
| 3 | NMDC | 80 | Value + momentum |
| 3 | PFC | 80 | Lender value, cleanest NPAs (universe screen find) |
| 5 | CHAMBLFERT | 76 | Value + trend intact |
| 6 | KARURVYSYA | 72 | Quality bank + momentum |
| 7 | TANLA | 70 | Quality tech at value price (hidden-gems find) |
| 8 | LICI | 68 | Value + flow tailwind |
| 9 | PETRONET | 67 | Value + LNG catalyst |
| 10 | INFY | 60 | Contrarian (below 200-DMA — stagger entry) |
| 10 | HINDPETRO | 60 | Contrarian (crude-collapse catalyst) |
| 12 | GPPL | 58 | Contrarian cash machine at 52w low, 5.3% yield (hidden-gems find) |
| — | GESHIP 80 / LICHSGFIN 64 / ONGC 61 / HCLTECH 57 / CPCL 56 / BANKBARODA 50 | | Watchlist |

Hidden-gems sweep also verified-and-rejected (see docs/RESEARCH.md): MASTEK (N500 membership
borderline), JKTYRE (D/E 0.81 + promoter selling), KTKBANK (ROE 10.4%), SCI, RECLTD/NATCOPHARM
(profit down YoY), CANFINHOME (P/B 2.0), GULFOILLUB (flat quarter, promoter drift), SARDAEN (PE 16.3),
Nuvama (62.8% PLEDGE — instant kill), MOIL/GMDC/NLC/EIL/Apollo Tyres/Deepak Fert/etc. on valuation or quality.

Not SEBI-registered investment advice. Educational screen — verify everything before acting.
