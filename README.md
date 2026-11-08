# AI Paper Trader

A small automated trading bot that runs on **GitHub Actions** and trades a **paper (fake-money) Alpaca account**.

**How it works (once per weekday):**
1. Pulls daily prices for your symbols from Alpaca.
2. Rules decide: trend following (20/50-day moving averages + RSI filter), long-only.
3. Risk checks run first: 10% max per position, max 5 positions, 7% stop-loss, stop buying if the account is down 3% on the day.
4. *(Optional)* Claude reviews each planned BUY against recent headlines and can **veto** it. It can never create or size a trade.
5. Orders go to the paper account. Every decision is logged (see the run's Summary tab, and the `decisions` artifact).

Paper trading is hard-coded in `trader/broker.py`. Nothing here can touch real money.

---

## Setup

### 1. Alpaca paper account
Sign up at https://alpaca.markets (a paper-only account is free). In the dashboard, switch to **Paper Trading** and generate an API key + secret.

### 2. GitHub repo
Create a **private** repo and push this folder to it:

```bash
git init && git add . && git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

### 3. Add secrets
Repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Required | What |
|---|---|---|
| `ALPACA_API_KEY` | yes | Paper key |
| `ALPACA_SECRET_KEY` | yes | Paper secret |
| `ANTHROPIC_API_KEY` | no | Enables the AI veto layer. Skip it to run rules-only. |

### 4. First run = dry run
Actions tab → **Paper trader** → **Run workflow** (leave "Dry run" ticked). Open the run and read the **Summary**: you'll see what the bot *would* do. When it looks sane, run it again with dry run unticked, or just let the schedule take over.

---

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
export ALPACA_API_KEY=...  ALPACA_SECRET_KEY=...   # paper keys
export DRY_RUN=true
python -m trader.main          # one pass
python -m trader.backtest 3    # replay the strategy on 3 years of history
pytest                         # run the tests (no network or keys needed)
```

## Tuning
Everything is an environment variable with a default in `trader/config.py` (`SYMBOLS`, `FAST_SMA`, `STOP_LOSS_PCT`, `MAX_POSITION_PCT`, ...). In GitHub Actions, add them under the `env:` block in `.github/workflows/trade.yml`.

## Project layout

```
trader/
  config.py     all settings
  strategy.py   indicators + entry/exit rules (pure functions)
  risk.py       position sizing, stop-loss, daily loss kill switch
  data.py       Alpaca market data
  broker.py     Alpaca orders (paper only)
  news.py       recent headlines
  ai_filter.py  Claude veto layer
  main.py       the run loop
  backtest.py   historical replay
tests/          unit tests + a simulated full run with a fake broker
.github/workflows/trade.yml   the schedule
```

## Know the limits
- **Scheduled GitHub Actions can start late** and aren't guaranteed to run. Fine for daily bars, wrong for anything time-sensitive.
- **Stop-losses are checked once per run**, not continuously. A stock can fall past your stop between runs.
- **Free data is IEX only** (one exchange), so volumes are low and prices can differ slightly from the consolidated market.
- **Paper trading is optimistic.** It doesn't model slippage or partial fills well.
- **Backtests flatter strategies.** Beating buy-and-hold on a few years of history proves little.
- GitHub pauses scheduled workflows in repos with no activity for 60 days (mainly a public-repo thing). Re-enable from the Actions tab if it happens.
- Going live is a different project: broker eligibility, tax, and real losses. Run paper for months first, and treat anything real as money you can afford to lose.

*This is a learning project, not financial advice.*
