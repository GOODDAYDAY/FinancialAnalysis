"""
Ticker normalization utilities.

Shared by market_data, momentum, news, and any agent that needs to
resolve a bare ticker code to a yfinance-compatible or akshare-compatible
form. Chinese A-share codes need exchange suffixes for yfinance but
naked codes for akshare, so both representations are provided.
"""


def normalize_for_yfinance(ticker: str) -> list[str]:
    """
    Return a list of yfinance-compatible ticker candidates.

    yfinance requires exchange suffixes for non-US stocks. Orchestrator
    may extract bare numeric codes from Chinese queries that need
    '.SS' / '.SZ' / '.BJ' / '.HK' appended.

    Returns candidates ordered by likelihood; the caller should try
    each in order until one returns non-empty market data.

    Rules (Chinese A-share + HK):
      - Already has a dot: passthrough as-is
      - 6-digit starting with 6         -> Shanghai (.SS)
      - 6-digit starting with 0         -> Shenzhen Main Board (.SZ)
      - 6-digit starting with 3         -> Shenzhen ChiNext (.SZ)
      - 6-digit starting with 4 or 8    -> Beijing (.BJ) with .SZ fallback
      - 5-digit numeric                 -> HK (.HK)
      - 4-digit numeric                 -> HK (.HK)
      - Letters (AAPL, TSLA)            -> passthrough (US stocks)
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return []
    if "." in ticker:
        return [ticker]
    if ticker.isdigit():
        if len(ticker) == 6:
            first = ticker[0]
            if first == "6":
                return [f"{ticker}.SS"]
            if first in ("0", "3"):
                return [f"{ticker}.SZ"]
            if first in ("4", "8"):
                return [f"{ticker}.BJ", f"{ticker}.SZ"]
            return [f"{ticker}.SS", f"{ticker}.SZ"]
        if len(ticker) in (4, 5):
            return [f"{ticker}.HK"]
    return [ticker]


def to_akshare_symbol(ticker: str) -> str:
    """
    Strip exchange suffix for akshare which usually wants bare codes.
    '600519.SS' -> '600519'
    '0700.HK'   -> '0700'  (akshare HK uses naked code too for some APIs)
    'AAPL'      -> 'AAPL'
    """
    ticker = (ticker or "").strip().upper()
    if "." in ticker:
        return ticker.split(".")[0]
    return ticker


def classify_exchange(ticker: str) -> str:
    """Return one of: 'SH', 'SZ', 'BJ', 'HK', 'US', 'UNKNOWN'."""
    t = (ticker or "").strip().upper()
    if t.endswith(".SS") or t.endswith(".SH"):
        return "SH"
    if t.endswith(".SZ"):
        return "SZ"
    if t.endswith(".BJ"):
        return "BJ"
    if t.endswith(".HK"):
        return "HK"
    base = to_akshare_symbol(t)
    if base.isdigit():
        if len(base) == 6:
            first = base[0]
            return {"6": "SH", "0": "SZ", "3": "SZ", "4": "BJ", "8": "BJ"}.get(first, "UNKNOWN")
        if len(base) in (4, 5):
            return "HK"
    if base.isalpha():
        return "US"
    return "UNKNOWN"


def is_a_share(ticker: str) -> bool:
    """True for Shanghai/Shenzhen/Beijing listed stocks."""
    return classify_exchange(ticker) in ("SH", "SZ", "BJ")
