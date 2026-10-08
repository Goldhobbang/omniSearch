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
from concurrent.futures import ThreadPoolExecutor, wait
from concurrent.futures import TimeoutError as FutureTimeout

import requests
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

TOOL_VERSION = 8
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DB = os.environ.get("OMNI_CACHE") or os.path.join(
    os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    or os.path.expanduser("~/.cache"), "omnisearch", "cache.db")
os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)
CACHE_TTL = 7 * 86400
CACHE_TTL_SHORT = 2 * 86400   # 자주 변하는 뉴스/웹메타: searxng, ddg, gdelt
CACHE_TTL_LONG = 30 * 86400   # 잘 안 변하는 공식API + 쿼터제 you (재호출·한도 절약)


def _ttl_for(key):
    """캐시키 prefix별 TTL. v{N}:{prefix}:... 형식에서 prefix 판별."""
    try:
        prefix = (key or "").split(":")[1]
    except Exception:
        return CACHE_TTL
    if prefix in ("searxng", "ddg", "ddgn", "gdelt"):
        return CACHE_TTL_SHORT
    if prefix in ("wiki", "openalex", "crossref", "wikidata", "arxiv",
                  "you", "s2"):
        return CACHE_TTL_LONG
    return CACHE_TTL
UA = "omniSearch/0.2 (+https://github.com/Goldhobbang/omniSearch)"

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
    "기관명": ["wikipedia", "searxng", "wikidata", "duckduckgo", "you_search"],
    "기술용어": ["wikipedia", "searxng", "duckduckgo", "you_search"],
    "entity": ["wikipedia", "searxng", "wikidata", "duckduckgo", "you_search"],
    "general": ["wikipedia", "searxng", "duckduckgo", "you_search"],
    "한국어 신조어": ["searxng", "wikipedia", "duckduckgo", "you_search"],
    "논문 제목": ["openalex", "crossref", "arxiv", "wikipedia", "searxng",
              "duckduckgo", "you_search"],
    "최신 AI뉴스나 논란": ["searxng_news", "wikipedia", "duckduckgo_news",
                        "you_search"],
}
# gdelt / semantic_scholar: 키 없는 공유 한도라 실측 429 대부분 -> extra= 로만 사용.
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
        if row and (time.time() - row[1]) < _ttl_for(key):
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


def _score_one(qc, qt, ko_toks, var, text, title_side):
    """단일 텍스트(제목 또는 스니펫)에 대한 관련도 0~1.
    제목과 스니펫을 분리 평가한다. 스니펫(title_side=False)은 상한 0.5:
    본문 언급만으로는 1.0을 주지 않는다 (예: venv 질의에 스니펫 "O Venvs"
    가 포함된 메탈 앨범 문서가 1.0을 받는 오답 방지)."""
    tc = compact(text)
    sc = 0.0
    if qc and any(v and (v in tc or tc in v) for v in var):
        sc = 1.0
    tt = en_tokens(text)
    if qt and tt:
        hit = 0
        for w in qt:
            for x in tt:
                # 어간 매칭은 길이 차이가 2자 이내일 때만 (dataloader->data 같은
                # 과도한 축약 매칭 방지, model->models 같은 복수형은 허용).
                if w == x or (len(w) > 3 and len(w) >= len(x) - 2 and x.startswith(w)) \
                        or (len(x) > 3 and len(x) >= len(w) - 2 and w.startswith(x)):
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
    if not title_side:
        sc = min(sc, 0.5)
    return round(sc, 3)


def relevance(query, items, topk=3):
    """상위 topk 중 최적 관련도 0~1.
    4경로: 동일문자/변형(제목 매칭시 1.0) + 영문토큰 + 한국어토큰(+동의어)
    + 바이그램재현율(상한 0.75). 스니펫만 매칭되면 0.5 상한."""
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
        st = _score_one(qc, qt, ko_toks, var, norm(it.get("title", "")), True)
        ss = _score_one(qc, qt, ko_toks, var, norm(it.get("snippet", "")), False)
        best = max(best, st, ss)
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

# 기본은 fail-fast: 429/차단이면 대기하지 않고 엔진을 COOLDOWN초 쉬게 한 뒤 즉시 포기.
# 대량 배치(eval/verify.py)는 OMNI_PATIENT=1 로 기존 대기·재시도 동작 사용.
PATIENT = os.environ.get("OMNI_PATIENT") == "1"
DEADLINE = float(os.environ.get("OMNI_DEADLINE", "600" if PATIENT else "4"))  # 검색 1회 전체 대기 상한(초)
COOLDOWN = 30
_COOL_UNTIL = {}


_STRIKES = {}


def _cool(label, seconds=COOLDOWN):
    """연속 차단마다 쉬는 시간 2배 (최대 10분). 성공하면 _ok()가 초기화."""
    n = _STRIKES.get(label, 0)
    _STRIKES[label] = n + 1
    _COOL_UNTIL[label] = time.time() + min(600, seconds * 2 ** n)


def _ok(label):
    _STRIKES.pop(label, None)


def _check_cool(label):
    if time.time() < _COOL_UNTIL.get(label, 0):
        raise ToolUnavailable(f"{label}: cooling down")


def _polite(key, min_interval):
    """엔진별 호출 간격. 잠금 안에서는 슬롯만 예약하고 대기는 밖에서 -> 엔진끼리 안 막힘.
    fail-fast 모드에서 대기열이 DEADLINE보다 길면 기다리지 않고 건너뜀."""
    with _POLITE_LOCK:
        now = time.time()
        slot = max(now, _LAST_CALL.get(key, 0) + min_interval)
        wait = slot - now
        if not PATIENT and wait > DEADLINE:
            raise ToolUnavailable(f"{key}: busy (queue {wait:.1f}s)")
        _LAST_CALL[key] = slot
    if wait > 0:
        time.sleep(wait)


def _backoff_seconds(resp, attempt):
    try:
        ra = resp.headers.get("Retry-After")
        if ra and str(ra).isdigit():
            return min(int(ra), 120)
    except Exception:
        pass
    return (5, 15, 40)[min(attempt, 2)]


def _get_json(url, params, timeout, label, min_interval=0.8, tries=4,
              headers=None):
    _check_cool(label)
    if not PATIENT:
        tries = min(tries, 2)
    for i in range(tries):
        _polite(label, min_interval)
        try:
            r = _session.get(url, params=params, timeout=timeout,
                             headers=headers)
        except requests.RequestException as e:
            time.sleep(3 * (i + 1))
            if i == tries - 1:
                raise ToolUnavailable(f"{label}: net {e}")
            continue
        if r.status_code == 429:
            if not PATIENT:
                _cool(label, max(COOLDOWN, _backoff_seconds(r, 0)))
                raise ToolUnavailable(f"{label}: 429 (cooldown)")
            if i == tries - 1:  # 마지막 시도면 대기 없이 바로 포기
                raise ToolUnavailable(f"{label}: 429 persistent")
            time.sleep(_backoff_seconds(r, i))
            continue
        try:
            r.raise_for_status()
        except requests.RequestException as e:
            raise ToolUnavailable(f"{label}: {e}")
        try:
            data = r.json()
            _ok(label)
            return data
        except ValueError:
            time.sleep(2 * (i + 1))  # 빈 응답 등 일시 오류 -> 재시도
            if i == tries - 1:
                raise ToolUnavailable(f"{label}: bad json persistent")
            continue
    raise ToolUnavailable(f"{label}: retries exhausted")
def _wiki_lang(query, lang, max_results):
    data = _get_json(f"https://{lang}.wikipedia.org/w/api.php", {
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "formatversion": "2", "srlimit": max_results,
    }, 15, "wikipedia", min_interval=0.2)
    out = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        url = f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(
            title.replace(" ", "_"))
        out.append({"title": title, "url": url,
                    "snippet": strip_tags(item.get("snippet", ""))})
    return out


def wiki_search(query, max_results=8):
    key = f"v{TOOL_VERSION}:wiki:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    # ko/en 동시 발사 (순차 대비 지연 반감). 한도 넉넉한 공식 API라 병렬 안전.
    langs = ["ko", "en"] if has_hangul(query) else ["en", "ko"]
    ex = ThreadPoolExecutor(max_workers=2)
    futs = {lang: ex.submit(_wiki_lang, query, lang, max_results)
            for lang in langs}
    ex.shutdown(wait=False)
    out, errs = [], []
    for lang in langs:
        try:
            out.extend(futs[lang].result(timeout=15))
        except Exception as e:
            errs.append(e)
        if len(out) >= 2:
            break
    if not out and errs:
        raise errs[0]
    cache_put(key, out)
    return out


def openalex_search(query, max_results=8):
    key = f"v{TOOL_VERSION}:openalex:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    params = {
        "search": query, "per-page": max_results,
        "select": "id,title,doi,publication_year,cited_by_count,authorships",
    }
    if os.environ.get("OPENALEX_MAILTO"):
        params["mailto"] = os.environ["OPENALEX_MAILTO"]
    data = _get_json("https://api.openalex.org/works", params, 20, "openalex",
                     min_interval=0.2)
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
    """단발 호출. 세션은 매번 재생성(오염된 세션 재사용 방지).
    예비 엔진이라 호출 빈도가 낮아 간격 1.5s로도 블록 위험 낮음."""
    _polite("ddg", 1.5)
    ddgs = DDGS()
    try:
        # backend 명시: 기본 "auto"는 여러 엔진을 2개씩 순차로 도는 메타검색이라 10초+.
        if kind == "text":
            return list(ddgs.text(query, max_results=max_results, backend="duckduckgo"))
        return list(ddgs.news(query, max_results=max_results, backend="duckduckgo"))
    finally:
        try:
            ddgs.__exit__(None, None, None)
        except Exception:
            pass


def _ddg_guarded(kind, query, max_results, norm_fn):
    """하드에러 30초후 1회 재시도 + junk 60초후 1회 재시도.
    junk(0점 또는 시그니처 매칭)는 캐시하지 않는다."""
    _check_cool("ddg")
    if _DDG_FAILS[0] >= 6 and PATIENT:
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
                if not PATIENT:
                    _cool("ddg")
                    raise ToolUnavailable(f"ddg_{kind}: rate limited (cooldown)")
                time.sleep(30)
                continue
            raise ToolUnavailable(f"ddg_{kind}: {e}")
        sc = relevance(query, out)
        junk = looks_junk(query, out)
        if (sc > 0 and not junk) or len(out) < 3 or attempt == 1:
            _DDG_FAILS[0] = 0
            _ok("ddg")
            return out, sc
        last = "junk-results-softblock"
        _DDG_FAILS[0] += 1
        if not PATIENT:
            _cool("ddg", 30)
            break
        time.sleep(60)
    raise ToolUnavailable(f"ddg_{kind} blocked after retry: {last}")


def ddg_text(query, max_results=5):
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


def ddg_news(query, max_results=5):
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


def warmup_searxng(base=None):
    """SearXNG 업스트림 예열: 일시적 straggler(ddg/naver 등)를 미리 suspend시켜
    다음 실검색이 full-timeout을 안 먹게 한다. HTTP GET만 하고 캐시에 기록하지
    않으며, 성공/실패를 따지지 않는다. 기동 직후 1회가 목적."""
    try:
        base = base or os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")
        for cat, q in (("general", "날씨"), ("news", "속보")):
            try:
                _session.get(f"{base}/search",
                             params={"q": q, "format": "json",
                                     "categories": cat},
                             timeout=(2, 6))
            except Exception:
                pass
    except Exception:
        pass


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
                    warmup_searxng(base)  # 콜드스타트 straggler 예열 후 반환
                    return True
            except requests.RequestException:
                pass
        return False


def searxng_news(query, max_results=8):
    return searxng_search(query, max_results, category="news")


def searxng_search(query, max_results=8, category="general"):
    """로컬 SearXNG (searxng/start.sh). 꺼져 있으면 자동 실행 1회 시도."""
    key = f"v{TOOL_VERSION}:searxng:{category}:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    base = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")
    for attempt in range(2):
        try:
            r = _session.get(f"{base}/search",
                             params={"q": query, "format": "json",
                                     "categories": category}, timeout=(1.5, 8))
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
    """Semantic Scholar. 키 없으면 공유 한도라 429 잦음 -> tries=2로 빨리 포기.
    SEMANTIC_SCHOLAR_KEY가 있으면 인증 한도(1r/s)로 간격 단축."""
    key = f"v{TOOL_VERSION}:s2:{query}:{max_results}"
    c = cache_get(key)
    if c is not None:
        return c
    s2_key = os.environ.get("SEMANTIC_SCHOLAR_KEY")
    data = _get_json("https://api.semanticscholar.org/graph/v1/paper/search", {
        "query": query, "limit": max_results,
        "fields": "title,url,year,citationCount,authors",
    }, 15, "semantic_scholar",
        min_interval=0.2 if s2_key else 1.1, tries=2,
        headers={"x-api-key": s2_key} if s2_key else None)
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
    # 문장부호("BERT:")가 섞이면 0건 -> 영숫자 토큰만, 제목 필드 AND 검색
    toks = [t for t in re.findall(r"[A-Za-z0-9]+", query) if t.lower() not in EN_STOP]
    if not toks:
        return []
    _check_cool("arxiv")
    _polite("arxiv", 3.0)
    try:
        r = _session.get("https://export.arxiv.org/api/query", params={
            "search_query": " AND ".join(f"ti:{t}" for t in toks),
            "max_results": max_results}, timeout=20)
        if r.status_code in (429, 503):
            _cool("arxiv")
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
    data = _get_json("https://api.crossref.org/works", params, 20, "crossref",
                     min_interval=0.3)
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
    }, 15, "wikidata", min_interval=0.3)
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


def you_search(query, max_results=5):
    """You.com keyless MCP (?profile=free, 일 100회). 키 발급 없음.
    쿼터 보호: 5건 + 타임아웃 10s + 캐시 30일."""
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
            timeout=10)
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
    "searxng_news": searxng_news,
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
    "searxng_news": "SearXNG 뉴스 (키 불필요)",
    "semantic_scholar": "Semantic Scholar 논문 (키 불필요)",
    "arxiv": "arXiv 논문 (키 불필요)",
    "crossref": "Crossref 논문 (키 불필요)",
    "wikidata": "Wikidata 개체 (키 불필요)",
}


# search()에서 차례가 와야 호출: you_search는 일일 한도, ddg는 차단이 잦은 예비 엔진.
# arxiv는 규칙상 3초 간격이라 deadline을 갉아먹으므로 차례 호출로 강등
# (OpenAlex+Crossref가 논문의 95%를 커버).
LAZY_ENGINES = {"you_search", "duckduckgo", "duckduckgo_news", "arxiv"}


# Tier별 1차 대기 상한: 공식API 1.5s 안에 못 오면 일단 건너뛰고, searxng는
# 3s까지. 1차 순회가 불발이면 전체 DEADLINE까지 늦은 엔진을 회수 (품질 보존).
TIER_TIMEOUT = {"wikipedia": 1.5, "wikidata": 1.5, "openalex": 1.5,
                "crossref": 1.5, "searxng": 3.0, "searxng_news": 3.0}


# 도메인 전문용어(entity/기술용어)는 위키 일반의미가 문자열 매칭으로 고득점을
# 받아 체인을 끊어버리는 문제를 피하려고 조기채택 임계를 상향: 임계 미만이면
# searxng까지 보고 best를 선택한다 (예: DataLoader ETL 문서 0.75 -> PyTorch
# 튜토리얼 1.0으로 교정). 그 외 카테고리는 0.6 유지 (지연 우선).
STOP_SCORE = {"기술용어": 0.8, "entity": 0.8}


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
        ex = ThreadPoolExecutor(max_workers=len(chain))
        futs = {t: ex.submit(_run_one, t, q) for t in chain}
        wait(futs.values(), timeout=DEADLINE)
        ex.shutdown(wait=False)  # 늦은 엔진은 백그라운드에서 끝나 캐시만 채움
        tools = {}
        for t, fu in futs.items():
            tools[t] = fu.result()[1] if fu.done() else {
                "label": TOOL_LABELS.get(t, t), "items": [], "score": 0.0,
                "status": "timeout", "detail": f">{DEADLINE}s"}
        ordered = sorted(tools, key=lambda t: tools[t]["score"], reverse=True)
        return {"query": q, "category": cat, "lang": detect_lang(q),
                "method": route["method"], "reason": route["reason"],
                "chain": chain, "order": ordered, "tools": tools,
                "elapsed": round(time.time() - t0, 1)}
    except Exception as e:
        return {"query": q if isinstance(q, str) else str(query),
                "error": f"fatal: {e}", "tools": {}}


def search(query, curated=None, extra=None):
    """메인 진입점. 절대 raise하지 않음.
    전문용어·동명이의(Opus/venv/backbone류)는 단일 best 대신 sense별 전부를
    보여주는 multi_search() 권장."""
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
        # 체인 전 엔진 동시 시작, 우선순위 순으로 결과 확인 -> 지연 = 첫 합격 엔진까지.
        # Tier 타임아웃: 빠른 엔진이 늦으면 일단 건너뛰고, 1차 불발시에만
        # 전체 DEADLINE까지 회수 (2차). 일일 한도 엔진(LAZY)은 차례가 왔을 때만 호출.
        ex = ThreadPoolExecutor(max_workers=len(chain))
        call = lambda t: [x for x in ENGINES[t](q) if norm(x.get("title"))]
        futs = {t: ex.submit(call, t) for t in chain if t not in LAZY_ENGINES}
        end = time.time() + DEADLINE
        pending = []
        for i, tool in enumerate(chain):
            if tool not in futs:  # 예비 엔진 차례 = 앞 엔진 전부 불합격 -> 남은 예비 동시 시작
                for t in chain[i:]:
                    futs.setdefault(t, ex.submit(call, t))
            fu = futs[tool]
            try:
                items = fu.result(timeout=max(
                    0.1, min(TIER_TIMEOUT.get(tool, DEADLINE),
                             end - time.time())))
            except FutureTimeout:
                tried[tool] = {"status": "timeout", "detail": f">{DEADLINE}s"}
                pending.append(tool)
                continue
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
            if sc >= STOP_SCORE.get(cat, 0.6) and items:
                pending = []
                break
        for tool in pending:  # 2차: 1차 불발시에만 늦은 엔진 회수
            try:
                items = futs[tool].result(timeout=max(0.1, end - time.time()))
            except FutureTimeout as e:
                tried[tool] = {"status": "timeout", "detail": str(e)[:60]}
                continue
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
        ex.shutdown(wait=False)
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
