"""Web and image search with graceful fallbacks — never crash the chat."""
from __future__ import annotations

import asyncio
import os
import re
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp

_SEARCH_RESULTS = 8
_IMAGE_RESULTS = 6
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _google_configured() -> bool:
    return bool(
        os.environ.get("GOOGLE_API_KEY", "").strip()
        and os.environ.get("GOOGLE_CSE_ID", "").strip()
    )


def _clean_result(url: str, title: str) -> bool:
    if not url or not title:
        return False
    if "duckduckgo.com/y.js" in url:
        return False
    return url.startswith("http")


def _unwrap_ddg_url(href: str) -> str:
    if "duckduckgo.com/l/?" in href:
        parsed = parse_qs(urlparse(href).query)
        if "uddg" in parsed:
            return unquote(parsed["uddg"][0])
    return href


def _ddg_text_sync(query: str, max_results: int) -> list[dict]:
    from duckduckgo_search import DDGS

    results: list[dict] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            results.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("href") or item.get("link") or ""),
                    "snippet": str(item.get("body") or item.get("snippet") or ""),
                }
            )
    return results


def _ddg_images_sync(query: str, max_results: int) -> list[dict]:
    from duckduckgo_search import DDGS

    images: list[dict] = []
    with DDGS() as ddgs:
        for item in ddgs.images(query, max_results=max_results):
            url = str(item.get("image") or item.get("thumbnail") or "")
            if not url:
                continue
            images.append(
                {
                    "url": url,
                    "title": str(item.get("title") or query),
                    "source": str(item.get("source") or ""),
                }
            )
    return images


async def _ddg_lite_text(
    session: aiohttp.ClientSession, query: str, max_results: int
) -> list[dict]:
    headers = {"User-Agent": _UA, "Content-Type": "application/x-www-form-urlencoded"}
    async with session.post(
        "https://lite.duckduckgo.com/lite/",
        data={"q": query},
        headers=headers,
    ) as resp:
        if resp.status >= 400:
            return []
        html = await resp.text()

    results: list[dict] = []
    link_pat = re.compile(
        r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*class=['\"]result-link['\"][^>]*>(.*?)</a>"
        r"|<a[^>]+class=['\"]result-link['\"][^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",
        re.I | re.S,
    )
    snip_pat = re.compile(
        r"class=['\"]result-snippet['\"][^>]*>(.*?)</td>",
        re.I | re.S,
    )
    chunks = re.split(r"</tr>\s*<tr>", html, flags=re.I)
    for chunk in chunks:
        link_m = link_pat.search(chunk)
        if not link_m:
            continue
        if link_m.group(1):
            url = _unwrap_ddg_url(unescape(link_m.group(1)))
            title = re.sub(r"<[^>]+>", "", link_m.group(2)).strip()
        else:
            url = _unwrap_ddg_url(unescape(link_m.group(3)))
            title = re.sub(r"<[^>]+>", "", link_m.group(4)).strip()
        snip_m = snip_pat.search(chunk)
        snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip() if snip_m else ""
        if title and url and _clean_result(url, title):
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


async def _google_text(
    session: aiohttp.ClientSession, query: str, max_results: int
) -> list[dict]:
    key = os.environ["GOOGLE_API_KEY"].strip()
    cx = os.environ["GOOGLE_CSE_ID"].strip()
    params = {
        "key": key,
        "cx": cx,
        "q": query,
        "num": min(max_results, 10),
    }
    async with session.get(
        "https://www.googleapis.com/customsearch/v1", params=params
    ) as resp:
        data = await resp.json(content_type=None)
        if resp.status >= 400:
            return []
    results: list[dict] = []
    for item in (data.get("items") or []) if isinstance(data, dict) else []:
        results.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("link") or ""),
                "snippet": str(item.get("snippet") or ""),
            }
        )
    return results


async def _google_images(
    session: aiohttp.ClientSession, query: str, max_results: int
) -> list[dict]:
    key = os.environ["GOOGLE_API_KEY"].strip()
    cx = os.environ["GOOGLE_CSE_ID"].strip()
    params = {
        "key": key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "num": min(max_results, 10),
    }
    async with session.get(
        "https://www.googleapis.com/customsearch/v1", params=params
    ) as resp:
        data = await resp.json(content_type=None)
        if resp.status >= 400:
            return []
    images: list[dict] = []
    for item in (data.get("items") or []) if isinstance(data, dict) else []:
        img_url = str(item.get("link") or "")
        if not img_url:
            continue
        images.append(
            {
                "url": img_url,
                "title": str(item.get("title") or query),
                "source": str(item.get("displayLink") or ""),
            }
        )
    return images


def wants_images(question: str) -> bool:
    lower = question.lower()
    if any(
        w in lower
        for w in (
            "image",
            "images",
            "photo",
            "photos",
            "picture",
            "pictures",
            "look like",
            "show me what",
            "what does",
        )
    ):
        return True
    if any(
        w in lower
        for w in (
            "flight",
            "flights",
            "price",
            "buy",
            "book",
            "ticket",
            "weather",
            "stock",
            "how much",
            "cost",
        )
    ):
        return False
    return False


async def search_web(
    session: aiohttp.ClientSession, query: str, *, max_results: int = _SEARCH_RESULTS
) -> tuple[list[dict], str]:
    if _google_configured():
        results = await _google_text(session, query, max_results)
        if results:
            return results, "google"

    results = await _ddg_lite_text(session, query, max_results)
    if results:
        return results, "duckduckgo"

    loop = asyncio.get_running_loop()
    try:
        results = await loop.run_in_executor(None, _ddg_text_sync, query, max_results)
        results = [r for r in results if _clean_result(r.get("url", ""), r.get("title", ""))]
        if results:
            return results, "duckduckgo"
    except Exception:
        pass

    return [], "unavailable"


async def search_images(
    session: aiohttp.ClientSession, query: str, *, max_results: int = _IMAGE_RESULTS
) -> list[dict]:
    if not wants_images(query):
        return []

    if _google_configured():
        try:
            images = await _google_images(session, query, max_results)
            if images:
                return images
        except Exception:
            pass

    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _ddg_images_sync, query, max_results)
    except Exception:
        return []


def format_search_context(results: list[dict]) -> str:
    if not results:
        return (
            "Web search returned no results (may be temporarily rate-limited). "
            "Answer from your knowledge and note if details may be outdated."
        )
    lines = ["Live web search results:"]
    for i, r in enumerate(results, 1):
        title = r.get("title") or "Untitled"
        snippet = r.get("snippet") or ""
        url = r.get("url") or ""
        lines.append(f"{i}. {title}\n   {snippet}\n   URL: {url}")
    return "\n".join(lines)


def search_provider() -> str:
    return "google" if _google_configured() else "duckduckgo"
