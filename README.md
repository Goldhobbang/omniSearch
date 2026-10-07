# omniSearch

API키 없이 첫 검색에 최고품질을 주는 자립형 검색 라우터. 무료·키 불필요 엔진 + 규칙 분류기 + 점수 기반 폴백 체인.
CLI, Python 라이브러리, MCP 서버(Claude Code / opencode 등), 웹 UI로 사용.

## Install

```bash
pipx install "omnisearch[mcp] @ git+https://github.com/Goldhobbang/omniSearch"
```

또는 개발용:

```bash
git clone https://github.com/Goldhobbang/omniSearch && cd omniSearch
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -e ".[web,mcp]"
```

Extras: `web` (Flask UI), `mcp` (MCP server). Python 3.10+.

## Usage

### CLI

```bash
omnisearch "Attention Is All You Need"          # best-pick
omnisearch "StayFree" --multi                   # every engine, grouped, scored
omnisearch "갓생" --json
omnisearch "reciprocal rank fusion" --extra marginalia
```

### Library

```python
from omnisearch import search, multi_search
r = search("Attention Is All You Need")   # never raises
m = multi_search("StayFree")              # all senses, sorted by score
```

### MCP server

Tools: `search(query)`, `multi_search(query)` over stdio.

Claude Code:

```bash
claude mcp add omnisearch -- omnisearch-mcp
```

opencode (`opencode.json`):

```json
{ "mcp": { "omnisearch": { "type": "local", "command": ["omnisearch-mcp"] } } }
```

### Web UI

```bash
omnisearch-web        # http://127.0.0.1:5000 , smart search at /smart (OMNI_PORT to change)
```

API: `GET /api/smart-search?q=...`, `GET /api/search?q=...&type=text|images|news|videos` (raw DuckDuckGo),
`GET /api/random-word?category=...`, `GET /api/word-lists`.

## Engines (all free, no key)

| Engine | Use | Note |
|---|---|---|
| Wikipedia (ko/en) | entities, orgs, tech | official API |
| SearXNG (local) | general web + Naver | auto-installed/started on first use, see below |
| DuckDuckGo text/news (`ddgs`) | general, slang, news | anti-bot hardening included |
| You.com keyless MCP | general web | ~100/day |
| OpenAlex, Semantic Scholar, arXiv, Crossref | paper titles | S2 keyless pool often 429 |
| GDELT DOC | news | public endpoint |
| Wikidata | entity senses (label + description) | disambiguation |
| Marginalia | English indie web (opt-in) | shared key, usually 429 |

### SearXNG

Runs locally (`127.0.0.1:8888`) from `src/omnisearch/searxng/`. On the first search where it is down,
omniSearch runs `start.sh` once (Windows: through WSL), which installs SearXNG into `~/searxng`
if missing (needs `git`, `python3`, `python3-venv`; no sudo). No Docker.
Manual start: `wsl -e bash src/omnisearch/searxng/start.sh` (Windows) / `bash src/omnisearch/searxng/start.sh`.

## Configuration (env)

| Var | Default | |
|---|---|---|
| `OMNI_CACHE` | `%LOCALAPPDATA%\omnisearch\cache.db` / `~/.cache/omnisearch/cache.db` | sqlite cache, 7-day TTL |
| `OMNI_EXTRA` | — | comma list of opt-in engines (`marginalia`) |
| `SEARXNG_URL` | `http://127.0.0.1:8888` | |
| `SEARXNG_AUTOSTART` | `1` | `0` disables auto start |
| `CROSSREF_MAILTO` | — | contact email for Crossref polite pool |
| `MARGINALIA_KEY` | `public` | dedicated free key |
| `OMNI_PORT` | `5000` | web UI port |
| `OMNI_DEADLINE` | `8` | max seconds one search waits; slow engines finish in background and fill the cache |
| `OMNI_PATIENT` | `0` | `1` = wait/retry on rate limits instead of fail-fast cooldown (set by `eval/verify.py`) |

## Anti-junk design

- junk detection (zero-score + known spam signatures) with retry, sessions recreated per call
- zero-score results are never cached; cache keys are versioned (`TOOL_VERSION`)
- web server warms up DDG trust on start

## Development

```bash
python tests/test_junk.py                     # offline unit tests (CI)
python eval/spot.py                           # live spot check -> eval/spot.txt
python eval/verify.py --start 0 --count 100   # 1000-word harness, resumable
python eval/build_words.py                    # rebuild eval/words_1000.json
```

v0.1 result: 1014 independent queries (660 en-wiki random + 310 ko-wiki random + 44 curated): 1014/1014 pass, avg score 0.992.

Layout: `src/omnisearch/core.py` (router, engines, cache, scoring), `cli.py`, `mcp_server.py`,
`web.py`, `wordlists.py`, `searxng/`; `eval/` harness; `tests/` offline tests.

## License

MIT
