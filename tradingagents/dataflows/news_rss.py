"""Google News RSS fetcher — zero-key news fallback for crypto tokens.

Yahoo Finance carries no news for most crypto tokens (it doesn't even list
meme coins), and the free crypto-news aggregators now require paid API keys.
Google News' public RSS search endpoint needs no key, covers anything the
open web wrote about, and matches the RSS/Atom fetcher style already used by
``reddit.py``.

Crypto symbols are queried as ``"<BASE> crypto"`` (e.g. ``SPCXB crypto``) so
results skew to the token rather than whatever else shares the letters;
non-crypto tickers pass through as-is. Items are filtered by publication
date against the requested window (look-ahead safety, same contract as
``yfinance_news``), and failures degrade to a placeholder string so an
analysis never crashes over missing flavour data.
"""

from __future__ import annotations

import html
import http.client
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .config import get_config
from .symbol_utils import crypto_base

logger = logging.getLogger(__name__)

_API = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
_UA = "tradingagents/0.3 (+https://github.com/TauricResearch/TradingAgents)"


def _news_query(ticker: str) -> str:
    """Search query for a ticker: crypto bases get a ``crypto`` qualifier."""
    base = crypto_base(ticker)
    return f"{base} crypto" if base else ticker.strip()


def _parse_pub_date(text: str | None) -> datetime | None:
    """RFC-2822 pubDate -> naive UTC datetime, or None when unparseable."""
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_news_google_rss(
    ticker: str,
    start_date: str,
    end_date: str,
    timeout: float = 10.0,
) -> str:
    """News headlines for ``ticker`` from Google News RSS, date-filtered.

    Returns a formatted plaintext block. Degrades to a clear "no news" /
    placeholder string on empty results or network failure — never raises.
    """
    query = _news_query(ticker)
    article_limit = get_config()["news_article_limit"]
    url = _API.format(query=quote_plus(query))
    req = Request(url, headers={"User-Agent": _UA})

    try:
        with urlopen(req, timeout=timeout) as resp:
            root = ET.fromstring(resp.read())
    except (OSError, http.client.HTTPException, ET.ParseError) as exc:
        logger.warning("Google News RSS fetch failed for %r: %s", query, exc)
        return f"<news unavailable: {type(exc).__name__}>"

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    # End of the end_date day, inclusive.
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    lines = []
    kept = 0
    for item in root.iter("item"):
        title = html.unescape((item.findtext("title") or "").strip())
        source = (item.findtext("source") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_dt = _parse_pub_date(item.findtext("pubDate"))

        # Look-ahead safety: keep only dated articles inside the window. An
        # undated item can't be proven to precede end_date, so it is dropped.
        if pub_dt is None or not (start_dt <= pub_dt <= end_dt):
            continue

        date_str = pub_dt.strftime("%Y-%m-%d")
        lines.append(f"### {title} (source: {source or 'unknown'}, {date_str})")
        if link:
            lines.append(f"Link: {link}")
        lines.append("")
        kept += 1
        if kept >= article_limit:
            break

    if kept == 0:
        return (
            f"No news found for {ticker} (searched Google News for {query!r}) "
            f"between {start_date} and {end_date}"
        )

    header = f"## {ticker} News (Google News, query {query!r}), from {start_date} to {end_date}:\n\n"
    return header + "\n".join(lines)
