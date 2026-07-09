"""Apify StockTwits-scraper fallback.

StockTwits' own public API (``api.stocktwits.com``) now sits behind a
Cloudflare managed challenge that blocks every programmatic request —
verified live for arbitrary symbols, not just crypto, and confirmed to also
block RapidAPI's proxy listing (same upstream, same wall). The Apify actor
``automation-lab/stocktwits-scraper`` drives a real browser through that
challenge, so it is used as a fallback when the direct path in
:mod:`stocktwits` returns its "<stocktwits unavailable...>" placeholder.

Apify billing is pay-per-event, unlike every other vendor in this package —
callers must not invoke this on every request; :mod:`sentiment_analyst`
only reaches it after the free direct path has already failed.
"""

from __future__ import annotations

import html
import json
import logging
import os
import urllib.error
from urllib.request import Request, urlopen

from .stocktwits import _stocktwits_symbol, render_stocktwits_messages

logger = logging.getLogger(__name__)

_ACTOR = "automation-lab~stocktwits-scraper"
_API = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"


def fetch_apify_stocktwits_messages(ticker: str, limit: int = 30, timeout: float = 90.0) -> str:
    """Fetch StockTwits messages for ``ticker`` via the Apify scraper fallback.

    Mirrors :func:`stocktwits.fetch_stocktwits_messages`'s contract: always
    returns a string (a placeholder on missing config, transport failure, or
    an empty result set) so the caller never has to special-case exceptions.
    """
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        return "<stocktwits unavailable: Apify fallback not configured (set APIFY_API_TOKEN)>"

    symbol = _stocktwits_symbol(ticker)
    body = json.dumps({"mode": "symbol", "symbols": [symbol], "maxMessages": limit}).encode()
    req = Request(
        f"{_API}?token={token}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            items = json.loads(resp.read())
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("Apify StockTwits fallback failed for %s: %s", ticker, exc)
        return f"<stocktwits unavailable: {type(exc).__name__}>"

    if not items:
        return f"<no StockTwits messages found for ${ticker.upper()}>"

    normalized = [
        {
            "created": item.get("createdAt", ""),
            "user": item.get("username", "?"),
            "sentiment": item.get("sentiment"),
            # The scraped body carries HTML entities (e.g. "&#39;") from the
            # page markup; unescape so the LLM sees plain text like the
            # direct API path (which returns clean JSON strings).
            "body": html.unescape(item.get("body") or ""),
        }
        for item in items
    ]
    return render_stocktwits_messages(normalized)
