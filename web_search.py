# Layer: Adapter
# File: app/adapters/search_adapters/web_search.py
# Responsibility: 网页搜索适配器，使用 Bing 搜索（国内可访问，无需 API Key）
# 同时保留 DuckDuckGo 作为备用

from __future__ import annotations
import re
import httpx
from html.parser import HTMLParser
from app.storage.models import SearchResult, SearchResults


class DuckDuckGoSearchAdapter:
    """
    网页搜索适配器：优先用 Bing，失败时回退到 DuckDuckGo。
    无需 API Key。
    """

    _BING_URL = "https://www.bing.com/search"
    _DDG_URL  = "https://lite.duckduckgo.com/lite/"
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    async def search(self, query: str, max_results: int = 5) -> SearchResults:
        if not query.strip():
            return SearchResults(query=query, results=[], total=0)

        # 先尝试 Bing
        try:
            print(f"[Search] Bing 搜索: {repr(query[:60])}")
            results = await self._bing_search(query, max_results)
            if results:
                print(f"[Search] Bing 返回 {len(results)} 条结果")
                return SearchResults(query=query, results=results, total=len(results))
            print("[Search] Bing 无结果，尝试 DuckDuckGo")
        except Exception as e:
            print(f"[Search] Bing 失败: {e}，尝试 DuckDuckGo")

        # 回退到 DuckDuckGo
        try:
            print(f"[Search] DuckDuckGo 搜索: {repr(query[:60])}")
            results = await self._ddg_search(query, max_results)
            print(f"[Search] DuckDuckGo 返回 {len(results)} 条结果")
            return SearchResults(query=query, results=results, total=len(results))
        except Exception as e:
            print(f"[Search] DuckDuckGo 失败: {e}")
            return SearchResults(query=query, results=[], total=0)

    # ── Bing ─────────────────────────────────

    async def _bing_search(self, query: str, max_results: int) -> list[SearchResult]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=8.0, read=15.0, write=5.0, pool=5.0),
            follow_redirects=True,
            headers={
                "User-Agent": self._UA,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            resp = await client.get(
                self._BING_URL,
                params={"q": query, "setlang": "zh-CN", "cc": "CN"},
            )
            resp.raise_for_status()
            return _parse_bing(resp.text, max_results)

    # ── DuckDuckGo ───────────────────────────

    async def _ddg_search(self, query: str, max_results: int) -> list[SearchResult]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=8.0, read=15.0, write=5.0, pool=5.0),
            follow_redirects=True,
        ) as client:
            resp = await client.post(
                self._DDG_URL,
                data={"q": query, "kl": "cn-zh"},
                headers={"User-Agent": self._UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            )
            resp.raise_for_status()
            return _parse_ddg(resp.text, max_results)


# ── Bing HTML 解析 ────────────────────────────────────────────────

def _parse_bing(html: str, max_results: int) -> list[SearchResult]:
    results: list[SearchResult] = []
    # Bing 结果块：<li class="b_algo">
    blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html, re.DOTALL)
    for block in blocks[:max_results]:
        # 标题和链接
        title_m = re.search(r'<h2[^>]*><a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not title_m:
            continue
        url = title_m.group(1)
        title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
        # 摘要
        snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
        snippet = re.sub(r'<[^>]+>', '', snippet_m.group(1)).strip() if snippet_m else ""
        if title and url and not url.startswith("javascript"):
            results.append(SearchResult(title=title, url=url, snippet=snippet, source="bing"))
    return results


# ── DuckDuckGo HTML 解析 ──────────────────────────────────────────

class _DDGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_link = False
        self._in_snippet = False
        self._current_url = ""
        self._current_title = ""
        self._snippet_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and "result-link" in d.get("class", ""):
            self._in_link = True
            self._current_url = d.get("href", "")
            self._current_title = ""
        elif tag == "td" and "result-snippet" in d.get("class", ""):
            self._in_snippet = True
            self._snippet_parts = []

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            self._in_link = False
        if tag == "td" and self._in_snippet:
            self._in_snippet = False
            if self._current_url and self._current_title:
                self.results.append(SearchResult(
                    title=self._current_title,
                    url=self._current_url,
                    snippet=" ".join(self._snippet_parts).strip(),
                    source="duckduckgo",
                ))

    def handle_data(self, data):
        if self._in_link:
            self._current_title += data.strip()
        elif self._in_snippet and data.strip():
            self._snippet_parts.append(data.strip())


def _parse_ddg(html: str, max_results: int) -> list[SearchResult]:
    p = _DDGParser()
    p.feed(html)
    return p.results[:max_results]
