"""OmniTool - API key 없이 동작하는 자립형 검색 라우터.

엔진 (전부 키 불필요):
  wikipedia       - ko/en Wikipedia API (공식, 안정)
  openalex        - 논문 (공식, 안정)
  gdelt           - 뉴스 DOC API (공개 엔드포인트)
  duckduckgo      - 일반 웹 (ddgs 라이브러리)
  duckduckgo_news - 뉴스 (ddgs 라이브러리)
  marginalia      - 독립엔진, API-Key: public (공유제한, 429 잦음 -> 후순위)
  you_search      - You.com keyless MCP (?profile=free, 일 100회, 키 발급 없음)

전략: 카테고리별 체인 실행 -> 1차 스코어 0.6 이상이면 채택,
      아니면 체인 내 다음 엔진 시도 -> 최종 best 선택.
search()는 절대 raise하지 않는다 (실패해도 result dict 반환).
"""
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

import requests
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

TOOL_VERSION = 7
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DB = os.path.join(BASE_DIR, "omnitool_cache.db")
CACHE_TTL = 7 * 86400
UA = "OmniTool/1.0 (local research harness)"

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept": "application/json"})

EN_STOP = frozenset(
    "the a an of and or for to in on at by with from as is are was were be been "
    "it its this that these those their there here which who whom whose what when "
    "where how why will would can could should may might must not no yes vs via "
    "per de la le les des der die das und ein eine vs et al".split()
)

NEWS_KW = ("논란", "소송", "발표", "출시", "최신", "속보", "규제", "선거", "저작권",
           "해킹", "유출", "선언", "기본법", "딥페이크", "공정성", "할루시네이션")
PAPER_HINTS = ("arxiv", "model", "transformer", "diffusion", "llm", "pre-training",
               "prompting", "retrieval", "generation", "bert", "gpt", "constitutional")
ORG_SUFFIX = ("연구원", "연구회", "협회", "재단", "대학교", "대학", "청", "위원회",
              "센터", "진흥원", "평가원", "기술원", "안전처", "기획원", "정보원")
TECH_HINTS = ("양자", "초전도", "데이터베이스", "학습", "칩", "프라이버시", "쿠버",
              "도커", "벡터", "rag", "트랜스포머", "뉴로모픽", "연합", "컨테이너",
              "아키텍처", "알고리즘", "네트워크", "반도체", "protein", "quantum")

CHAIN = {
    "기관명": ["wikipedia", "searxng", "duckduckgo", "you_search", "wikidata"],
    "기술용어": ["wikipedia", "searxng", "duckduckgo", "you_search"],
    "entity": ["wikipedia", "searxng", "duckduckgo", "you_search", "wikidata"],
    "general": ["wikipedia", "searxng", "duckduckgo", "you_search"],
    "한국어 신조어": ["searxng", "duckduckgo", "you_search", "wikipedia"],
    "논문 제목": ["openalex", "semantic_scholar", "arxiv", "crossref",
              "wikipedia", "duckduckgo", "you_search"],
    "최신 AI뉴스나 논란": ["duckduckgo_news", "wikipedia", "you_search",
                        "gdelt", "duckduckgo"],
}
# marginalia는 기본 체인에서 제외 (공유키 429 상시 + 범용품질 낮음).
# 영어 롱테일/인디웹 전용 opt-in: extra=["marginalia"] 또는 OMNI_EXTRA 환경변수.

def _with_extra(chain, extra):
    if extra is None:
        extra = [e.strip() for e in os.environ.get("OMNI_EXTRA", "").split(",")
                 if e.strip()]
    out = list(chain)
    for e in extra:
        if e in ENGINES and e not in out:
            out.append(e)
    return out


class ToolUnavailable(Exception):
    pass


# ---------------- cache ----------------
def _db():
    con = sqlite3.connect(CACHE_DB, timeout=30)
    con.execute("CREATE TABLE IF NOT EXISTS c(k TEXT PRIMARY KEY, v TEXT, ts REAL)")
    return con


def cache_get(key):
    try:
        con = _db()
        row = con.execute("SELECT v, ts FROM c WHERE k=?", (key,)).fetchone()
        con.close()
        if row and (time.time() - row[1]) < CACHE_TTL:
            return json.loads(row[0])
    except Exception:
        return None
    return None


def cache_put(key, val):
    try:
        con = _db()
        con.execute("INSERT OR REPLACE INTO c VALUES (?,?,?)",
                    (key, json.dumps(val, ensure_ascii=False), time.time()))
        con.commit()
        con.close()
    except Exception:
        pass


# ---------------- text utils ----------------
def norm(s):
    return unicodedata.normalize("NFKC", s or "").strip()


def compact(s):
    return re.sub(r"\s+", "", norm(s)).lower()


def en_tokens(s):
    toks = re.findall(r"[a-z0-9]+", (s or "").lower())
    return [t for t in toks if t not in EN_STOP and (len(t) > 1 or t.isdigit())]


def has_hangul(s):
    return any("\uac00" <= c <= "\ud7a3" for c in (s or ""))


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


# 한↔영 기술/시사 동의어 (cross-script 관련도 측정용, 오프라인 사전)
SYN = {
    "인공지능": ["ai"], "머신러닝": ["machine", "learning"],
    "딥러닝": ["deep", "learning"], "챗봇": ["chatbot"],
    "반도체": ["semiconductor", "chip"], "양자": ["quantum"],
    "초전도체": ["superconductor"], "연합학습": ["federated", "learning"],
    "차등": ["differential"], "프라이버시": ["privacy"],
    "생성형": ["generative"], "신경망": ["neural", "network"],
    "학습": ["learning"], "데이터": ["data"], "규제": ["regulation"],
    "소송": ["lawsuit"], "논란": ["controversy"], "선거": ["election"],
    "저작권": ["copyright"], "해킹": ["hacking"], "유출": ["leak"],
    "기본법": ["act", "framework", "law"], "시행": ["enforcement"],
    "면접": ["interview"], "채용": ["hiring"], "공정성": ["fairness"],
    "의료": ["medical"], "사고": ["accident"], "무단": ["unauthorized"],
    "수집": ["collection"], "오픈소스": ["open", "source"],
    "모델": ["model"], "거대언어모델": ["llm"], "할루시네이션": ["hallucination"],
    "딥페이크": ["deepfake"], "벡터": ["vector"],
    "데이터베이스": ["database"], "아키텍처": ["architecture"],
}
REV_SYN = {}
for _k, _gl in SYN.items():
    for _g in _gl:
        REV_SYN.setdefault(_g, []).append(_k)


def _variants(qc):
    """full-query compact 변형들 (동의어 치환)."""
    var = {qc}
    for k, gl in SYN.items():
        if k in qc:
            for g in gl:
                var.add(qc.replace(k, g))
    for g, kos in REV_SYN.items():
        if g in qc:
            for k in kos:
                var.add(qc.replace(g, k))
    return var


def _bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


def relevance(query, items, topk=3):
    """상위 topk 중 최적 관련도 0~1.
    4경로: 동일문자/변형(1.0) + 영문토큰 + 한국어토큰(+동의어) + 바이그램재현율(상한 0.75)."""
    q = norm(query)
    qc = compact(q)
    qt = en_tokens(q)
    for k, gl in SYN.items():
        if k in qc:
            qt = qt + gl
    ko_toks = [t for t in q.split()
               if has_hangul(t) and len(compact(t)) >= 2]
    var = _variants(qc)
    best = 0.0
    for it in (items or [])[:topk]:
        t = norm(it.get("title", "")) + " " + norm(it.get("snippet", ""))
        tc = compact(t)
        sc = 0.0
        if qc and any(v and (v in tc or tc in v) for v in var):
            sc = 1.0
        tt = en_tokens(t)
        if qt and tt:
            hit = 0
            for w in qt:
                for x in tt:
                    if w == x or (len(w) > 3 and x.startswith(w)) \
                            or (len(x) > 3 and w.startswith(x)):
                        hit += 1
                        break
            sc = max(sc, hit / len(qt))
        if ko_toks:
            hit = 0
            for tok in ko_toks:
                ctok = compact(tok)
                gl = []
                for k, g in SYN.items():
                    if k in tok:
                        gl += g
                if ctok in tc or any(g in tc for g in gl):
                    hit += 1
            sc = max(sc, hit / len(ko_toks))
        if len(qc) >= 6:
            qb, tb = _bigrams(qc), _bigrams(tc)
            if qb:
                sc = max(sc, min(len(qb & tb) / len(qb), 0.75))
        best = max(best, sc)
    return round(best, 3)


# ---------------- junk signatures ----------------
# DDG 소프트블록 시 에러 대신 반환되는 무관련 결과 패턴 (실측 기록 기반).
SPAM_DOMAINS = ("zhihu.com", "zhidao.baidu.com", "baidu.com")
HOMEPAGE_URLS = (
    "https://www.wikipedia.org/",
    "https://en.wikipedia.org/wiki/Main_Page",
    "https://ko.wikipedia.org/wiki/위키백과:대문",
    "https://support.google.com/youtubetv/?hl=en",
)


def looks_junk(query, items):
    """True면 소프트블록 junk로 보고 재시도 대상. 거짓양성 방지를 위해
    관련도 0.6 이상이면 junk가 아니다."""
    if not items or len(items) < 3:
        return False
    if relevance(query, items) >= 0.6:
        return False
    urls = [(it.get("url") or "") for it in items]
    doms = [urllib.parse.urlparse(u).netloc.lower() for u in urls]
    spam = sum(1 for d in doms if any(s in d for s in SPAM_DOMAINS))
    home = sum(1 for u in urls
               if u in HOMEPAGE_URLS or "/youtube/answer/57407" in u)
    if spam >= 2 or home >= 2:
        return True
    # 한글 쿼리인데 상위 결과에 한글도, 영문 gloss/token 매칭도 없으면 junk.
    # 단 쿼리 자체가 URL에 있으면 정상 (예: openai.com 질의).
    q = norm(query)
    if has_hangul(q) and not en_tokens(q):
        blob = " ".join(norm(it.get("title", "")) + " "
                        + norm(it.get("snippet", ""))
                        for it in items[:3])
        if not has_hangul(blob):
            qt = []
            for k, gl in SYN.items():
                if k in compact(q):
                    qt += gl
            tt = en_tokens(blob)
            overlap = any(w == x or (len(w) > 3 and x.startswith(w))
                          for w in qt for x in tt)
            if not overlap and compact(q) not in "".join(urls).lower():
                return True
    return False


# ---------------- polite http ----------------
_LAST_CALL = {}
_POLITE_LOCK = threading.Lock()


def _polite(key, min_interval):
    with _POLITE_LOCK:
        now = time.time()
        wait = min_interval - (now - _LAST_CALL.get(key, 0))
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL[key] = time.time()


def _backoff_seconds(resp, attempt):
    try:
        ra = resp.headers.get("Retry-After")
        if ra and str(ra).isdigit():
            return min(int(ra), 120)
    except Exception:
        pass
    return (5, 15, 40)[min(attempt, 2)]


def _get_json(url, params, timeout, label, min_interval=0.8, tries=4):
    for i in range(tries):
        _polite(label, min_interval)
        try:
            r = _session.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            time.sleep(3 * (i + 1))
            if i == tries - 1:
                raise ToolUnavailable(f"{label}: net {e}")
            continue
        if r.status_code == 429:
            if i == tries - 1:  # 마지막 시도면 대기 없이 바로 포기
                raise ToolUnavailable(f"{label}: 429 persistent")
            time.sleep(_backoff_seconds(r, i))
            continue
        try:
            r.raise_for_status()
        except requests.RequestException as e:
            raise ToolUnavailable(f"{label}: {e}")
        try:
            return r.json()
        except ValueError:
            time.sleep(2 * (i + 1))  # 빈 응답 등 일시 오류 -> 재시도
            if i == tries - 1:
                raise ToolUnavailable(f"{label}: bad json persistent")
            continue
    raise ToolUnavailable(f"{label}: retries exhausted")
def wiki_search(query, max_results=8):
    key = f"v{TOOL_VERSION}:wiki:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    out = []
    langs = ["ko", "en"] if has_hangul(query) else ["en", "ko"]
    for lang in langs:
        data = _get_json(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "formatversion": "2", "srlimit": max_results,
        }, 15, "wikipedia")
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            url = f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(
                title.replace(" ", "_"))
            out.append({"title": title, "url": url,
                        "snippet": strip_tags(item.get("snippet", ""))})
        if len(out) >= 2:
            break
    cache_put(key, out)
    return out


def openalex_search(query, max_results=8):
    key = f"v{TOOL_VERSION}:openalex:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    data = _get_json("https://api.openalex.org/works", {
        "search": query, "per-page": max_results,
        "select": "id,title,doi,publication_year,cited_by_count,authorships",
    }, 20, "openalex", min_interval=0.5)
    out = []
    for w in data.get("results", []):
        authors = ", ".join(
            a.get("author", {}).get("display_name", "")
            for a in w.get("authorships", [])[:3])
        out.append({
            "title": w.get("title", "") or "",
            "url": w.get("doi") or w.get("id", "") or "",
            "snippet": f"{w.get('publication_year', '?')}년 · 인용 "
                       f"{w.get('cited_by_count', 0)}회 · {authors}",
        })
    cache_put(key, out)
    return out


def gdelt_search(query, max_results=10):
    key = f"v{TOOL_VERSION}:gdelt:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    data = _get_json("https://api.gdeltproject.org/api/v2/doc/doc", {
        "query": query, "mode": "artlist", "maxrecords": max_results,
        "format": "json", "sort": "datedesc",
    }, 20, "gdelt", min_interval=0.5)
    out = [{"title": a.get("title", "") or "",
            "url": a.get("url", "") or "",
            "snippet": f"{a.get('domain', '')} · {a.get('seendate', '')}"}
           for a in data.get("articles", [])]
    cache_put(key, out)
    return out


_DDG_FAILS = [0]

RATE_HINTS = ("429", "202", "rate", "limit", "timeout", "timed out", "empty",
              "vqd", "challenge", "anomaly", "403", "blocked", "h2", "load")


def _ddg_once(kind, query, max_results):
    """단발 호출. 세션은 매번 재생성(오염된 세션 재사용 방지)."""
    _polite("ddg", 3.0)
    ddgs = DDGS()
    try:
        if kind == "text":
            return list(ddgs.text(query, max_results=max_results))
        return list(ddgs.news(query, max_results=max_results))
    finally:
        try:
            ddgs.__exit__(None, None, None)
        except Exception:
            pass


def _ddg_guarded(kind, query, max_results, norm_fn):
    """하드에러 30초후 1회 재시도 + junk 60초후 1회 재시도.
    junk(0점 또는 시그니처 매칭)는 캐시하지 않는다."""
    if _DDG_FAILS[0] >= 6:
        time.sleep(120)
        _DDG_FAILS[0] = 0
    last = None
    for attempt in (0, 1):
        try:
            out = norm_fn(_ddg_once(kind, query, max_results))
        except Exception as e:
            last = e
            if any(k in str(e).lower() for k in RATE_HINTS):
                _DDG_FAILS[0] += 1
                time.sleep(30)
                continue
            raise ToolUnavailable(f"ddg_{kind}: {e}")
        sc = relevance(query, out)
        junk = looks_junk(query, out)
        if (sc > 0 and not junk) or len(out) < 3 or attempt == 1:
            _DDG_FAILS[0] = 0
            return out, sc
        last = "junk-results-softblock"
        _DDG_FAILS[0] += 1
        time.sleep(60)
    raise ToolUnavailable(f"ddg_{kind} blocked after retry: {last}")


def ddg_text(query, max_results=8):
    key = f"v{TOOL_VERSION}:ddg:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    out, sc = _ddg_guarded("text", query, max_results, lambda raw: [
        {"title": r.get("title", "") or "", "url": r.get("href", "") or "",
         "snippet": r.get("body", "") or ""} for r in raw])
    if sc > 0 and not looks_junk(query, out):
        cache_put(key, out)
    return out


def ddg_news(query, max_results=8):
    key = f"v{TOOL_VERSION}:ddgn:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    out, sc = _ddg_guarded("news", query, max_results, lambda raw: [
        {"title": r.get("title", "") or "", "url": r.get("url", "") or "",
         "snippet": r.get("body", "") or ""} for r in raw])
    if sc > 0 and not looks_junk(query, out):
        cache_put(key, out)
    return out


def marginalia_search(query, max_results=8):
    """Marginalia 독립엔진. 키는 MARGINALIA_KEY 환경변수, 기본값은 공유키 public.
    전용키(무료 비상업)는 contact@marginalia-search.com 이메일로 발급."""
    key = f"v{TOOL_VERSION}:marg:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    api_key = os.environ.get("MARGINALIA_KEY", "public")
    try:
        r = _session.get("https://api2.marginalia-search.com/search",
                         params={"query": query, "count": max_results},
                         headers={"API-Key": api_key}, timeout=12)
        if r.status_code in (429, 503):
            raise ToolUnavailable("marginalia: shared-key rate limited")
        r.raise_for_status()
        out = [{"title": x.get("title", "") or "", "url": x.get("url", "") or "",
                "snippet": x.get("description", "") or ""}
               for x in r.json().get("results", [])]
    except ToolUnavailable:
        raise
    except Exception as e:
        raise ToolUnavailable(f"marginalia: {e}")
    cache_put(key, out)
    return out


_SEARXNG_LOCK = threading.Lock()
_SEARXNG_TRIED = False


def _searxng_autostart(base):
    """로컬 SearXNG가 꺼져 있으면 searxng/start.sh를 1회 띄우고 최대 60초 대기.
    Windows는 WSL 경유. 끄기: SEARXNG_AUTOSTART=0. 프로세스당 1회만 시도."""
    global _SEARXNG_TRIED
    if os.environ.get("SEARXNG_AUTOSTART", "1") == "0" or "127.0.0.1" not in base             and "localhost" not in base:
        return False
    with _SEARXNG_LOCK:
        if _SEARXNG_TRIED:
            return False
        _SEARXNG_TRIED = True
        if os.name == "nt":
            if not shutil.which("wsl"):
                return False
            cmd, kw = ["wsl", "-e", "bash", "searxng/start.sh"], {
                "creationflags": subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            cmd, kw = ["bash", "searxng/start.sh"], {"start_new_session": True}
        subprocess.Popen(cmd, cwd=BASE_DIR, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        for _ in range(60):  # 첫 실행은 install.sh 포함이라 오래 걸릴 수 있음
            time.sleep(1)
            try:
                if _session.get(f"{base}/healthz", timeout=1).ok:
                    return True
            except requests.RequestException:
                pass
        return False


def searxng_search(query, max_results=8):
    """로컬 SearXNG (searxng/start.sh). 꺼져 있으면 자동 실행 1회 시도."""
    key = f"v{TOOL_VERSION}:searxng:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    base = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")
    for attempt in range(2):
        try:
            r = _session.get(f"{base}/search",
                             params={"q": query, "format": "json"}, timeout=(2, 15))
            r.raise_for_status()
            data = r.json()
            break
        except requests.ConnectionError as e:
            if attempt or not _searxng_autostart(base):
                raise ToolUnavailable(f"searxng: down ({str(e)[:60]})")
        except (requests.RequestException, ValueError) as e:
            raise ToolUnavailable(f"searxng: {str(e)[:80]}")
    out = [{"title": x.get("title", ""), "url": x.get("url", ""),
            "snippet": x.get("content", "")}
           for x in data.get("results", [])[:max_results]]
    if out:  # 빈 결과(엔진 전부 차단)는 캐시 안 함
        cache_put(key, out)
    return out


def semantic_scholar_search(query, max_results=8):
    """Semantic Scholar. 키 없으면 공유 한도라 429 잦음 -> tries=2로 빨리 포기."""
    key = f"v{TOOL_VERSION}:s2:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    data = _get_json("https://api.semanticscholar.org/graph/v1/paper/search", {
        "query": query, "limit": max_results,
        "fields": "title,url,year,citationCount,authors",
    }, 15, "semantic_scholar", min_interval=1.1, tries=2)
    out = []
    for p in data.get("data") or []:
        authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
        out.append({"title": p.get("title") or "", "url": p.get("url") or "",
                    "snippet": f"{p.get('year') or '?'}년 · 인용 "
                               f"{p.get('citationCount') or 0}회 · {authors}"})
    cache_put(key, out)
    return out


_ATOM = "{http://www.w3.org/2005/Atom}"


def arxiv_search(query, max_results=8):
    """arXiv Atom API. 이용 규칙상 호출 간격 3초."""
    key = f"v{TOOL_VERSION}:arxiv:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    _polite("arxiv", 3.0)
    try:
        r = _session.get("https://export.arxiv.org/api/query", params={
            "search_query": f'all:"{query}"', "max_results": max_results},
            timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError) as e:
        raise ToolUnavailable(f"arxiv: {e}")
    out = []
    for e in root.findall(f"{_ATOM}entry"):
        out.append({"title": norm(e.findtext(f"{_ATOM}title") or ""),
                    "url": e.findtext(f"{_ATOM}id") or "",
                    "snippet": (e.findtext(f"{_ATOM}published") or "")[:4] + "년 · "
                               + norm(e.findtext(f"{_ATOM}summary") or "")[:200]})
    cache_put(key, out)
    return out


def crossref_search(query, max_results=8):
    """Crossref. CROSSREF_MAILTO 환경변수 있으면 polite pool 사용."""
    key = f"v{TOOL_VERSION}:crossref:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    params = {"query.bibliographic": query, "rows": max_results,
              "select": "title,DOI,URL,issued,is-referenced-by-count"}
    if os.environ.get("CROSSREF_MAILTO"):
        params["mailto"] = os.environ["CROSSREF_MAILTO"]
    data = _get_json("https://api.crossref.org/works", params, 20, "crossref")
    out = []
    for w in data.get("message", {}).get("items", []):
        year = ((w.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out.append({"title": " ".join(w.get("title") or []),
                    "url": w.get("URL") or "",
                    "snippet": f"{year or '?'}년 · 인용 "
                               f"{w.get('is-referenced-by-count', 0)}회"})
    cache_put(key, out)
    return out


def wikidata_search(query, max_results=8):
    """Wikidata 개체 후보 (동명이의 구분용: 라벨 + 설명)."""
    key = f"v{TOOL_VERSION}:wikidata:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    lang = "ko" if has_hangul(query) else "en"
    data = _get_json("https://www.wikidata.org/w/api.php", {
        "action": "wbsearchentities", "search": query, "language": lang,
        "uselang": lang, "limit": max_results, "format": "json",
    }, 15, "wikidata")
    out = [{"title": e.get("label", ""),
            "url": "https://www.wikidata.org/wiki/" + e.get("id", ""),
            "snippet": e.get("description", "")}
           for e in data.get("search", [])]
    cache_put(key, out)
    return out


def _parse_mcp_sse(text):
    """You.com MCP SSE에서 you-search 결과 추출 -> 표준 items."""
    for m in re.finditer(r"^data: (.*)$", text, re.M):
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue
        res = d.get("result")
        if not isinstance(res, dict):
            continue
        sc = res.get("structuredContent")
        payload = None
        if isinstance(sc, dict) and isinstance(sc.get("results"), dict):
            payload = sc["results"]
        else:
            for c in res.get("content", []) or []:
                t = (c.get("text") or "") if isinstance(c, dict) else ""
                if '"web"' in t or '"results"' in t:
                    try:
                        payload = json.loads(t).get("results")
                    except Exception:
                        payload = None
                    break
        if not payload:
            continue
        out = []
        for section in ("web", "news"):
            for x in payload.get(section, []) or []:
                if not isinstance(x, dict):
                    continue
                out.append({"title": x.get("title", "") or "",
                            "url": x.get("url", "") or "",
                            "snippet": x.get("description", "") or x.get("snippet", "") or ""})
        if out:
            return out
    return []


def you_search(query, max_results=8):
    """You.com keyless MCP (?profile=free, 일 100회). 키 발급 없음."""
    key = f"v{TOOL_VERSION}:you:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    _polite("you", 2.0)
    try:
        r = _session.post("https://api.you.com/mcp?profile=free", headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"}, json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "you-search",
                       "arguments": {"query": query, "count": max_results}}},
            timeout=60)
    except requests.RequestException as e:
        raise ToolUnavailable(f"you_search: net {e}")
    if r.status_code in (429, 402, 403):
        raise ToolUnavailable(f"you_search: http {r.status_code} (quota?)")
    try:
        r.raise_for_status()
    except requests.RequestException as e:
        raise ToolUnavailable(f"you_search: {e}")
    # text/event-stream 에는 charset이 없어 requests가 latin-1로 오디코딩함 -> utf-8 강제
    try:
        body = r.content.decode("utf-8")
    except Exception:
        body = r.text
    out = [x for x in _parse_mcp_sse(body)[:max_results]
           if norm(x.get("title"))]
    cache_put(key, out)
    return out


ENGINES = {
    "wikipedia": wiki_search,
    "openalex": openalex_search,
    "gdelt": gdelt_search,
    "duckduckgo": ddg_text,
    "duckduckgo_news": ddg_news,
    "marginalia": marginalia_search,
    "you_search": you_search,
    "searxng": searxng_search,
    "semantic_scholar": semantic_scholar_search,
    "arxiv": arxiv_search,
    "crossref": crossref_search,
    "wikidata": wikidata_search,
}


# ---------------- router ----------------
def detect_lang(query):
    q = query or ""
    if has_hangul(q):
        return "ko" if sum(c.isascii() for c in q) / max(len(q), 1) < 0.5 else "mix"
    if re.search(r"[a-zA-Z]", q):
        return "en"
    return "other"


def classify(query, curated=None):
    q = norm(query)
    ql = q.lower()
    if curated:
        for cat, words in curated.items():
            if q in words:
                return {"category": cat, "method": "rule:exact-match",
                        "reason": f"큐레이션 '{cat}' 일치"}
    if any(k in q for k in NEWS_KW):
        return {"category": "최신 AI뉴스나 논란", "method": "rule:keyword-news",
                "reason": "뉴스 키워드 포함"}
    ascii_ratio = sum(c.isascii() for c in q) / max(len(q), 1)
    if (":" in q and any(h in ql for h in PAPER_HINTS)) \
            or (len(q.split()) >= 6 and ascii_ratio > 0.6
                and any(h in ql for h in PAPER_HINTS)):
        return {"category": "논문 제목", "method": "rule:pattern-paper",
                "reason": "영어 논문형 제목 패턴(콜론+학술키워드)"}
    if q.endswith(ORG_SUFFIX):
        return {"category": "기관명", "method": "rule:pattern-org",
                "reason": "기관 접미사 패턴"}
    if any(h in q or h in ql for h in TECH_HINTS):
        return {"category": "기술용어", "method": "rule:keyword-tech",
                "reason": "기술 키워드 포함"}
    toks = q.split()
    if len(toks) >= 2 or (toks and toks[0][:1].isupper()):
        return {"category": "entity", "method": "rule:pattern-entity",
                "reason": "복합어/대문자 개체명 패턴"}
    if has_hangul(q) and len(q) <= 6:
        return {"category": "한국어 신조어", "method": "rule:fallback-short-ko",
                "reason": "짧은 한국어 (신조어 후보)"}
    return {"category": "general", "method": "rule:fallback-default",
            "reason": "기본 일반 검색"}


TOOL_LABELS = {
    "wikipedia": "Wikipedia (키 불필요)",
    "openalex": "OpenAlex 논문 (키 불필요)",
    "gdelt": "GDELT 뉴스 (키 불필요)",
    "duckduckgo": "DuckDuckGo 일반 (키 불필요)",
    "duckduckgo_news": "DuckDuckGo 뉴스 (키 불필요)",
    "marginalia": "Marginalia 독립엔진 (키 불필요)",
    "you_search": "You.com keyless (키 불필요)",
    "searxng": "SearXNG 로컬 메타검색 (키 불필요)",
    "semantic_scholar": "Semantic Scholar 논문 (키 불필요)",
    "arxiv": "arXiv 논문 (키 불필요)",
    "crossref": "Crossref 논문 (키 불필요)",
    "wikidata": "Wikidata 개체 (키 불필요)",
}


def _run_one(tool, q):
    try:
        items = [x for x in ENGINES[tool](q) if norm(x.get("title"))]
        sc = relevance(q, items)
        return tool, {"label": TOOL_LABELS.get(tool, tool),
                      "items": items[:10], "score": sc,
                      "status": "ok", "count": len(items)}
    except ToolUnavailable as e:
        return tool, {"label": TOOL_LABELS.get(tool, tool),
                      "items": [], "score": 0.0,
                      "status": "unavailable", "detail": str(e)[:120]}
    except Exception as e:
        return tool, {"label": TOOL_LABELS.get(tool, tool),
                      "items": [], "score": 0.0,
                      "status": "error", "detail": str(e)[:120]}


def multi_search(query, curated=None, extra=None):
    """체인 내 전 엔진 실행 + 점수순 정렬. 절대 raise하지 않음.
    단일 best만 보던 search()와 달리 모든 sense를 보여줘서
    동명이의(StayFree 노래 vs 앱 같은) 케이스를 사용자가 직접 고를 수 있다."""
    t0 = time.time()
    q = norm(query)
    if not q:
        return {"query": query, "error": "empty query", "tools": {}}
    try:
        route = classify(q, curated)
        cat = route["category"]
        chain = _with_extra(CHAIN.get(cat, CHAIN["general"]), extra)
        tools = {}
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(chain)) as ex:
            for tool, pack in ex.map(lambda t: _run_one(t, q), chain):
                tools[tool] = pack
        ordered = sorted(tools, key=lambda t: tools[t]["score"], reverse=True)
        return {"query": q, "category": cat, "lang": detect_lang(q),
                "method": route["method"], "reason": route["reason"],
                "chain": chain, "order": ordered, "tools": tools,
                "elapsed": round(time.time() - t0, 1)}
    except Exception as e:
        return {"query": q if isinstance(q, str) else str(query),
                "error": f"fatal: {e}", "tools": {}}


def search(query, curated=None, extra=None):
    """메인 진입점. 절대 raise하지 않음."""
    t0 = time.time()
    q = norm(query)
    if not q:
        return {"query": query, "error": "empty query", "pass": False, "items": []}
    try:
        route = classify(q, curated)
        cat = route["category"]
        chain = _with_extra(CHAIN.get(cat, CHAIN["general"]), extra)
        lang = detect_lang(q)
        tried = {}
        best = None
        for tool in chain:
            try:
                items = [x for x in ENGINES[tool](q) if norm(x.get("title"))]
            except ToolUnavailable as e:
                tried[tool] = {"status": "unavailable", "detail": str(e)[:120]}
                continue
            except Exception as e:
                tried[tool] = {"status": "error", "detail": str(e)[:120]}
                continue
            sc = relevance(q, items)
            tried[tool] = {"status": "ok", "n": len(items), "score": sc}
            cand = (sc, len(items), tool, items)
            if best is None or (sc, len(items)) > (best[0], best[1]):
                best = cand
            if sc >= 0.6 and items:
                break
        if best and best[3]:
            _, _, tool, items = best
            return {"query": q, "category": cat, "lang": lang,
                    "method": route["method"], "reason": route["reason"],
                    "chain": chain, "used_tool": tool,
                    "score": tried[tool]["score"], "count": len(items),
                    "items": items[:10], "tried": tried,
                    "elapsed": round(time.time() - t0, 1)}
        return {"query": q, "category": cat, "lang": lang,
                "method": route.get("method", "?"), "chain": chain,
                "used_tool": None, "score": 0.0, "count": 0,
                "items": [], "tried": tried,
                "elapsed": round(time.time() - t0, 1), "error": "no results"}
    except Exception as e:
        return {"query": q if isinstance(q, str) else str(query),
                "error": f"fatal: {e}", "pass": False, "items": [],
                "elapsed": round(time.time() - t0, 1)}
