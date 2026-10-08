# omniSearch

[![ci](https://github.com/Goldhobbang/omniSearch/actions/workflows/ci.yml/badge.svg)](https://github.com/Goldhobbang/omniSearch/actions/workflows/ci.yml)
[![demo](https://img.shields.io/badge/demo-GitHub%20Pages-d1410f)](https://goldhobbang.github.io/omniSearch/)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

API키 없이 첫 검색에 최고품질을 주는 자립형 검색 라우터. 무료·키 불필요 엔진 + 규칙 분류기 + 점수 기반 폴백 체인.
CLI, Python 라이브러리, MCP 서버(Claude Code / opencode 등), 웹 UI로 사용.

**[브라우저 데모](https://goldhobbang.github.io/omniSearch/)**: 서버·설치 없이 CORS가 허용된 엔진(Wikipedia · Wikidata · OpenAlex · Crossref)만으로 같은 분류·융합을 돌려 볼 수 있다. 전체 엔진은 아래 설치 버전에서 쓴다.

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
omnisearch "venv" --fetch                       # top-1 page body excerpt (Jina, slow)
omnisearch "reciprocal rank fusion" --extra marginalia
```

### Library

```python
from omnisearch import search, multi_search
r = search("Attention Is All You Need")   # never raises
m = multi_search("StayFree")              # all senses, sorted by score
```

전문용어·동명이의(`Opus`, `venv`, `backbone`, `DataLoader`류)는 `search()`가
위키 일반의미 1개만 고를 수 있으니 `multi_search()`로 sense별 전부를 보고 고르세요.
단일 best가 필요하면 `search()`의 `used_tool`/`score`로 판단.

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
omnisearch-web        # http://127.0.0.1:5000 (OMNI_PORT to change)
```

One page, two modes: **smart routing** (route card, per-engine score/status, fused list with source badges)
and raw **DuckDuckGo** (text / images / news / videos). Light/dark theme (press `D`).

API: `GET /api/smart-search?q=...`, `GET /api/search?q=...&type=text|images|news|videos` (raw DuckDuckGo),
`GET /api/random-word?category=...`, `GET /api/word-lists`.

The UI is Vite + React + [shadcn/ui](https://ui.shadcn.com) in `frontend/`. The compiled bundle is committed
in `src/omnisearch/static/`, so installing the package needs no Node. To change the UI:

```bash
cd frontend && npm install
npm run dev           # Vite dev server (URL is printed), proxies /api to a running omnisearch-web
npm run build         # rewrites src/omnisearch/static/ -> commit it
npm run build:demo    # GitHub Pages demo (frontend/dist); deployed by .github/workflows/pages.yml
```

## Engines (all free, no key)

| Engine | Use | Note |
|---|---|---|
| Wikipedia (ko/en) | entities, orgs, tech | official API |
| Bing web RSS | general / Korean web, slang (namu.wiki etc.) | keyless, unofficial feed; market only set for Korean queries |
| Bing web RSS + `뜻` query (`bing_define`) | slang definitions | first engine for Korean slang; irrelevant answers score 0 and are skipped |
| Bing news RSS, Google News RSS | news, slang explanations | keyless, unofficial feeds; Bing links are unwrapped to the article URL |
| OpenAlex, Crossref, arXiv | paper titles | arXiv: title-field search, 3s spacing |
| Wikidata | entity senses (label + description) | disambiguation |
| DuckDuckGo text/news (`ddgs`, backend `duckduckgo`) | fallback | called only when earlier engines fail |
| Tavily AI search | fallback (LAZY) | keyless works with no key but rate-limits fast under burst pacing — key recommended; `TAVILY_API_KEY` unlocks 1000 free credits/month (basic=1) |
| You.com keyless MCP | fallback | ~100/day, called only when reached |
| GNews | news fallback (LAZY) | needs `GNEWS_API_KEY` (free 100/day, no card, 12h delay); skipped instantly without key |
| Stack Overflow | code-identifier fallback (LAZY) | no key, 300/day·IP; fires only for single-token code queries (`venv`, `constexpr`) |
| HuggingFace Hub | model-name front-run (LAZY) | no key; fires first only for digit model queries (`30B`) |
| Jina Reader | opt-in fetch (`--fetch`) | no key, 20 RPM (`JINA_API_KEY` for 500 RPM); page-body excerpt, never in the hot path |
| SearXNG (local) | opt-in extra source | `OMNI_EXTRA=searxng`; needs WSL/Linux, see below |
| GDELT DOC, Semantic Scholar | news / papers (opt-in `extra=`) | keyless shared pools, mostly 429 in tests |
| Marginalia | English indie web (opt-in) | shared key, usually 429 |

### SearXNG (optional)

Not in the default chains. Enable with `OMNI_EXTRA=searxng` (or `extra=["searxng", "searxng_news"]`).
Runs locally (`127.0.0.1:8888`) from `src/omnisearch/searxng/`. On the first search where it is down,
omniSearch runs `start.sh` once (Windows: through WSL), which installs SearXNG into `~/searxng`
if missing (needs `git`, `python3`, `python3-venv`; no sudo). No Docker.
After boot one warmup query runs so the first real search skips cold-start stragglers.
Manual start: `wsl -e bash src/omnisearch/searxng/start.sh` (Windows) / `bash src/omnisearch/searxng/start.sh`.

## Configuration (env)

| Var | Default | |
|---|---|---|
| `OMNI_CACHE` | `%LOCALAPPDATA%\omnisearch\cache.db` / `~/.cache/omnisearch/cache.db` | sqlite cache: 뉴스/웹 2일, 공식API·You 30일, 기타 7일 |
| `OMNI_EXTRA` | — | comma list of opt-in engines (`marginalia`, `searxng`, `searxng_news`) |
| `SEARXNG_URL` | `http://127.0.0.1:8888` | |
| `SEARXNG_AUTOSTART` | `1` | `0` disables auto start |
| `CROSSREF_MAILTO` | — | contact email for Crossref polite pool |
| `OPENALEX_MAILTO` | — | contact email for OpenAlex polite pool |
| `TAVILY_API_KEY` | — (keyless) | Tavily key; `TAVILY_MONTHLY` (default 1000) monthly quota |
| `GNEWS_API_KEY` | — (skip) | GNews key; `GNEWS_DAILY` (default 100) daily quota |
| `JINA_API_KEY` | — (20 RPM) | Jina Reader key for 500 RPM |
| `SE_DAILY` | `300` | StackExchange advisory daily quota |
| `SEMANTIC_SCHOLAR_KEY` | — | S2 API key: 있으면 인증 한도(1r/s)로 호출 간격 단축 |
| `MARGINALIA_KEY` | `public` | dedicated free key |
| `OMNI_PORT` | `5000` | web UI port |
| `OMNI_DEADLINE` | `4` | max seconds one search waits; slow engines finish in background and fill the cache |
| `OMNI_PATIENT` | `0` | `1` = wait/retry on rate limits instead of fail-fast cooldown (set by `eval/verify.py`) |

## Hybrid fusion

`search()` and `multi_search()` merge every engine that finished and scored >= 0.4 with a weighted
RRF (`fuse()`): rank weight = the engine's relevance, URLs are canonicalised and syndicated titles
(`- 매체명` tails) are merged. Items carry `sources`; documents several engines agree on rise to the top.
`search()` never waits for fusion: only engines already done when the winner is chosen are merged.
Engines scoring below 70% of the best engine are left out, so a weak engine cannot dilute a strong one.

## Speed and rate limits

- `search()` starts the non-fallback engines of a chain at once and returns the first result that
  passes, in priority order; slow engines finish in the background and fill the cache.
- tiered wait: official APIs 1.5s, Bing/Google feeds 2-3s, whole search `OMNI_DEADLINE` (4s);
  a tier timeout is skipped first. If nothing passed, the fallback engines (Tavily, DuckDuckGo, You.com)
  start together and are judged in completion order, not chain order.
- news feeds are accepted at lexical score 0.45 (headline wording differs from the query, so scores
  cluster at 0.4-0.6 even for on-topic articles).
- per-engine call spacing reserves a slot and sleeps outside the lock, so one engine's wait never
  blocks another; a queue longer than the deadline is skipped instead of waited on.
- 429 / soft block: the engine cools down 30s, doubling on each repeat (max 10 min), reset on success.
- quota engines (Tavily monthly, GNews daily) track usage in sqlite; exhausted quota
  skips without network, and a 402/403 marks the period spent.

## Anti-junk design

- junk detection (zero-score + known spam signatures) with retry, sessions recreated per call
- zero-score results are never cached; cache keys are versioned (`TOOL_VERSION`)
- web server warms up DDG trust on start

## Development

```bash
python tests/test_junk.py                     # offline unit tests (CI)
python tests/test_ratelimit.py
python eval/bench.py run paced 0              # latency/quality under human pacing
python eval/bench.py run burst 1              # ... under back-to-back agent pacing
python eval/bench.py report eval/bench_out/*.json
python eval/spot.py                           # live spot check -> eval/spot.txt
python eval/verify.py --start 0 --count 100   # 1000-word harness, resumable
python eval/build_words.py                    # rebuild eval/words_1000.json
```

v0.1 result: 1014 independent queries (660 en-wiki random + 310 ko-wiki random + 44 curated): 1014/1014 pass, avg score 0.992.

Layout: `src/omnisearch/core.py` (router, engines, cache, scoring), `cli.py`, `mcp_server.py`,
`web.py` (Flask API + serves `static/`), `wordlists.py`, `searxng/`; `frontend/` web UI source (shadcn/ui),
`src/omnisearch/static/` its build; `eval/` harness; `tests/` offline tests.

## License

MIT
