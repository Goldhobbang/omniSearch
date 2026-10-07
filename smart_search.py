"""랜덤 단어 -> 규칙 기반 분류기 -> 키 없이 무료 API 라우팅.

라우팅표:
- 기관명       -> Wikipedia (ko) + DuckDuckGo 보조
- 기술용어     -> Wikipedia (ko/en) + DuckDuckGo 보조
- 한국어 신조어 -> DuckDuckGo text (위키에 잘 없음)
- 논문 제목    -> OpenAlex (키 불필요)
- 최신 AI뉴스/논란 -> GDELT DOC API (키 불필요) + DuckDuckGo news 보조
"""
import random
import urllib.parse

import requests

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

WORD_LISTS = {
    "기관명": [
        "한국천문연구원",
        "한국전자통신연구원",
        "식품의약품안전처",
        "한국원자력안전기술원",
        "국립국어원",
        "한국지능정보사회진흥원",
        "정보통신기획평가원",
        "한국과학기술원",
        "한국저작권위원회",
        "개인정보보호위원회",
    ],
    "기술용어": [
        "양자 얽힘",
        "초전도체",
        "벡터 데이터베이스",
        "RAG",
        "트랜스포머 아키텍처",
        "쿠버네티스",
        "도커 컨테이너",
        "차등 프라이버시",
        "연합학습",
        "뉴로모픽 칩",
    ],
    "한국어 신조어": [
        "갓생",
        "스불재",
        "어쩔티비",
        "무지성",
        "킹받네",
        "삼귀다",
        "꾸안꾸",
        "점메추",
        "알잘딱깔센",
        "어그로",
    ],
    "논문 제목": [
        "Attention Is All You Need",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "Language Models are Few-Shot Learners",
        "Diffusion Models Beat GANs on Image Synthesis",
        "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
        " Constitutional AI: Harmlessness from AI Feedback",
    ],
    "최신 AI뉴스나 논란": [
        "생성형 AI 저작권 소송",
        "AI 딥페이크 선거 논란",
        "인공지능 기본법 시행 논란",
        "AI 학습데이터 무단수집 논란",
        "거대언어모델 할루시네이션 의료사고 논란",
        "AI 면접 채용 공정성 논란",
        "오픈소스 AI 모델 규제 논란",
    ],
}

# 카테고리 -> 사용할 도구
ROUTE_MAP = {
    "기관명": ["wikipedia", "duckduckgo"],
    "기술용어": ["wikipedia", "duckduckgo"],
    "한국어 신조어": ["duckduckgo"],
    "논문 제목": ["openalex"],
    "최신 AI뉴스나 논란": ["gdelt", "duckduckgo_news"],
}

ORG_SUFFIX = ("연구원", "연구회", "협회", "재단", "대학교", "대학교", "청", "부", "위원회", "센터", "진흥원", "평가원", "기술원", "안전처")
NEWS_KEYWORDS = ("논란", "소송", "발표", "출시", "최신", "속보", "규제", "선거", "저작권", "해킹", "유출", "선언", "기본법", "딥페이크", "공정성", "할루시네이션")
PAPER_HINTS = ("arxiv", "et al", "model", "transformer", "diffusion", "llm", "pre-training", "prompting", "retrieval", "generation", "bert", "gpt")


def _norm(q: str) -> str:
    return q.strip()


def classify(query: str) -> dict:
    """규칙 기반 분류. exact-match 우선, 이후 패턴 매칭."""
    q = _norm(query)
    q_lower = q.lower()

    # 1) 리스트에 정확히 있으면 그대로
    for cat, words in WORD_LISTS.items():
        if q in words:
            tools = ROUTE_MAP[cat]
            return {"category": cat, "tools": tools, "reason": f"사전 단어리스트 '{cat}'에 정확히 일치", "method": "rule:exact-match"}

    # 2) 뉴스 패턴
    if any(k in q for k in NEWS_KEYWORDS):
        return {"category": "최신 AI뉴스나 논란", "tools": ROUTE_MAP["최신 AI뉴스나 논란"],
                "reason": "논란/소송/규제 등 뉴스 키워드 포함", "method": "rule:keyword-news"}
    # 3) 논문 패턴 (영어 제목, 콜론, 길이가 김)
    if (":" in q or any(h in q_lower for h in PAPER_HINTS)
            or (len(q.split()) >= 5 and sum(c.isascii() for c in q) / max(len(q), 1) > 0.6)):
        return {"category": "논문 제목", "tools": ROUTE_MAP["논문 제목"],
                "reason": "영어 논문형 제목 패턴 (콜론/학술 키워드/긴 영문)", "method": "rule:pattern-paper"}
    # 4) 기관명 패턴
    if q.endswith(ORG_SUFFIX) or any(s in q for s in ("한국", "국립", "정보통신", "과학기술")) and len(q) <= 15:
        return {"category": "기관명", "tools": ROUTE_MAP["기관명"],
                "reason": "기관 접미사(원/청/회/위원회 등) 또는 공공기관 명명 패턴", "method": "rule:pattern-org"}
    # 5) 신조어: 리스트에 없지만 짧은 한국어 + 조사 없이 끝남 -> DuckDuckGo
    # (오분류 방지를 위해 기술 키워드가 있으면 기술용어 우선)
    tech_hints = ("양자", "초전도", "데이터베이스", "학습", "칩", "프라이버시", "쿠버", "도커", "벡터", "RAG", "트랜스포머")
    if any(h in q for h in tech_hints):
        return {"category": "기술용어", "tools": ROUTE_MAP["기술용어"],
                "reason": "기술 키워드 포함", "method": "rule:keyword-tech"}

    # 6) 기본값: 한글 짧은 단어 -> 신조어 가능성, 그 외 일반(DDG)
    if len(q) <= 6 and all("\uac00" <= c <= "\ud7a3" or c.isascii() for c in q.replace(" ", "")):
        return {"category": "한국어 신조어", "tools": ROUTE_MAP["한국어 신조어"],
                "reason": "짧은 한국어 단어 (기본값: 신조어/DDG로 조회)", "method": "rule:fallback-short-ko"}
    return {"category": "기술용어", "tools": ROUTE_MAP["기술용어"],
            "reason": "어느 패턴에도 안 맞음 (기본값: 기술용어/Wikipedia+DDG)", "method": "rule:fallback-default"}


def pick_random_word(category: str | None = None) -> dict:
    if category and category in WORD_LISTS:
        cat = category
    else:
        cat = random.choice(list(WORD_LISTS.keys()))
    return {"category": cat, "word": random.choice(WORD_LISTS[cat])}


# ---------- 각 도구별 검색 함수 (전부 키 불필요) ----------

def search_duckduckgo(query: str, max_results: int = 10) -> list:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def search_duckduckgo_news(query: str, max_results: int = 10) -> list:
    with DDGS() as ddgs:
        return list(ddgs.news(query, max_results=max_results))


def search_wikipedia(query: str, max_results: int = 5) -> list:
    """ko.wikipedia 검색 + 요약. 결과 표준화: title/url/snippet."""
    out = []
    try:
        r = requests.get("https://ko.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": max_results,
        }, timeout=10)
        r.raise_for_status()
        for item in r.json().get("query", {}).get("search", []):
            title = item["title"]
            url = "https://ko.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            # 요약 한 건씩
            snippet = ""
            try:
                s = requests.get(
                    "https://ko.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title),
                    timeout=10).json()
                snippet = s.get("extract", "")
            except Exception:
                pass
            out.append({"title": title, "url": url, "snippet": snippet or item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")})
    except Exception as e:
        out.append({"title": f"Wikipedia 오류: {e}", "url": "", "snippet": ""})
    return out


def search_openalex(query: str, max_results: int = 10) -> list:
    """논문 검색. 표준화: title/url/snippet(+meta)."""
    out = []
    try:
        r = requests.get("https://api.openalex.org/works", params={
            "search": query, "per-page": max_results,
            "select": "id,title,doi,publication_year,cited_by_count,authorships,abstract_inverted_index",
        }, timeout=15)
        r.raise_for_status()
        for w in r.json().get("results", []):
            authors = ", ".join(a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])[:3])
            out.append({
                "title": w.get("title", ""),
                "url": w.get("doi") or w.get("id", ""),
                "snippet": f"{w.get('publication_year', '?')}년 · 인용 {w.get('cited_by_count', 0)}회 · 저자: {authors}",
            })
    except Exception as e:
        out.append({"title": f"OpenAlex 오류: {e}", "url": "", "snippet": ""})
    return out


def search_gdelt(query: str, max_results: int = 20) -> list:
    """GDELT DOC API 뉴스 검색. 표준화: title/url/snippet(+meta)."""
    out = []
    try:
        r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
            "query": query, "mode": "artlist", "maxrecords": max_results,
            "format": "json", "sort": "datedesc",
        }, timeout=15)
        r.raise_for_status()
        for a in r.json().get("articles", []):
            out.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "snippet": f"{a.get('sourcecountry', '')} {a.get('domain', '')} · {a.get('seendate', '')}",
            })
    except Exception as e:
        out.append({"title": f"GDELT 오류: {e}", "url": "", "snippet": ""})
    return out


TOOL_LABEL = {
    "wikipedia": "Wikipedia (키 불필요)",
    "duckduckgo": "DuckDuckGo 일반 (키 불필요)",
    "duckduckgo_news": "DuckDuckGo 뉴스 (키 불필요)",
    "openalex": "OpenAlex 논문 (키 불필요)",
    "gdelt": "GDELT 뉴스 (키 불필요)",
}


def smart_search(query: str) -> dict:
    """분류 -> 도구 호출 -> 통합 반환."""
    route = classify(query)
    results_by_tool = {}
    for tool in route["tools"]:
        try:
            if tool == "wikipedia":
                results_by_tool[tool] = {"label": TOOL_LABEL[tool], "items": search_wikipedia(query)}
            elif tool == "duckduckgo":
                results_by_tool[tool] = {"label": TOOL_LABEL[tool],
                                         "items": [{"title": r.get("title", ""), "url": r.get("href", ""),
                                                    "snippet": r.get("body", "")} for r in search_duckduckgo(query)]}
            elif tool == "duckduckgo_news":
                results_by_tool[tool] = {"label": TOOL_LABEL[tool],
                                         "items": [{"title": r.get("title", ""), "url": r.get("url", ""),
                                                    "snippet": r.get("body", "")} for r in search_duckduckgo_news(query)]}
            elif tool == "openalex":
                results_by_tool[tool] = {"label": TOOL_LABEL[tool], "items": search_openalex(query)}
            elif tool == "gdelt":
                results_by_tool[tool] = {"label": TOOL_LABEL[tool], "items": search_gdelt(query)}
        except Exception as e:
            results_by_tool[tool] = {"label": TOOL_LABEL.get(tool, tool), "items": [],
                                     "error": str(e)}
    return {"query": query, "route": route, "results_by_tool": results_by_tool}


if __name__ == "__main__":
    # 간단 자가테스트: 카테고리별 1개씩
    for cat, words in WORD_LISTS.items():
        q = words[0]
        print(f"[{cat}] {q} ->", classify(q))
