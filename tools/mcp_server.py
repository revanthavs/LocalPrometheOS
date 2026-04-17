"""Local MCP server exposing core tools (web search, RSS, HTTP fetch, file read)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
import requests
from ddgs import DDGS


def _load_allowed_dirs() -> List[Path]:
    """Read PROMETHEOS_FILESYSTEM_ALLOWED_DIRS (colon-separated paths) from env."""
    raw = os.environ.get("PROMETHEOS_FILESYSTEM_ALLOWED_DIRS", "")
    if not raw.strip():
        return []
    return [Path(p).resolve() for p in raw.split(":") if p.strip()]


_ALLOWED_DIRS: List[Path] = _load_allowed_dirs()


TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "news_search",
        "description": "Search recent news via Google News RSS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "arxiv_search",
        "description": "Search arXiv for papers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "wikipedia_search",
        "description": "Search Wikipedia articles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "reddit_search",
        "description": "Search Reddit posts (unauthenticated; rate-limited).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
                "sort": {"type": "string", "default": "new"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "github_search",
        "description": "Search GitHub repositories (unauthenticated; rate-limited).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "per_page": {"type": "integer", "default": 10},
                "sort": {"type": "string", "default": "stars"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "hn_top",
        "description": "Fetch top Hacker News stories.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "http_fetch",
        "description": "Fetch a URL via HTTP GET.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "timeout": {"type": "integer", "default": 15},
                "max_chars": {"type": "integer", "default": 5000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "rss_reader",
        "description": "Read and parse an RSS feed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["url"],
        },
    },
    {
        "name": "filesystem_read",
        "description": "Read a local file from disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_chars": {"type": "integer", "default": 5000},
            },
            "required": ["path"],
        },
    },
]


def _write_response(message_id: Any, result: Any = None, error: Dict[str, Any] | None = None) -> None:
    response: Dict[str, Any] = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def _handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    _ = params
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "serverInfo": {"name": "LocalPrometheOS MCP", "version": "0.1.0"},
    }


def _handle_tools_list() -> Dict[str, Any]:
    return {"tools": TOOL_SPECS}


def _handle_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
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


def _handle_http_fetch(args: Dict[str, Any]) -> Dict[str, Any]:
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


def _handle_news_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    if not query:
        raise ValueError("news_search requires 'query'")
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
    return {"query": query, "items": items}


def _handle_arxiv_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    if not query:
        raise ValueError("arxiv_search requires 'query'")
    max_results = int(args.get("max_results", 5))
    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query=all:{requests.utils.quote(query)}&start=0&max_results={max_results}"
    )
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_results]:
        items.append(
            {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published": entry.get("published"),
                "summary": entry.get("summary"),
            }
        )
    return {"query": query, "items": items}


def _handle_wikipedia_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    if not query:
        raise ValueError("wikipedia_search requires 'query'")
    max_results = int(args.get("max_results", 5))
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": max_results,
    }
    response = requests.get("https://en.wikipedia.org/w/api.php", params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    items = []
    for entry in data.get("query", {}).get("search", []):
        title = entry.get("title")
        pageid = entry.get("pageid")
        items.append(
            {
                "title": title,
                "pageid": pageid,
                "snippet": entry.get("snippet"),
                "url": f"https://en.wikipedia.org/?curid={pageid}",
            }
        )
    return {"query": query, "items": items}


def _handle_reddit_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    if not query:
        raise ValueError("reddit_search requires 'query'")
    limit = int(args.get("limit", 10))
    sort = args.get("sort", "new")
    headers = {"User-Agent": "LocalPrometheOS/0.1"}
    params = {"q": query, "limit": limit, "sort": sort, "restrict_sr": False}
    response = requests.get("https://www.reddit.com/search.json", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    payload = response.json()
    items = []
    for child in payload.get("data", {}).get("children", []):
        data = child.get("data", {})
        items.append(
            {
                "title": data.get("title"),
                "subreddit": data.get("subreddit"),
                "score": data.get("score"),
                "url": data.get("url"),
                "created_utc": data.get("created_utc"),
            }
        )
    return {"query": query, "items": items}


def _handle_github_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    if not query:
        raise ValueError("github_search requires 'query'")
    per_page = int(args.get("per_page", 10))
    sort = args.get("sort", "stars")
    params = {"q": query, "per_page": per_page, "sort": sort}
    headers = {"Accept": "application/vnd.github+json"}
    response = requests.get("https://api.github.com/search/repositories", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    payload = response.json()
    items = []
    for repo in payload.get("items", []):
        items.append(
            {
                "name": repo.get("full_name"),
                "url": repo.get("html_url"),
                "description": repo.get("description"),
                "stars": repo.get("stargazers_count"),
                "language": repo.get("language"),
            }
        )
    return {"query": query, "items": items}


def _handle_hn_top(args: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(args.get("limit", 10))
    ids_resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
    ids_resp.raise_for_status()
    ids = ids_resp.json()[:limit]
    items = []
    for story_id in ids:
        item_resp = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
            timeout=10,
        )
        item_resp.raise_for_status()
        data = item_resp.json()
        items.append(
            {
                "id": story_id,
                "title": data.get("title"),
                "url": data.get("url"),
                "score": data.get("score"),
                "by": data.get("by"),
            }
        )
    return {"items": items}


def _handle_rss_reader(args: Dict[str, Any]) -> Dict[str, Any]:
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


def _handle_filesystem_read(args: Dict[str, Any]) -> Dict[str, Any]:
    path_str = args.get("path")
    if not path_str:
        raise ValueError("filesystem_read requires 'path'")

    resolved = Path(path_str).resolve()

    if not _ALLOWED_DIRS:
        raise PermissionError(
            "filesystem_read is disabled: set PROMETHEOS_FILESYSTEM_ALLOWED_DIRS "
            "environment variable to enable it."
        )
    if not any(
        resolved == allowed or resolved.is_relative_to(allowed)
        for allowed in _ALLOWED_DIRS
    ):
        raise PermissionError(
            f"Access denied: '{resolved}' is outside the permitted directories."
        )

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: '{resolved}'")
    if not resolved.is_file():
        raise ValueError(f"Path is not a file: '{resolved}'")

    max_chars = int(args.get("max_chars", 5000))
    content = resolved.read_text()
    if len(content) > max_chars:
        content = content[:max_chars] + "\n...[truncated]"
    return {"path": str(resolved), "content": content}


def _handle_tool_call(params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    args = params.get("arguments") or {}
    if name == "web_search":
        return _handle_web_search(args)
    if name == "news_search":
        return _handle_news_search(args)
    if name == "arxiv_search":
        return _handle_arxiv_search(args)
    if name == "wikipedia_search":
        return _handle_wikipedia_search(args)
    if name == "reddit_search":
        return _handle_reddit_search(args)
    if name == "github_search":
        return _handle_github_search(args)
    if name == "hn_top":
        return _handle_hn_top(args)
    if name == "http_fetch":
        return _handle_http_fetch(args)
    if name == "rss_reader":
        return _handle_rss_reader(args)
    if name == "filesystem_read":
        return _handle_filesystem_read(args)
    raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            continue

        message_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        try:
            if method == "initialize":
                result = _handle_initialize(params)
            elif method == "tools/list":
                result = _handle_tools_list()
            elif method == "tools/call":
                result = _handle_tool_call(params)
            else:
                raise ValueError(f"Unknown method: {method}")
            _write_response(message_id, result=result)
        except Exception as exc:  # noqa: BLE001
            _write_response(message_id, error={"code": -32000, "message": str(exc)})


if __name__ == "__main__":
    main()
