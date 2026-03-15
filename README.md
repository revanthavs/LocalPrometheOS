# LocalPrometheOS

**LocalPrometheOS — Autonomous AI monitoring powered by local models.**

LocalPrometheOS is a local-first autonomous AI task monitoring platform powered by local LLMs via LM Studio. It schedules monitoring tasks (crypto, research, jobs, logs, sentiment) and uses multi-agent planning and tool execution to generate summaries and recommendations.

## Features (v1)
- Local-first architecture with LM Studio OpenAI-compatible API
- Multi-agent workflow (planner, worker, evaluator)
- Cron scheduling with APScheduler
- MCP tool support (stdio + HTTP)
- Built-in tools for crypto price, news, RSS, HTTP fetch, filesystem read
- SQLite persistence for tasks, runs, results, and logs
- Typer CLI
- Streamlit dashboard

## Prerequisites
- Python 3.10+
- LM Studio running locally

Recommended models:
- qwen2.5
- qwen3
- llama3
- deepseek

## Install
```bash
pip install -r requirements.txt
```

## Configure
Edit `LocalPrometheOS/config/config.yaml` to select the model name and MCP servers.

LM Studio should be running at:
```
http://localhost:1234/v1
```

## Run CLI
```bash
python main.py list-tasks
python main.py run "Bitcoin Monitor"
python main.py start

# Or use the helper script:
./prometheos list-tasks
./prometheos run "Bitcoin Monitor"
./prometheos start
```

## Start UI
```bash
streamlit run ui/streamlit_app.py
```

## Task Definitions
Tasks live in `tasks/` as individual YAML files.

Example:
```yaml
name: "Bitcoin Monitor"
schedule: "0 15 * * *"
goal: "Determine whether to buy, hold, or pause Bitcoin purchases."
tools:
  - "crypto_price"
  - "crypto_news"
  - "market_sentiment"
inputs:
  coin_id: "bitcoin"
  vs_currency: "usd"
  query: "bitcoin"
  limit: 5
enabled: true
```

## Example Output
```
BTC Price: $71,203
24h change: -1.8%

Sentiment: Neutral

Recommendation: HOLD
Reason: Market consolidation.
```

## Project Structure
```
local-prometheos/
  agents/
  scheduler/
  orchestrator/
  tools/
  models/
  tasks/
  database/
  ui/
  config/
  examples/
  main.py
  requirements.txt
  README.md
```

## Notes
- Built-in tools use public endpoints (CoinGecko, Google News RSS, DuckDuckGo) without paid APIs.
- A default local MCP server is included at `tools/mcp_server.py` with core tools:
  - `web_search`
  - `news_search`
  - `arxiv_search`
  - `wikipedia_search`
  - `reddit_search` (rate-limited)
  - `github_search` (rate-limited)
  - `hn_top`
  - `http_fetch`
  - `rss_reader`
  - `filesystem_read`
- The default MCP server is enabled in `config/config.yaml`. Remove it if you prefer no MCP tools.

## License
MIT
