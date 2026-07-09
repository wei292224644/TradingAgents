"""StockTwits public symbol-stream fetcher.

StockTwits exposes a per-symbol message stream at
``api.stocktwits.com/api/2/streams/symbol/{ticker}.json`` that requires no
API key, no OAuth, and no registration. Each message includes a
user-labeled sentiment field (``Bullish``/``Bearish``/null), the message
body, timestamp, and posting user.

The function is deliberately self-contained: short timeout, graceful
degradation on any HTTP or parse failure, and a string return type so
the calling agent gets a uniform interface regardless of whether the
network call succeeded.
"""

from __future__ import annotations

import http.client
import json
import logging
from urllib.request import Request, urlopen

from .symbol_utils import crypto_base

logger = logging.getLogger(__name__)

_API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"


def _stocktwits_symbol(ticker: str) -> str:
    """Map a crypto pair to StockTwits' ``<BASE>.X`` convention.

    StockTwits lists crypto as ``BTC.X`` (Yahoo's ``BTC-USD`` form 404s), so any
    crypto symbol resolves to its base plus ``.X``; other symbols pass through
    upper-cased.
    """
    base = crypto_base(ticker)
    return f"{base}.X" if base else ticker.strip().upper()


def fetch_stocktwits_messages(ticker: str, limit: int = 30, timeout: float = 10.0) -> str:
    """Fetch recent StockTwits messages for ``ticker`` and return them as a
    formatted plaintext block ready for prompt injection.

    Returns a placeholder string when the endpoint is unreachable, the
    symbol has no messages, or the response shape is unexpected — the
    caller never has to special-case None or exceptions.
    """
    mapped = _stocktwits_symbol(ticker)
    try:
        mapped.encode("ascii")
    except UnicodeEncodeError:
        # HTTP/1.1 request lines must be ASCII. StockTwits symbols with
        # non-ASCII bases (e.g. Chinese meme-coin names) cannot be sent.
        return f"<stocktwits unavailable: non-ASCII symbol {ticker}>"

    url = _API.format(ticker=mapped)
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
        # OSError covers URLError/TimeoutError/connection resets; HTTPException
        # covers chunked-transfer errors (IncompleteRead/BadStatusLine, #1024).
        logger.warning("StockTwits fetch failed for %s: %s", ticker, exc)
        return f"<stocktwits unavailable: {type(exc).__name__}>"

    messages = data.get("messages", []) if isinstance(data, dict) else []
    if not messages:
        return f"<no StockTwits messages found for ${ticker.upper()}>"

    normalized = [
        {
            "created": m.get("created_at", ""),
            "user": (m.get("user") or {}).get("username", "?"),
            "sentiment": (
                ((m.get("entities") or {}).get("sentiment") or {}).get("basic")
                if isinstance((m.get("entities") or {}).get("sentiment"), dict)
                else None
            ),
            "body": m.get("body") or "",
        }
        for m in messages[:limit]
    ]
    return render_stocktwits_messages(normalized)


def render_stocktwits_messages(messages: list[dict]) -> str:
    """Render normalized StockTwits-shaped messages to the standard text block.

    ``messages`` items carry ``created``, ``user``, ``sentiment``
    (``"Bullish"``/``"Bearish"``/``None``), and ``body``. Shared by the direct
    API path above and the Apify-scraper fallback (:mod:`apify_stocktwits`) so
    both produce output identical enough that the sentiment-analyst prompt's
    "read the StockTwits Bullish/Bearish ratio" guidance applies regardless of
    which one actually served the data.
    """
    lines = []
    bullish = bearish = unlabeled = 0
    for m in messages:
        body = (m.get("body") or "").replace("\n", " ").strip()
        if len(body) > 280:
            body = body[:280] + "…"

        sentiment = m.get("sentiment")
        if sentiment == "Bullish":
            bullish += 1
            tag = "Bullish"
        elif sentiment == "Bearish":
            bearish += 1
            tag = "Bearish"
        else:
            unlabeled += 1
            tag = "no-label"
        lines.append(f"[{m.get('created', '')} · @{m.get('user', '?')} · {tag}] {body}")

    total = bullish + bearish + unlabeled
    bull_pct = round(100 * bullish / total) if total else 0
    bear_pct = round(100 * bearish / total) if total else 0
    summary = (
        f"Bullish: {bullish} ({bull_pct}%) · "
        f"Bearish: {bearish} ({bear_pct}%) · "
        f"Unlabeled: {unlabeled} · "
        f"Total: {total} most-recent messages"
    )
    return summary + "\n\n" + "\n".join(lines)
