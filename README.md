# omniSearch

API키 없이 첫 검색에 최고품질을 주는 자립형 검색 라우터. 키워드 불필요 엔진 7종 + 규칙 분류기 + 점수 기반 폴백 체인.

## Engines (all keyless)

| Engine | Use | Note |
|---|---|---|
| Wikipedia (ko/en) | entities, orgs, tech | official API |
| OpenAlex | paper titles | official API |
| GDELT DOC | news | public endpoint |
| DuckDuckGo text/news (`ddgs`) | general, slang, news | anti-bot hardening included |
| Marginalia (`public` key) | English long-tail / indie web only (opt-in) | shared limit, usually 429 |
| You.com keyless MCP (`?profile=free`) | general web | ~100/day, no signup |
| SearXNG (local; WSL on Windows) | general web + Naver | auto-installed and auto-started on first use (`SEARXNG_AUTOSTART=0` to disable) |
| Semantic Scholar | paper titles | keyless shared limit, frequent 429 |
| arXiv | paper titles | Atom API, 3s interval |
| Crossref | paper titles | set `CROSSREF_MAILTO` env for polite pool |
| Wikidata | entity senses (label + description) | disambiguation |

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

- General search: http://127.0.0.1:5000
- Smart routing search: http://127.0.0.1:5000/smart

Library use:

```python
from omnitool import search, multi_search
r = search("Attention Is All You Need")   # best-pick, never raises
m = multi_search("StayFree")              # every engine, scored, sense-separated
m2 = multi_search("reciprocal rank fusion", extra=["marginalia"])  # opt-in niche engine
```

Marginalia: excluded from default chains (shared `public` key is rate-limited;
quality is English-indie-only). Enable globally with `OMNI_EXTRA=marginalia`.
Dedicated free key via `MARGINALIA_KEY` env.

## Tests

```powershell
python tests/test_junk.py   # offline unit tests
python spot.py              # live spot check -> spot.txt
python verify.py --start 0 --count 100   # 1000-word harness
```

## API

- `GET /api/search?q=...&type=text|images|news|videos` — raw DuckDuckGo
- `GET /api/smart-search?q=...` — `{route, results_by_tool, scores, order, elapsed}`
- `GET /api/random-word?category=...` / `GET /api/word-lists`

`SMART_BACKEND` in `app.py`: `"multi"` (default) or `"legacy"` (single-engine fallback, instant rollback).

## Anti-junk design

- junk detection (zero-score + known spam signatures) with retry, sessions recreated per call
- zero-score results are never cached; caches are version-keyed (`TOOL_VERSION`)
- server warms up DDG trust on start (`_warmup`)

## Verification

1014 independent queries (660 en-wiki random + 310 ko-wiki random + 44 curated orgs/tech/slang/papers/news): **1014/1014 pass**, avg score 0.992. Harness: `python verify.py --start 0 --count 100` (resumable, progress in `verify_progress.json`). Word list: `words_1000.json`, builder: `build_words.py`.

## Files

- `omnitool.py` — router + engines + cache + scoring
- `smart_search.py` — legacy single-engine backend + curated word lists
- `app.py` — Flask UI + API
- `verify.py` / `build_words.py` — test harness / corpus builder

## License

MIT
