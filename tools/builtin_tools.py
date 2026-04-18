"""Built-in tools and tool registry for LocalPrometheOS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
import json

import feedparser
import requests
from ddgs import DDGS

from utils.retry import http_retry


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class ToolContext:
    lm_client: Optional[Any] = None


ToolHandler = Callable[[Dict[str, Any], ToolContext], Dict[str, Any]]


class ToolRegistry:
    def __init__(self, context: Optional[ToolContext] = None) -> None:
        self._tools: Dict[str, ToolHandler] = {}
        self._specs: Dict[str, ToolSpec] = {}
        self._context = context or ToolContext()
        self._mcp_client = None
        self._mcp_specs: Dict[str, ToolSpec] = {}

    def set_mcp_client(self, mcp_client: Any) -> None:
        self._mcp_client = mcp_client

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._tools[spec.name] = handler
        self._specs[spec.name] = spec

    def refresh_mcp_tools(self) -> None:
        if not self._mcp_client:
            return
        self._mcp_specs = {spec.name: spec for spec in self._mcp_client.list_tools()}

    def list_specs(self) -> List[ToolSpec]:
        specs = list(self._specs.values())
        if self._mcp_client:
            self.refresh_mcp_tools()
            specs.extend(self._mcp_specs.values())
        return specs

    def call(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name in self._tools:
            return self._tools[name](args, self._context)
        if self._mcp_client:
            if not self._mcp_specs or name not in self._mcp_specs:
                self.refresh_mcp_tools()
            if name in self._mcp_specs:
                try:
                    return self._mcp_client.call_tool(name, args)
                except Exception:  # noqa: BLE001
                    # Fall back to built-in tool if available.
                    base_name = name.split("/")[-1]
                    if base_name in self._tools:
                        return self._tools[base_name](args, self._context)
                    raise
        # Fallback for namespaced tools that map to built-ins.
        if "/" in name:
            base_name = name.split("/")[-1]
            if base_name in self._tools:
                return self._tools[base_name](args, self._context)
        raise KeyError(f"Unknown tool: {name}")


@http_retry
def _crypto_price(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
    coin_id = args.get("coin_id", "bitcoin")
    vs_currency = args.get("vs_currency", "usd")
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": vs_currency,
        "include_24hr_change": "true",
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    price = data.get(coin_id, {}).get(vs_currency)
    change = data.get(coin_id, {}).get(f"{vs_currency}_24h_change")
    return {
        "coin_id": coin_id,
        "vs_currency": vs_currency,
        "price": price,
        "change_24h": change,
        "source": "coingecko",
    }


def _crypto_news(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
    query = args.get("query", "bitcoin")
    limit = int(args.get("limit", 5))
    url = (
        "https://news.google.com/rss/search?"
        f"q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:limit]:
        items.append(
            {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published": entry.get("published"),
            }
        )
    return {"query": query, "items": items, "source": "google_news_rss"}


def _rss_reader(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
    url = args.get("url")
    if not url:
        raise ValueError("rss_reader requires 'url'")
    limit = int(args.get("limit", 5))
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:limit]:
        items.append(
            {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published": entry.get("published"),
            }
        )
    return {"url": url, "items": items}


@http_retry
def _http_fetch(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
    url = args.get("url")
    if not url:
        raise ValueError("http_fetch requires 'url'")
    timeout = int(args.get("timeout", 15))
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    text = response.text
    max_chars = int(args.get("max_chars", 5000))
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"
    return {
        "url": url,
        "status_code": response.status_code,
        "text": text,
        "length": len(response.text),
    }


def _web_search(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
    query = args.get("query")
    if not query:
        raise ValueError("web_search requires 'query'")
    max_results = int(args.get("max_results", 5))
    results: List[Dict[str, Any]] = []
    with DDGS() as ddgs:
        for entry in ddgs.text(query, max_results=max_results, backend="html"):
            results.append(
                {
                    "title": entry.get("title"),
                    "url": entry.get("href"),
                    "snippet": entry.get("body"),
                }
            )
    return {"query": query, "results": results}


def _filesystem_read(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
    path = args.get("path")
    if not path:
        raise ValueError("filesystem_read requires 'path'")
    max_chars = int(args.get("max_chars", 5000))
    content = Path(path).read_text()
    if len(content) > max_chars:
        content = content[:max_chars] + "\n...[truncated]"
    return {"path": path, "content": content}


def _market_sentiment(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    if not context.lm_client:
        raise RuntimeError("market_sentiment requires an LMStudio client")
    items = args.get("items")
    text = args.get("text")
    if not items and not text:
        raise ValueError("market_sentiment requires 'items' or 'text'")
    if items:
        snippet = json.dumps(items, indent=2)
    else:
        snippet = str(text)
    prompt = (
        "You are a market sentiment analyst.\n"
        "Summarize sentiment as one of: Positive, Neutral, Negative.\n"
        "Return JSON with keys: sentiment, rationale.\n"
        "Content:\n"
        f"{snippet}\n"
    )
    response = context.lm_client.chat(
        [
            {"role": "system", "content": "You return strict JSON only."},
            {"role": "user", "content": prompt},
        ]
    )
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"sentiment": "Unknown", "rationale": response}


def build_registry(context: Optional[ToolContext] = None) -> ToolRegistry:
    registry = ToolRegistry(context=context)
    registry.register(
        ToolSpec(
            name="crypto_price",
            description="Fetch crypto price and 24h change from CoinGecko.",
            input_schema={
                "type": "object",
                "properties": {
                    "coin_id": {"type": "string", "default": "bitcoin"},
                    "vs_currency": {"type": "string", "default": "usd"},
                },
            },
        ),
        _crypto_price,
    )
    registry.register(
        ToolSpec(
            name="crypto_news",
            description="Fetch recent crypto news via Google News RSS.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": "bitcoin"},
                    "limit": {"type": "integer", "default": 5},
                },
            },
        ),
        _crypto_news,
    )
    registry.register(
        ToolSpec(
            name="rss_reader",
            description="Read and parse an RSS feed.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["url"],
            },
        ),
        _rss_reader,
    )
    registry.register(
        ToolSpec(
            name="http_fetch",
            description="Fetch a URL via HTTP GET.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "timeout": {"type": "integer", "default": 15},
                    "max_chars": {"type": "integer", "default": 5000},
                },
                "required": ["url"],
            },
        ),
        _http_fetch,
    )
    registry.register(
        ToolSpec(
            name="web_search",
            description="Search the web using DuckDuckGo.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        _web_search,
    )
    registry.register(
        ToolSpec(
            name="filesystem_read",
            description="Read a local file from disk.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer", "default": 5000},
                },
                "required": ["path"],
            },
        ),
        _filesystem_read,
    )
    registry.register(
        ToolSpec(
            name="market_sentiment",
            description="Analyze sentiment from news snippets using the local LLM.",
            input_schema={
                "type": "object",
                "properties": {
                    "items": {"type": "array"},
                    "text": {"type": "string"},
                },
            },
        ),
        _market_sentiment,
    )
    return registry
