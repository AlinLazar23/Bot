"""
Advanced Personal Crypto Bot
==============================
Features:
- Personal portfolio tracking with P&L
- Whale tracker (large transactions)
- Daily personalized report
- Technical alerts (RSI, MACD, Golden/Death Cross)
- Multi-language (RO/EN)
- Per-user settings

Requirements:
    pip install python-telegram-bot[job-queue] requests pytz

Commands:
    /start
    /portfolio add BTC 0.5 45000  - Add coin (symbol, amount, buy price)
    /portfolio                     - View portfolio
    /portfolio remove BTC          - Remove coin
    /pnl                           - Profit/Loss report
    /watchlist add ETH             - Add to watchlist
    /watchlist                     - View watchlist prices
    /watchlist remove ETH          - Remove from watchlist
    /whales                        - Latest whale transactions
    /alert_ema BTC 200             - EMA200 daily crossover alert
    /alert_fear 20                 - Fear & Greed alert
    /alerts                        - View all personal alerts
    /report                        - Get daily report now
    /set_report 08:00              - Set daily report time
    /set_lang ro / en              - Set language
    /set_currency USD / EUR / GBP  - Set currency
    /risk                          - Portfolio risk score
    /help
"""

import os
import json
import time
import asyncio
import logging
import datetime
import requests
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
WHALE_API      = "https://api.whale-alert.io/v1/transactions"
WHALE_API_KEY  = os.environ.get("WHALE_API_KEY", "")  # Optional - whale-alert.io free key
# Salveaza in /data daca exista (Railway Volume), altfel local
DATA_DIR  = "/data" if os.path.isdir("/data") else "."
DATA_FILE = os.path.join(DATA_DIR, "user_data.json")
CHECK_INTERVAL = 60    # 1 min - check technical alerts
WHALE_INTERVAL = 600   # 10 min - check whale transactions
WHALE_MIN_USD  = 1000000  # Minimum $1M for whale alert

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── TRANSLATIONS ──────────────────────────────────────────────────────────────
T = {
    "ro": {
        "welcome": "Bun venit la CryptoPersonal Bot!\n\nBotul tau personal de crypto cu portofoliu, alerte tehnice si rapoarte zilnice.\n\nScrie /help pentru comenzi.",
        "help": (
            "Comenzi disponibile:\n\n"
            "PORTOFOLIU\n"
            "/portfolio add BTC 0.5 45000 - Adauga moneda\n"
            "/portfolio - Vezi portofoliul\n"
            "/portfolio remove BTC - Sterge moneda\n"
            "/pnl - Profit/Pierdere\n\n"
            "WATCHLIST\n"
            "/watchlist add ETH - Adauga la watchlist\n"
            "/watchlist - Vezi preturile\n"
            "/watchlist remove ETH - Sterge\n\n"
            "ALERTE\n"
            "/alert_ema BTC 200 - Alerta EMA200 daily\n"
            "/alert_fear 20 - Alerta Fear & Greed\n"
            "/alerts - Alertele tale\n\n"
            "RAPOARTE\n"
            "/report - Raport acum\n"
            "/set_report 08:00 - Ora raportului zilnic\n\n"
            "BALENE\n"
            "/whales - Ultimele tranzactii mari\n\n"
            "RISC\n"
            "/risk - Scor de risc portofoliu\n\n"
            "SETARI\n"
            "/set_lang ro / en - Limba\n"
            "/set_currency USD / EUR / RON - Moneda\n"
        ),
        "portfolio_empty": "Portofoliul tau este gol.\nFoloseste /portfolio add BTC 0.5 45000",
        "portfolio_added": "Adaugat in portofoliu: {} {} la pretul de {}",
        "portfolio_removed": "Sters din portofoliu: {}",
        "portfolio_not_found": "{} nu este in portofoliu.",
        "watchlist_empty": "Watchlist-ul tau este gol.\nFoloseste /watchlist add BTC",
        "watchlist_added": "{} adaugat in watchlist.",
        "watchlist_removed": "{} sters din watchlist.",
        "loading": "Se incarca...",
        "no_data": "Nu s-au putut obtine datele. Incearca din nou.",
        "lang_set": "Limba setata: Romana",
        "currency_set": "Moneda setata: {}",
        "report_set": "Raportul zilnic va fi trimis la {}",
        "report_title": "Raport Zilnic Personal",
        "risk_title": "Scor de Risc Portofoliu",
        "whales_title": "Tranzactii Balene (>$1M)",
        "no_whales": "Nu au fost detectate tranzactii mari recent.",
        "alert_ema_set": "Alerta EMA setata: {} EMA{} {}",
        "alert_fear_set": "Alerta Fear & Greed setata: sub {}",
        "alerts_empty": "Nu ai alerte active.",
        "pnl_empty": "Nu ai monede in portofoliu pentru P&L.",
    },
    "en": {
        "welcome": "Welcome to CryptoPersonal Bot!\n\nYour personal crypto bot with portfolio tracking, technical alerts and daily reports.\n\nType /help for commands.",
        "help": (
            "Available commands:\n\n"
            "PORTFOLIO\n"
            "/portfolio add BTC 0.5 45000 - Add coin\n"
            "/portfolio - View portfolio\n"
            "/portfolio remove BTC - Remove coin\n"
            "/pnl - Profit/Loss report\n\n"
            "WATCHLIST\n"
            "/watchlist add ETH - Add to watchlist\n"
            "/watchlist - View prices\n"
            "/watchlist remove ETH - Remove\n\n"
            "ALERTS\n"
            "/alert_ema BTC 200 - EMA200 daily alert\n"
            "/alert_fear 20 - Fear & Greed alert\n"
            "/alerts - Your alerts\n\n"
            "REPORTS\n"
            "/report - Get report now\n"
            "/set_report 08:00 - Daily report time\n\n"
            "WHALES\n"
            "/whales - Latest large transactions\n\n"
            "RISK\n"
            "/risk - Portfolio risk score\n\n"
            "SETTINGS\n"
            "/set_lang ro / en - Language\n"
            "/set_currency USD / EUR / GBP - Currency\n"
        ),
        "portfolio_empty": "Your portfolio is empty.\nUse /portfolio add BTC 0.5 45000",
        "portfolio_added": "Added to portfolio: {} {} at {}",
        "portfolio_removed": "Removed from portfolio: {}",
        "portfolio_not_found": "{} is not in your portfolio.",
        "watchlist_empty": "Your watchlist is empty.\nUse /watchlist add BTC",
        "watchlist_added": "{} added to watchlist.",
        "watchlist_removed": "{} removed from watchlist.",
        "loading": "Loading...",
        "no_data": "Could not fetch data. Try again.",
        "lang_set": "Language set: English",
        "currency_set": "Currency set: {}",
        "report_set": "Daily report will be sent at {}",
        "report_title": "Daily Personal Report",
        "risk_title": "Portfolio Risk Score",
        "whales_title": "Whale Transactions (>$1M)",
        "no_whales": "No large transactions detected recently.",
        "alert_ema_set": "EMA alert set: {} EMA{} {}",
        "alert_fear_set": "Fear & Greed alert set: below {}",
        "alerts_empty": "You have no active alerts.",
        "pnl_empty": "No coins in portfolio for P&L.",
    }
}

def t(uid, key, *args):
    lang = get_user(uid).get("lang", "ro")
    text = T.get(lang, T["ro"]).get(key, key)
    if args:
        try:
            text = text.format(*args)
        except Exception:
            pass
    return text

# ─── USER DATA ─────────────────────────────────────────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                raw = json.load(f)
            return {int(k): v for k, v in raw.items()}
        except Exception as e:
            logger.error("load_data error: " + str(e))
    return {}

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(user_data, f, indent=2)
    except Exception as e:
        logger.error("save_data error: " + str(e))

user_data = load_data()

DEFAULT_USER = {
    "lang":        "ro",
    "currency":    "USD",
    "portfolio":   {},   # {symbol: {slug, amount, buy_price}}
    "watchlist":   [],   # [symbol]
    "alerts":      {     # personal alerts
        "rsi":    {},    # {symbol: threshold}
        "fear":   None,  # threshold value
    },
    "report_time": "08:00",
    "report_enabled": True,
}

def get_user(uid):
    uid = int(uid)
    if uid not in user_data:
        user_data[uid] = dict(DEFAULT_USER)
        user_data[uid]["alerts"] = {"rsi": {}, "fear": None}
        user_data[uid]["portfolio"] = {}
        user_data[uid]["watchlist"] = []
    return user_data[uid]

# ─── CACHE ─────────────────────────────────────────────────────────────────────
_cache = {}
CACHE_TTL = 180

def cache_get(key):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None

def cache_set(key, data):
    _cache[key] = (data, time.time())

# ─── COIN SLUG MAP ─────────────────────────────────────────────────────────────
COIN_SLUG_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
    "DOGE": "dogecoin", "DOT": "polkadot", "AVAX": "avalanche-2",
    "LINK": "chainlink", "LTC": "litecoin", "UNI": "uniswap",
    "XLM": "stellar", "TRX": "tron", "SHIB": "shiba-inu",
    "MATIC": "matic-network", "NEAR": "near", "ATOM": "cosmos",
    "FTM": "fantom", "ALGO": "algorand", "XMR": "monero",
    "PEPE": "pepe", "SUI": "sui", "APT": "aptos",
    "ARB": "arbitrum", "OP": "optimism", "INJ": "injective-protocol",
    "FET": "fetch-ai", "ICP": "internet-computer",
    "FIL": "filecoin", "VET": "vechain", "SEI": "sei-network",
    "TIA": "celestia", "GRT": "the-graph", "EGLD": "elrond-erd-2",
    "HYPE": "hyperliquid", "GALA": "gala",
}

def resolve_slug(symbol):
    return COIN_SLUG_MAP.get(symbol.upper(), symbol.lower())

# ─── CURRENCY RATES ────────────────────────────────────────────────────────────
CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "RON": "RON "}

def get_currency_rate(currency):
    if currency == "USD":
        return 1.0
    cached = cache_get("rate:" + currency)
    if cached:
        return cached
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "tether", "vs_currencies": currency.lower()},
            timeout=8,
        )
        if r.status_code == 200:
            rate = r.json().get("tether", {}).get(currency.lower(), 1.0)
            cache_set("rate:" + currency, rate)
            return rate
    except Exception:
        pass
    return 1.0

def fmt_currency(value, currency="USD"):
    rate = get_currency_rate(currency)
    converted = value * rate
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    if converted >= 1:
        return symbol + "{:,.2f}".format(converted)
    return symbol + "{:.6f}".format(converted)

def fmt_price(value):
    if value is None:
        return "N/A"
    try:
        if value >= 1:
            return "$" + "{:,.2f}".format(value)
        return "$" + "{:.6f}".format(value)
    except Exception:
        return "N/A"

def fmt_pct(value):
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    emoji = "🟢" if value >= 0 else "🔴"
    return emoji + " " + sign + "{:.2f}%".format(value)

# ─── COINGECKO API ─────────────────────────────────────────────────────────────

def cg_get(endpoint, params=None, timeout=15):
    for attempt in range(3):
        if attempt > 0:
            time.sleep(8)
        try:
            r = requests.get(
                COINGECKO_BASE + endpoint,
                params=params,
                timeout=timeout,
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", 30)))
                continue
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.error("cg_get error: " + str(e))
    return None

def get_price(slug):
    cached = cache_get("price:" + slug)
    if cached:
        return cached
    data = cg_get("/simple/price", params={
        "ids": slug,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
    })
    if data and slug in data:
        result = {
            "price":      data[slug].get("usd", 0),
            "change_24h": data[slug].get("usd_24h_change", 0),
            "market_cap": data[slug].get("usd_market_cap", 0),
        }
        cache_set("price:" + slug, result)
        return result
    return None

def get_full_data(slug):
    cached = cache_get("full:" + slug)
    if cached:
        return cached
    data = cg_get("/coins/" + slug, params={
        "localization": "false", "tickers": "false",
        "community_data": "false", "developer_data": "false",
    })
    if not data:
        return None
    m = data["market_data"]
    result = {
        "symbol":     data["symbol"].upper(),
        "name":       data["name"],
        "price":      m["current_price"].get("usd", 0),
        "change_1h":  m.get("price_change_percentage_1h_in_currency", {}).get("usd") or 0,
        "change_24h": m.get("price_change_percentage_24h") or 0,
        "change_7d":  m.get("price_change_percentage_7d") or 0,
        "high_24h":   m["high_24h"].get("usd", 0),
        "low_24h":    m["low_24h"].get("usd", 0),
        "market_cap": m["market_cap"].get("usd", 0),
        "volume_24h": m["total_volume"].get("usd", 0),
        "rank":       data.get("market_cap_rank", "N/A"),
    }
    cache_set("full:" + slug, result)
    return result

def get_fear_greed(fresh=False):
    if not fresh:
        cached = cache_get("fear_greed")
        if cached:
            return cached
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                result = {
                    "value":     int(data[0]["value"]),
                    "label":     data[0]["value_classification"],
                    "yesterday": int(data[1]["value"]) if len(data) > 1 else int(data[0]["value"]),
                }
                cache_set("fear_greed", result)
                return result
    except Exception as e:
        logger.error("get_fear_greed error: " + str(e))
    return None

def get_ema(slug, period=200, timeframe="daily"):
    """
    Calculate EMA from CoinGecko price history.
    timeframe: daily only
    CoinGecko max: 365 days.
    """
    cache_key = "ema:" + slug + ":" + str(period) + ":" + timeframe
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        # Daily - maxim 365 zile
        data = cg_get("/coins/" + slug + "/market_chart",
                      params={"vs_currency": "usd", "days": "365", "interval": "daily"})
        if not data or "prices" not in data:
            return None
        prices = [p[1] for p in data["prices"]]

        if not prices:
            return None

        # Daca avem mai putine date decat perioada, folosim ce avem
        effective_period = min(period, len(prices))

        # Calculate EMA cu datele disponibile
        k = 2 / (effective_period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = price * k + ema * (1 - k)

        ema = round(ema, 2)
        cache_set(cache_key, ema)
        return ema
    except Exception as e:
        logger.error("get_ema error: " + str(e))
    return None

def get_current_price_simple(slug):
    """Get current price quickly."""
    pd = get_price(slug)
    return pd["price"] if pd else None

def get_ma(slug, period=50):
    """Calculate Moving Average from price history."""
    cached = cache_get("ma:" + str(period) + ":" + slug)
    if cached is not None:
        return cached
    try:
        data = cg_get("/coins/" + slug + "/market_chart",
                      params={"vs_currency": "usd", "days": str(period + 10), "interval": "daily"})
        if not data or "prices" not in data:
            return None
        prices = [p[1] for p in data["prices"]]
        if len(prices) < period:
            return None
        ma = sum(prices[-period:]) / period
        ma = round(ma, 2)
        cache_set("ma:" + str(period) + ":" + slug, ma)
        return ma
    except Exception as e:
        logger.error("get_ma error: " + str(e))
    return None

# ─── WHALE TRACKER ─────────────────────────────────────────────────────────────

def get_whale_transactions():
    """
    Fetch large transactions from whale-alert.io API.
    Falls back to simulated data if no API key.
    """
    cached = cache_get("whales")
    if cached is not None:
        return cached

    transactions = []

    if WHALE_API_KEY:
        try:
            r = requests.get(
                WHALE_API,
                params={
                    "api_key":   WHALE_API_KEY,
                    "min_value": WHALE_MIN_USD,
                    "limit":     10,
                    "start":     int(time.time()) - 3600,
                },
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                for tx in data.get("transactions", []):
                    transactions.append({
                        "symbol":    tx.get("symbol", "").upper(),
                        "amount":    tx.get("amount", 0),
                        "value_usd": tx.get("amount_usd", 0),
                        "from":      tx.get("from", {}).get("owner_type", "unknown"),
                        "to":        tx.get("to", {}).get("owner_type", "unknown"),
                        "hash":      tx.get("hash", "")[:16] + "...",
                    })
        except Exception as e:
            logger.error("whale API error: " + str(e))
    else:
        # Fallback: use CoinGecko volume spikes as proxy for whale activity
        try:
            r = requests.get(
                COINGECKO_BASE + "/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": "bitcoin,ethereum,binancecoin,ripple,solana",
                    "order": "volume_desc",
                    "per_page": 5,
                    "page": 1,
                    "sparkline": "false",
                },
                timeout=10,
                headers={"Accept": "application/json"},
            )
            if r.status_code == 200:
                for c in r.json():
                    vol = c.get("total_volume", 0)
                    if vol > WHALE_MIN_USD * 100:
                        transactions.append({
                            "symbol":    c["symbol"].upper(),
                            "amount":    0,
                            "value_usd": vol,
                            "from":      "market",
                            "to":        "market",
                            "note":      "High volume activity",
                        })
        except Exception as e:
            logger.error("whale fallback error: " + str(e))

    cache_set("whales", transactions)
    return transactions

# ─── PORTFOLIO HELPERS ─────────────────────────────────────────────────────────

def fmt_large(value):
    try:
        if value >= 1000000000:
            return "$" + "{:.2f}B".format(value / 1000000000)
        if value >= 1000000:
            return "$" + "{:.1f}M".format(value / 1000000)
        if value >= 1000:
            return "$" + "{:.1f}K".format(value / 1000)
        return "$" + "{:,.2f}".format(value)
    except Exception:
        return "N/A"

def calculate_portfolio(uid):
    user = get_user(uid)
    portfolio = user.get("portfolio", {})
    currency  = user.get("currency", "USD")

    if not portfolio:
        return None

    total_value    = 0
    total_invested = 0
    coins_data     = []

    for symbol, info in portfolio.items():
        slug      = info.get("slug", resolve_slug(symbol))
        amount    = float(info.get("amount", 0))
        buy_price = float(info.get("buy_price", 0))

        price_data = get_price(slug)
        if not price_data:
            continue

        current_price  = price_data["price"]
        change_24h     = price_data.get("change_24h", 0)
        current_value  = amount * current_price
        invested       = amount * buy_price
        pnl            = current_value - invested
        pnl_pct        = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0

        total_value    += current_value
        total_invested += invested

        coins_data.append({
            "symbol":        symbol,
            "amount":        amount,
            "buy_price":     buy_price,
            "current_price": current_price,
            "current_value": current_value,
            "invested":      invested,
            "pnl":           pnl,
            "pnl_pct":       pnl_pct,
            "change_24h":    change_24h,
        })

    total_pnl     = total_value - total_invested
    total_pnl_pct = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0

    return {
        "coins":           coins_data,
        "total_value":     total_value,
        "total_invested":  total_invested,
        "total_pnl":       total_pnl,
        "total_pnl_pct":   total_pnl_pct,
        "currency":        currency,
    }

def calculate_risk_score(portfolio_data):
    """
    Returns risk score 1-10 and breakdown.
    Based on: diversification, altcoin exposure, volatility.
    """
    if not portfolio_data or not portfolio_data["coins"]:
        return 5, "N/A", []

    coins  = portfolio_data["coins"]
    total  = portfolio_data["total_value"]
    notes  = []
    score  = 3  # base score (low risk)

    # 1. Concentration risk
    for c in coins:
        pct = (c["current_value"] / total * 100) if total > 0 else 0
        if pct > 70:
            score += 3
            notes.append("High concentration in " + c["symbol"] + " (" + "{:.0f}%".format(pct) + ")")
        elif pct > 50:
            score += 2
            notes.append("Significant exposure to " + c["symbol"] + " (" + "{:.0f}%".format(pct) + ")")

    # 2. Altcoin vs BTC/ETH ratio
    stable_symbols = {"BTC", "ETH"}
    stable_value   = sum(c["current_value"] for c in coins if c["symbol"] in stable_symbols)
    alt_value      = total - stable_value
    alt_pct        = (alt_value / total * 100) if total > 0 else 0

    if alt_pct > 80:
        score += 3
        notes.append("Very high altcoin exposure ({:.0f}%)".format(alt_pct))
    elif alt_pct > 60:
        score += 2
        notes.append("High altcoin exposure ({:.0f}%)".format(alt_pct))
    elif alt_pct > 40:
        score += 1
        notes.append("Moderate altcoin exposure ({:.0f}%)".format(alt_pct))
    else:
        notes.append("Good BTC/ETH diversification ({:.0f}% alts)".format(alt_pct))

    # 3. Number of coins (diversification)
    n = len(coins)
    if n == 1:
        score += 2
        notes.append("No diversification (1 coin only)")
    elif n < 3:
        score += 1
        notes.append("Low diversification (" + str(n) + " coins)")
    elif n >= 5:
        notes.append("Good diversification (" + str(n) + " coins)")

    score = max(1, min(10, score))

    if score <= 3:   label = "Low"
    elif score <= 5: label = "Moderate"
    elif score <= 7: label = "High"
    else:            label = "Very High"

    return score, label, notes

# ─── DAILY REPORT ──────────────────────────────────────────────────────────────

async def generate_report(uid):
    user     = get_user(uid)
    lang     = user.get("lang", "ro")
    currency = user.get("currency", "USD")

    lines = []
    now   = datetime.datetime.now(pytz.timezone("Europe/Bucharest"))
    lines.append("=== " + t(uid, "report_title") + " ===")
    lines.append(now.strftime("%d.%m.%Y %H:%M"))
    lines.append("")

    # Fear & Greed
    fg = get_fear_greed()
    if fg:
        trend = ""
        if fg["value"] > fg["yesterday"]:
            trend = " (sus)"
        elif fg["value"] < fg["yesterday"]:
            trend = " (jos)"
        fng_emoji = "😱" if fg["value"] <= 25 else ("😰" if fg["value"] <= 45 else ("😐" if fg["value"] <= 55 else ("😄" if fg["value"] <= 75 else "🤑")))
        lines.append("SENTIMENT PIATA" if lang == "ro" else "MARKET SENTIMENT")
        lines.append(fng_emoji + " Fear & Greed: " + str(fg["value"]) + "/100 - " + fg["label"] + trend)
        lines.append("")

    # Portfolio summary
    pf = calculate_portfolio(uid)
    if pf and pf["coins"]:
        lines.append("PORTOFOLIU" if lang == "ro" else "PORTFOLIO")
        lines.append("Valoare totala: " + fmt_currency(pf["total_value"], currency) if lang == "ro" else "Total value: " + fmt_currency(pf["total_value"], currency))
        lines.append("P&L: " + fmt_currency(pf["total_pnl"], currency) + " (" + fmt_pct(pf["total_pnl_pct"]) + ")")
        lines.append("")
        for c in pf["coins"]:
            lines.append(
                c["symbol"] + ": " + fmt_currency(c["current_value"], currency) +
                " | 24h: " + fmt_pct(c["change_24h"])
            )
        lines.append("")

    # Watchlist
    watchlist = user.get("watchlist", [])
    if watchlist:
        lines.append("WATCHLIST")
        for symbol in watchlist[:5]:
            slug = resolve_slug(symbol)
            pd   = get_price(slug)
            time.sleep(0.3)
            if pd:
                lines.append(symbol + ": " + fmt_price(pd["price"]) + " | " + fmt_pct(pd.get("change_24h", 0)))
        lines.append("")

    # Technical signals - EMA200 daily position
    signals = []
    all_coins = list(set(
        list(user.get("portfolio", {}).keys()) + user.get("watchlist", [])
    ))
    for symbol in all_coins[:5]:
        slug  = resolve_slug(symbol)
        ema   = get_ema(slug, 200, "daily")
        price = get_current_price_simple(slug)
        time.sleep(0.5)
        if ema and price:
            pos = "above" if price > ema else "below"
            emoji = "🟢" if pos == "above" else "🔴"
            signals.append(symbol + " EMA200 Daily: " + emoji + " " + pos.upper() + " (" + fmt_price(ema) + ")")

    if signals:
        lines.append("SEMNALE TEHNICE" if lang == "ro" else "TECHNICAL SIGNALS")
        for s in signals:
            lines.append(s)
        lines.append("")

    lines.append("---")
    lines.append("/portfolio | /watchlist | /risk")

    return "\n".join(lines)

# ─── COMMAND HANDLERS ──────────────────────────────────────────────────────────

async def cmd_start(update, context):
    uid = update.effective_user.id
    get_user(uid)
    save_data()
    keyboard = [
        [InlineKeyboardButton("Portfolio", callback_data="portfolio"),
         InlineKeyboardButton("Watchlist", callback_data="watchlist")],
        [InlineKeyboardButton("Report",    callback_data="report"),
         InlineKeyboardButton("Whales",    callback_data="whales")],
        [InlineKeyboardButton("Help",      callback_data="help")],
    ]
    await update.message.reply_text(
        t(uid, "welcome"),
        reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_help(update, context):
    uid = update.effective_user.id
    await update.message.reply_text(t(uid, "help"))

async def cmd_portfolio(update, context):
    uid  = update.effective_user.id
    user = get_user(uid)
    args = context.args

    # /portfolio add BTC 0.5 45000
    if args and args[0].lower() == "add":
        if len(args) < 3:
            await update.message.reply_text("Usage: /portfolio add BTC 0.5 45000")
            return
        symbol    = args[1].upper()
        try:
            amount    = float(args[2])
            buy_price = float(args[3]) if len(args) > 3 else 0
        except ValueError:
            await update.message.reply_text("Invalid number.")
            return
        slug = resolve_slug(symbol)
        user["portfolio"][symbol] = {
            "slug":      slug,
            "amount":    amount,
            "buy_price": buy_price,
        }
        save_data()
        await update.message.reply_text(t(uid, "portfolio_added", symbol, amount, fmt_price(buy_price)))
        return

    # /portfolio remove BTC
    if args and args[0].lower() == "remove":
        if len(args) < 2:
            await update.message.reply_text("Usage: /portfolio remove BTC")
            return
        symbol = args[1].upper()
        if symbol in user["portfolio"]:
            del user["portfolio"][symbol]
            save_data()
            await update.message.reply_text(t(uid, "portfolio_removed", symbol))
        else:
            await update.message.reply_text(t(uid, "portfolio_not_found", symbol))
        return

    # /portfolio - show
    if not user.get("portfolio"):
        await update.message.reply_text(t(uid, "portfolio_empty"))
        return

    await update.message.reply_text(t(uid, "loading"))
    pf = calculate_portfolio(uid)
    if not pf:
        await update.message.reply_text(t(uid, "no_data"))
        return

    currency = user.get("currency", "USD")
    lines    = ["Your Portfolio\n"]
    for c in pf["coins"]:
        pnl_str = fmt_currency(c["pnl"], currency)
        lines.append(
            c["symbol"] + " x" + str(c["amount"]) + "\n"
            "  Value:  " + fmt_currency(c["current_value"], currency) + "\n"
            "  Price:  " + fmt_price(c["current_price"]) + "\n"
            "  24h:    " + fmt_pct(c["change_24h"]) + "\n"
            "  P&L:    " + pnl_str + " (" + fmt_pct(c["pnl_pct"]) + ")\n"
        )
    lines.append("\nTOTAL VALUE: " + fmt_currency(pf["total_value"], currency))
    lines.append("TOTAL P&L:   " + fmt_currency(pf["total_pnl"], currency) + " (" + fmt_pct(pf["total_pnl_pct"]) + ")")

    keyboard = [[InlineKeyboardButton("Refresh", callback_data="portfolio")]]
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_pnl(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    if not user.get("portfolio"):
        await update.message.reply_text(t(uid, "pnl_empty"))
        return
    await update.message.reply_text(t(uid, "loading"))
    pf = calculate_portfolio(uid)
    if not pf:
        await update.message.reply_text(t(uid, "no_data"))
        return
    currency = user.get("currency", "USD")
    lines = ["P&L Report\n"]
    for c in sorted(pf["coins"], key=lambda x: x["pnl_pct"], reverse=True):
        emoji = "🟢" if c["pnl"] >= 0 else "🔴"
        lines.append(
            emoji + " " + c["symbol"] + "\n"
            "  Buy: " + fmt_price(c["buy_price"]) + " -> Now: " + fmt_price(c["current_price"]) + "\n"
            "  P&L: " + fmt_currency(c["pnl"], currency) + " (" + fmt_pct(c["pnl_pct"]) + ")\n"
        )
    total_emoji = "🟢" if pf["total_pnl"] >= 0 else "🔴"
    lines.append(total_emoji + " TOTAL: " + fmt_currency(pf["total_pnl"], currency) + " (" + fmt_pct(pf["total_pnl_pct"]) + ")")
    await update.message.reply_text("\n".join(lines))

async def cmd_watchlist(update, context):
    uid  = update.effective_user.id
    user = get_user(uid)
    args = context.args

    if args and args[0].lower() == "add":
        if len(args) < 2:
            await update.message.reply_text("Usage: /watchlist add BTC")
            return
        symbol = args[1].upper()
        if symbol not in user["watchlist"]:
            user["watchlist"].append(symbol)
            save_data()
        await update.message.reply_text(t(uid, "watchlist_added", symbol))
        return

    if args and args[0].lower() == "remove":
        if len(args) < 2:
            await update.message.reply_text("Usage: /watchlist remove BTC")
            return
        symbol = args[1].upper()
        if symbol in user["watchlist"]:
            user["watchlist"].remove(symbol)
            save_data()
        await update.message.reply_text(t(uid, "watchlist_removed", symbol))
        return

    if not user.get("watchlist"):
        await update.message.reply_text(t(uid, "watchlist_empty"))
        return

    await update.message.reply_text(t(uid, "loading"))
    currency = user.get("currency", "USD")
    lines = ["Watchlist\n"]
    for symbol in user["watchlist"]:
        slug = resolve_slug(symbol)
        pd   = get_price(slug)
        time.sleep(0.3)
        if pd:
            rsi = get_rsi(slug)
            rsi_str = " | RSI " + str(rsi) if rsi else ""
            lines.append(
                symbol + ": " + fmt_price(pd["price"]) + "\n"
                "  24h: " + fmt_pct(pd.get("change_24h", 0)) + rsi_str + "\n"
            )
        else:
            lines.append(symbol + ": N/A\n")
    keyboard = [[InlineKeyboardButton("Refresh", callback_data="watchlist")]]
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_whales(update, context):
    uid = update.effective_user.id
    await update.message.reply_text(t(uid, "loading"))
    txs = get_whale_transactions()
    if not txs:
        await update.message.reply_text(t(uid, "no_whales"))
        return
    lines = [t(uid, "whales_title") + "\n"]
    for tx in txs[:8]:
        val = fmt_large(tx["value_usd"])
        if "note" in tx:
            lines.append(tx["symbol"] + " - " + val + " - " + tx["note"])
        else:
            lines.append(
                tx["symbol"] + " - " + val + "\n"
                "  " + tx["from"] + " -> " + tx["to"]
            )
    keyboard = [[InlineKeyboardButton("Refresh", callback_data="whales")]]
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_alert_ema(update, context):
    """
    /alert_ema BTC daily 200   - alert when BTC price crosses EMA200 daily
    """
    uid  = update.effective_user.id
    user = get_user(uid)

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n"
            "/alert_ema BTC 200\n\n"
            "Vei primi alerta cand pretul incruciseaza EMA-ul pe daily."
        )
        return

    symbol    = context.args[0].upper()
    timeframe = "daily"
    try:
        period = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Period must be a number (e.g. 200)")
        return

    if period not in [20, 50, 100, 200]:
        await update.message.reply_text("Period must be: 20, 50, 100 or 200")
        return

    slug = resolve_slug(symbol)

    # Get current EMA to show user
    await update.message.reply_text("Se calculeaza EMA...")
    ema = get_ema(slug, period, timeframe)
    price = get_current_price_simple(slug)

    if ema is None:
        await update.message.reply_text("Nu s-a putut calcula EMA pentru " + symbol + ". Incearca alt simbol.")
        return

    # Store alert
    if "ema" not in user["alerts"]:
        user["alerts"]["ema"] = {}

    alert_key = symbol + ":daily:" + str(period)
    # Determine if price is above or below EMA now
    position = "above" if (price and price > ema) else "below"
    user["alerts"]["ema"][alert_key] = {
        "symbol":    symbol,
        "slug":      slug,
        "timeframe": timeframe,
        "period":    period,
        "position":  position,  # current position relative to EMA
    }
    save_data()

    price_str = fmt_price(price) if price else "N/A"
    pos_text = "DEASUPRA" if position == "above" else "SUB"
    msg = (
        "Alerta EMA setata!\n\n"
        + symbol + " EMA" + str(period) + " " + timeframe.upper() + "\n"
        + "EMA" + str(period) + ": " + fmt_price(ema) + "\n"
        + "Pret curent: " + price_str + "\n"
        + "Pozitie: " + pos_text + " EMA\n\n"
        + "Vei fi notificat cand pretul incruciseaza EMA" + str(period) + "."
    )
    await update.message.reply_text(msg)

async def cmd_alert_fear(update, context):
    uid  = update.effective_user.id
    user = get_user(uid)
    if not context.args:
        await update.message.reply_text("Usage: /alert_fear 20")
        return
    try:
        threshold = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid threshold.")
        return
    user["alerts"]["fear"] = threshold
    save_data()
    await update.message.reply_text(t(uid, "alert_fear_set", threshold))

async def cmd_alerts(update, context):
    uid  = update.effective_user.id
    user = get_user(uid)
    alerts = user.get("alerts", {})
    ema_alerts  = alerts.get("ema", {})
    fear_alert  = alerts.get("fear")

    if not ema_alerts and not fear_alert:
        await update.message.reply_text(t(uid, "alerts_empty"))
        return

    lines = ["Your Alerts\n"]
    if ema_alerts:
        lines.append("EMA Alerts:")
        for key, info in ema_alerts.items():
            lines.append(
                "  " + info["symbol"] + " EMA" + str(info["period"]) +
                " " + info["timeframe"].upper() +
                " (currently " + info["position"] + " EMA)"
            )
    if fear_alert:
        lines.append("Fear & Greed Alert: < " + str(fear_alert))
    await update.message.reply_text("\n".join(lines))

async def cmd_report(update, context):
    uid = update.effective_user.id
    await update.message.reply_text(t(uid, "loading"))
    text = await generate_report(uid)
    keyboard = [[InlineKeyboardButton("Refresh", callback_data="report")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_set_report(update, context):
    uid  = update.effective_user.id
    user = get_user(uid)
    if not context.args:
        await update.message.reply_text("Usage: /set_report 08:00")
        return
    time_str = context.args[0]
    try:
        datetime.datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text("Invalid time format. Use HH:MM (e.g. 08:00)")
        return
    user["report_time"]    = time_str
    user["report_enabled"] = True
    save_data()
    await update.message.reply_text(t(uid, "report_set", time_str))

async def cmd_set_lang(update, context):
    uid  = update.effective_user.id
    user = get_user(uid)
    if not context.args or context.args[0].lower() not in ["ro", "en"]:
        await update.message.reply_text("Usage: /set_lang ro or /set_lang en")
        return
    user["lang"] = context.args[0].lower()
    save_data()
    await update.message.reply_text(t(uid, "lang_set"))

async def cmd_set_currency(update, context):
    uid   = update.effective_user.id
    user  = get_user(uid)
    valid = ["USD", "EUR", "GBP", "RON"]
    if not context.args or context.args[0].upper() not in valid:
        await update.message.reply_text("Usage: /set_currency USD\nOptions: " + ", ".join(valid))
        return
    user["currency"] = context.args[0].upper()
    save_data()
    await update.message.reply_text(t(uid, "currency_set", user["currency"]))

async def cmd_risk(update, context):
    uid  = update.effective_user.id
    user = get_user(uid)
    if not user.get("portfolio"):
        await update.message.reply_text(t(uid, "portfolio_empty"))
        return
    await update.message.reply_text(t(uid, "loading"))
    pf    = calculate_portfolio(uid)
    score, label, notes = calculate_risk_score(pf)
    bar   = "X" * score + "." * (10 - score)
    lines = [
        t(uid, "risk_title") + "\n",
        "Score: " + str(score) + "/10 - " + label,
        "[" + bar + "]\n",
    ]
    for note in notes:
        lines.append("- " + note)
    await update.message.reply_text("\n".join(lines))

# ─── CALLBACKS ─────────────────────────────────────────────────────────────────

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    uid  = update.effective_user.id
    data = query.data

    if data == "portfolio":
        user = get_user(uid)
        if not user.get("portfolio"):
            await query.edit_message_text(t(uid, "portfolio_empty"))
            return
        pf = calculate_portfolio(uid)
        if not pf:
            await query.edit_message_text(t(uid, "no_data"))
            return
        currency = user.get("currency", "USD")
        lines = ["Your Portfolio\n"]
        for c in pf["coins"]:
            pnl_str = fmt_currency(c["pnl"], currency)
            lines.append(
                c["symbol"] + " x" + str(c["amount"]) + "\n"
                "  Value:  " + fmt_currency(c["current_value"], currency) + "\n"
                "  Price:  " + fmt_price(c["current_price"]) + "\n"
                "  24h:    " + fmt_pct(c["change_24h"]) + "\n"
                "  P&L:    " + pnl_str + " (" + fmt_pct(c["pnl_pct"]) + ")\n"
            )
        lines.append("\nTOTAL VALUE: " + fmt_currency(pf["total_value"], currency))
        lines.append("TOTAL P&L:   " + fmt_currency(pf["total_pnl"], currency) + " (" + fmt_pct(pf["total_pnl_pct"]) + ")")
        keyboard = [[InlineKeyboardButton("Refresh", callback_data="portfolio")]]
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "watchlist":
        user = get_user(uid)
        if not user.get("watchlist"):
            await query.edit_message_text(t(uid, "watchlist_empty"))
            return
        lines = ["Watchlist\n"]
        for symbol in user["watchlist"]:
            slug = resolve_slug(symbol)
            pd   = get_price(slug)
            time.sleep(0.3)
            if pd:
                lines.append(symbol + ": " + fmt_price(pd["price"]) + " | " + fmt_pct(pd.get("change_24h", 0)))
        keyboard = [[InlineKeyboardButton("Refresh", callback_data="watchlist")]]
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "report":
        text = await generate_report(uid)
        keyboard = [[InlineKeyboardButton("Refresh", callback_data="report")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "whales":
        txs = get_whale_transactions()
        if not txs:
            await query.edit_message_text(t(uid, "no_whales"))
            return
        lines = [t(uid, "whales_title") + "\n"]
        for tx in txs[:8]:
            val = fmt_large(tx["value_usd"])
            if "note" in tx:
                lines.append(tx["symbol"] + " - " + val + " - " + tx["note"])
            else:
                lines.append(tx["symbol"] + " - " + val + "\n  " + tx["from"] + " -> " + tx["to"])
        keyboard = [[InlineKeyboardButton("Refresh", callback_data="whales")]]
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "help":
        await query.edit_message_text(t(uid, "help"))

# ─── BACKGROUND JOBS ───────────────────────────────────────────────────────────

async def check_technical_alerts(context):
    """Check RSI and Fear & Greed alerts for all users."""
    fg = get_fear_greed(fresh=True)
    if fg:
        logger.info("Fear & Greed check: " + str(fg["value"]))
    for uid, user in list(user_data.items()):
        alerts = user.get("alerts", {})

        # Fear & Greed alert - trimite o singura data pana se revine peste prag
        fear_threshold = alerts.get("fear")
        if fg and fear_threshold is not None:
            alert_key = "fear_sent_" + str(uid)
            already_sent = user.get("_fear_alert_sent", False)
            if fg["value"] <= fear_threshold and not already_sent:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            "Fear & Greed Alert!\n\n"
                            "Fear & Greed: " + str(fg["value"]) + "/100 - " + fg["label"] + "\n"
                            "Your threshold: below " + str(fear_threshold)
                        )
                    )
                    user["_fear_alert_sent"] = True
                    save_data()
                except Exception as e:
                    logger.error("Fear alert error: " + str(e))
            elif fg["value"] > fear_threshold and already_sent:
                # Reseteaza cand revine peste prag
                user["_fear_alert_sent"] = False
                save_data()

        # EMA crossover alerts
        ema_alerts = alerts.get("ema", {})
        for alert_key, info in list(ema_alerts.items()):
            slug      = info["slug"]
            period    = info["period"]
            timeframe = info["timeframe"]
            symbol    = info["symbol"]
            old_pos   = info.get("position", "above")

            ema   = get_ema(slug, period, timeframe)
            price = get_current_price_simple(slug)
            time.sleep(0.5)

            if ema is None or price is None:
                continue

            new_pos = "above" if price > ema else "below"

            # Crossover detected - trimite o singura data
            already_sent = info.get("alert_sent", False)
            if new_pos != old_pos and not already_sent:
                direction = "CROSSED ABOVE" if new_pos == "above" else "CROSSED BELOW"
                emoji     = "🟢" if new_pos == "above" else "🔴"
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            emoji + " EMA Crossover Alert - " + symbol + "\n\n"
                            + symbol + " a " + direction + " EMA" + str(period) + " " + timeframe.upper() + "\n"
                            + "Pret: " + fmt_price(price) + "\n"
                            + "EMA" + str(period) + ": " + fmt_price(ema)
                        )
                    )
                    # Marcheaza ca trimis si actualizeaza pozitia
                    user["alerts"]["ema"][alert_key]["position"]   = new_pos
                    user["alerts"]["ema"][alert_key]["alert_sent"] = True
                    save_data()
                except Exception as e:
                    logger.error("EMA alert error: " + str(e))
            elif new_pos == old_pos and already_sent:
                # Reseteaza dupa ce pretul revine pe aceeasi parte
                user["alerts"]["ema"][alert_key]["alert_sent"] = False
                save_data()

async def check_daily_reports(context):
    """Send daily reports at user-configured times."""
    now_ro = datetime.datetime.now(pytz.timezone("Europe/Bucharest"))
    current_time = now_ro.strftime("%H:%M")

    for uid, user in list(user_data.items()):
        if not user.get("report_enabled", True):
            continue
        report_time = user.get("report_time", "08:00")
        if current_time == report_time:
            try:
                text = await generate_report(uid)
                keyboard = [[InlineKeyboardButton("Refresh", callback_data="report")]]
                await context.bot.send_message(
                    chat_id=uid, text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e:
                logger.error("Daily report error for " + str(uid) + ": " + str(e))

async def check_whale_alerts(context):
    """Check for new large transactions and alert users."""
    txs = get_whale_transactions()
    if not txs:
        return
    for uid, user in list(user_data.items()):
        portfolio_symbols = set(user.get("portfolio", {}).keys())
        watchlist_symbols = set(user.get("watchlist", []))
        monitored = portfolio_symbols | watchlist_symbols
        if not monitored:
            continue
        for tx in txs:
            if tx["symbol"] in monitored and tx["value_usd"] >= WHALE_MIN_USD * 5:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            "Whale Alert - " + tx["symbol"] + "\n\n"
                            "Large transaction: " + fmt_large(tx["value_usd"]) + "\n"
                            "This coin is in your portfolio/watchlist."
                        )
                    )
                except Exception as e:
                    logger.error("Whale alert error: " + str(e))

# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("portfolio",    cmd_portfolio))
    app.add_handler(CommandHandler("pnl",          cmd_pnl))
    app.add_handler(CommandHandler("watchlist",    cmd_watchlist))
    app.add_handler(CommandHandler("whales",       cmd_whales))
    app.add_handler(CommandHandler("alert_ema",    cmd_alert_ema))
    app.add_handler(CommandHandler("alert_fear",   cmd_alert_fear))
    app.add_handler(CommandHandler("alerts",       cmd_alerts))
    app.add_handler(CommandHandler("report",       cmd_report))
    app.add_handler(CommandHandler("set_report",   cmd_set_report))
    app.add_handler(CommandHandler("set_lang",     cmd_set_lang))
    app.add_handler(CommandHandler("set_currency", cmd_set_currency))
    app.add_handler(CommandHandler("risk",         cmd_risk))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Background jobs
    app.job_queue.run_repeating(check_technical_alerts, interval=CHECK_INTERVAL, first=60)
    app.job_queue.run_repeating(check_daily_reports,    interval=60,             first=30)

    print("CryptoPersonal Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
