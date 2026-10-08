"""omniSearch 웹 UI (Flask). 실행: omnisearch-web

화면은 frontend/ (Vite + React + shadcn/ui)에서 빌드되어 src/omnisearch/static/ 으로
나오고, Flask가 /static/ 아래에서 그대로 서빙한다.
"""
import os
import threading
import time

from flask import Flask, jsonify, request

# duckduckgo-search >= 7.0 에서는 패키지명이 ddgs 로 변경됨. 둘 다 지원.
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from .core import multi_search, warmup_searxng
from .wordlists import WORD_LISTS, pick_random_word

app = Flask(__name__)  # 같은 패키지의 static/ 을 /static/ 으로 서빙


@app.route("/")
@app.route("/smart")  # 구 URL 호환: 일반 검색/스마트 검색이 한 화면으로 합쳐짐
def index():
    return app.send_static_file("index.html")


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    search_type = request.args.get("type", "text")
    if not query:
        return jsonify({"error": "검색어(q)가 비어 있습니다."}), 400
    try:
        with DDGS() as ddgs:
            if search_type == "images":
                results = list(ddgs.images(query, max_results=20))
            elif search_type == "news":
                results = list(ddgs.news(query, max_results=20))
            elif search_type == "videos":
                results = list(ddgs.videos(query, max_results=20))
            else:
                results = list(ddgs.text(query, max_results=20))
        return jsonify({"query": query, "type": search_type, "count": len(results), "results": results})
    except Exception as e:
        if "No results found" in str(e):  # ddgs는 결과 0건을 예외로 알린다 -> 빈 목록으로
            return jsonify({"query": query, "type": search_type, "count": 0, "results": []})
        return jsonify({"error": f"duckduckgo-search 오류: {e}"}), 500


@app.route("/api/word-lists")
def api_word_lists():
    return jsonify(WORD_LISTS)


@app.route("/api/random-word")
def api_random_word():
    return jsonify(pick_random_word(request.args.get("category")))


@app.route("/api/smart-search")
def api_smart_search():
    """OmniTool multi_search 백엔드: 체인 전 엔진 실행 + 점수순 섹션 표시.
    단일 best만 주던 구방식과 달리 동명이의 sense를 전부 보여준다."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "검색어(q)가 비어 있습니다."}), 400
    try:
        r = multi_search(query)
        if r.get("error") and not r.get("tools"):
            return jsonify({"error": r["error"]}), 500
        return jsonify({
            "query": r["query"],
            "route": {"category": r.get("category"), "tools": r.get("chain", []),
                      "method": r.get("method"), "reason": r.get("reason")},
            "fused": r.get("fused", []),
            "results_by_tool": {
                t: {"label": p["label"], "items": p["items"],
                    "status": p.get("status"), "detail": p.get("detail")}
                for t, p in r.get("tools", {}).items()},
            "scores": {t: p.get("score") for t, p in r.get("tools", {}).items()},
            "order": r.get("order", []),
            "elapsed": r.get("elapsed"),
        })
    except Exception as e:
        return jsonify({"error": f"스마트 검색 오류: {e}"}), 500


_WARMED = False


def _warmup():
    """서버 시작 시 DDG 신뢰도 + SearXNG 업스트림 예열. 실패해도 무시."""
    global _WARMED
    if _WARMED:
        return
    _WARMED = True
    try:
        time.sleep(3)
        with DDGS() as ddgs:
            for q in ["서울", "Python", "김치찌개", "BTS"]:
                try:
                    list(ddgs.text(q, max_results=3))
                except Exception:
                    pass
                time.sleep(2)
        warmup_searxng()
    except Exception:
        pass


def main():
    port = int(os.environ.get("OMNI_PORT", "5000"))
    threading.Thread(target=_warmup, daemon=True).start()
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
