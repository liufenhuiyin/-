# Layer: Adapter
# File: app/adapters/search_adapters/web_search.py
# Responsibility: 实现 SearchAdapterProtocol——调用 DuckDuckGo HTML 搜索接口，
#                 解析结果返回 SearchResults。不需要 API Key，适合离线/内网环境。
# Input:  query: str, max_results: int
# Output: SearchResults（含 list[SearchResult]）
# 禁止: 业务逻辑、编排、导入 UI 库

from __future__ import annotations

import httpx
from html.parser import HTMLParser

from app.storage.models import SearchResult, SearchResults


class DuckDuckGoSearchAdapter:
    """
    DuckDuckGo Lite HTML 搜索适配器。

    实现 SearchAdapterProtocol（结构性兼容，无需显式继承）。

    使用 DuckDuckGo Lite（lite.duckduckgo.com）的 HTML 接口，
    无需 API Key，解析结果条目（标题、URL、摘要）返回。
    """

    _SEARCH_URL = "https://lite.duckduckgo.com/lite/"
    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> SearchResults:
        """
        执行 DuckDuckGo 搜索。

        Args:
            query:       搜索查询字符串
            max_results: 最多返回条目数

        Returns:
            SearchResults — 包含解析到的 SearchResult 列表
        """
        if not query.strip():
            return SearchResults(query=query, results=[], total=0)

        try:
            print(f"[Search] 正在搜索: {repr(query)}")
            raw_html = await self._fetch_html(query)
            print(f"[Search] HTML 长度: {len(raw_html)}")
            results = _parse_ddg_results(raw_html, max_results)
            print(f"[Search] 解析到 {len(results)} 条结果")
            if results:
                for r in results[:2]:
                    print(f"  - {r.title[:50]}")
            return SearchResults(
                query=query,
                results=results,
                total=len(results),
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"[Search] 网络错误: {e}")
            return SearchResults(query=query, results=[], total=0)

    # ──────────────────────────────────────────
    # 内部 HTTP
    # ──────────────────────────────────────────

    async def _fetch_html(self, query: str) -> str:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=8.0, read=15.0, write=5.0, pool=5.0),
            follow_redirects=True,
        ) as client:
            resp = await client.post(
                self._SEARCH_URL,
                data={"q": query, "kl": "cn-zh"},
                headers={
                    "User-Agent": self._USER_AGENT,
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            resp.raise_for_status()
            return resp.text


# ──────────────────────────────────────────────
# HTML 解析（模块私有）
# ──────────────────────────────────────────────

class _DDGParser(HTMLParser):
    """
    解析 DuckDuckGo Lite HTML。

    Lite 页面结构（每条结果）：
        <a class="result-link" href="...">Title</a>
        <td class="result-snippet">Snippet text</td>
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_link = False
        self._in_snippet = False
        self._current_url = ""
        self._current_title = ""
        self._current_snippet_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        attr_dict = dict(attrs)

        if tag == "a" and "result-link" in attr_dict.get("class", ""):
            self._in_link = True
            self._current_url = attr_dict.get("href", "")
            self._current_title = ""
            return

        if tag == "td" and "result-snippet" in attr_dict.get("class", ""):
            self._in_snippet = True
            self._current_snippet_parts = []
            return

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            self._in_link = False

        if tag == "td" and self._in_snippet:
            self._in_snippet = False
            snippet = " ".join(self._current_snippet_parts).strip()
            if self._current_url and self._current_title:
                self.results.append(SearchResult(
                    title=self._current_title,
                    url=self._current_url,
                    snippet=snippet,
                    source="duckduckgo",
                ))
            self._current_snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._current_title += data.strip()
        elif self._in_snippet:
            stripped = data.strip()
            if stripped:
                self._current_snippet_parts.append(stripped)


def _parse_ddg_results(html: str, max_results: int) -> list[SearchResult]:
    """从 DuckDuckGo Lite HTML 中解析搜索结果列表。"""
    parser = _DDGParser()
    parser.feed(html)
    return parser.results[:max_results]
