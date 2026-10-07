"""duckduckgo-search 라이브러리를 사용한 간단한 검색 웹페이지 (Flask 백엔드)."""
import threading
import time

from flask import Flask, jsonify, request, render_template_string

# duckduckgo-search >= 7.0 에서는 패키지명이 ddgs 로 변경됨. 둘 다 지원.
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from smart_search import WORD_LISTS, classify, pick_random_word, smart_search
from omnitool import multi_search

# "multi": full engine chain (default). "legacy": old single-engine backend.
# Instant rollback: flip to "legacy" and restart.
SMART_BACKEND = "multi"

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>DuckDuckGo 간단 검색</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Malgun Gothic", sans-serif; background: #f6f8fa; margin: 0; padding: 0; color: #1c1e21; }
  header { background: #de5833; color: white; padding: 24px 16px; text-align: center; }
  header h1 { margin: 0; font-size: 24px; }
  header p { margin: 8px 0 0; opacity: 0.9; font-size: 14px; }
  main { max-width: 720px; margin: 24px auto; padding: 0 16px 40px; }
  .search-box { display: flex; gap: 8px; background: white; padding: 12px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .search-box input { flex: 1; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 8px; }
  .search-box button { padding: 12px 20px; font-size: 16px; background: #de5833; color: white; border: none; border-radius: 8px; cursor: pointer; }
  .search-box button:hover { background: #c74a2a; }
  .search-box button:disabled { opacity: 0.6; cursor: wait; }
  .tabs { display: flex; gap: 8px; margin: 16px 0; }
  .tabs button { padding: 8px 16px; border: 1px solid #ddd; background: white; border-radius: 20px; cursor: pointer; }
  .tabs button.active { background: #1c1e21; color: white; border-color: #1c1e21; }
  #status { margin: 12px 0; font-size: 14px; color: #666; }
  .result { background: white; border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
  .result a.title { font-size: 17px; font-weight: bold; color: #1a0dab; text-decoration: none; }
  .result a.title:hover { text-decoration: underline; }
  .result .url { font-size: 13px; color: #006621; margin-top: 4px; word-break: break-all; }
  .result .snippet { font-size: 14px; margin-top: 8px; line-height: 1.5; }
  .result img { max-width: 100%; border-radius: 8px; margin-top: 8px; }
  .meta { font-size: 12px; color: #888; margin-top: 8px; }
</style>
</head>
<body>
<header>
  <h1>🦆 DuckDuckGo 간단 검색</h1>
  <p>duckduckgo-search 라이브러리 + Flask로 만든 테스트 페이지</p>
</header>
<main>
  <div class="search-box">
    <input id="q" type="text" placeholder="검색어를 입력하세요 (예: 파이썬)" value="파이썬" />
    <button id="btn" onclick="doSearch()">검색</button>
  </div>
  <div class="tabs">
    <button class="active" data-type="text">일반</button>
    <button data-type="images">이미지</button>
    <button data-type="news">뉴스</button>
    <button data-type="videos">비디오</button>
  </div>
  <div id="status">검색어를 입력하고 검색 버튼을 눌러보세요.</div>
  <div id="results"></div>
</main>
<script>
let searchType = "text";
document.querySelectorAll(".tabs button").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll(".tabs button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    searchType = b.dataset.type;
    doSearch();
  };
});
document.getElementById("q").addEventListener("keydown", e => {
  if (e.key === "Enter") doSearch();
});

async function doSearch() {
  const q = document.getElementById("q").value.trim();
  const btn = document.getElementById("btn");
  const status = document.getElementById("status");
  const resultsDiv = document.getElementById("results");
  if (!q) { status.textContent = "검색어를 입력해주세요."; return; }
  btn.disabled = true;
  btn.textContent = "검색 중...";
  status.textContent = `"${q}" (${searchType}) 검색 중...`;
  resultsDiv.innerHTML = "";
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&type=${searchType}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "검색 실패");
    status.textContent = `총 ${data.count}건 (backend: duckduckgo-search)`;
    if (data.results.length === 0) {
      resultsDiv.innerHTML = "<p>결과가 없습니다.</p>";
      return;
    }
    resultsDiv.innerHTML = data.results.map(renderItem).join("");
  } catch (e) {
    status.textContent = "오류: " + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "검색";
  }
}

function esc(s) {
  return (s || "").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
}

function renderItem(r) {
  if (searchType === "images") {
    return `<div class="result">
      <a class="title" href="${esc(r.url)}" target="_blank">${esc(r.title)}</a>
      <div><img src="${esc(r.image)}" alt="${esc(r.title)}" loading="lazy" /></div>
      <div class="url">${esc(r.url)}</div>
      <div class="meta">출처: ${esc(r.source || "")} / 크기: ${esc(r.width || "?")}x${esc(r.height || "?")}</div>
    </div>`;
  }
  if (searchType === "news") {
    return `<div class="result">
      <a class="title" href="${esc(r.url)}" target="_blank">${esc(r.title)}</a>
      <div class="snippet">${esc(r.body || "")}</div>
      <div class="meta">${esc(r.source || "")} · ${esc(r.date || "")}</div>
    </div>`;
  }
  if (searchType === "videos") {
    return `<div class="result">
      <a class="title" href="${esc(r.content)}" target="_blank">${esc(r.title)}</a>
      <div class="snippet">${esc(r.description || "")}</div>
      <div class="meta">길이: ${esc(r.duration || "?")} · 게시: ${esc(r.published || "")} · 조회: ${esc(r.statistics || "")}</div>
    </div>`;
  }
  return `<div class="result">
    <a class="title" href="${esc(r.href)}" target="_blank">${esc(r.title)}</a>
    <div class="url">${esc(r.href)}</div>
    <div class="snippet">${esc(r.body || "")}</div>
  </div>`;
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


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
        return jsonify({"error": f"duckduckgo-search 오류: {e}"}), 500


SMART_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>스마트 라우팅 검색</title>
<style>
  body { font-family: -apple-system, "Malgun Gothic", sans-serif; background: #f6f8fa; margin: 0; color: #1c1e21; }
  header { background: #1c1e21; color: white; padding: 24px 16px; text-align: center; }
  header a { color: #ffd8cc; font-size: 13px; }
  main { max-width: 760px; margin: 24px auto; padding: 0 16px 40px; }
  .card { background: white; border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
  .row { display: flex; gap: 8px; }
  input { flex: 1; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 8px; }
  button { padding: 12px 16px; font-size: 15px; background: #de5833; color: white; border: none; border-radius: 8px; cursor: pointer; }
  button.ghost { background: #1c1e21; }
  button:disabled { opacity: 0.6; }
  .route { background: #fff7ed; border: 1px solid #fed7aa; border-radius: 8px; padding: 12px; margin: 12px 0; font-size: 14px; }
  .result { border-top: 1px solid #eee; padding: 10px 0; }
  .result a { color: #1a0dab; font-weight: bold; text-decoration: none; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chips button { background: white; color: #1c1e21; border: 1px solid #ddd; border-radius: 16px; padding: 6px 12px; font-size: 13px; }
</style>
</head>
<body>
<header>
  <h1>🤖 스마트 라우팅 검색 (키 불필요)</h1>
  <p>규칙 분류기가 단어 종류를 판단 → Wikipedia / OpenAlex / GDELT / DuckDuckGo 중 자동 선택</p>
  <a href="/">← 일반 검색으로</a>
</header>
<main>
  <div class="card">
    <div class="row">
      <input id="q" placeholder="검색어 입력 (예: 갓생, Attention Is All You Need)" />
      <button class="ghost" onclick="randomWord()">🎲 랜덤</button>
      <button id="btn" onclick="doSmart()">검색</button>
    </div>
    <div class="chips" id="chips"></div>
  </div>
  <div id="route"></div>
  <div id="results"></div>
</main>
<script>
async function loadLists() {
  const r = await fetch("/api/word-lists").then(x => x.json());
  const chips = document.getElementById("chips");
  chips.innerHTML = "";
  for (const [cat, words] of Object.entries(r)) {
    const b = document.createElement("button");
    b.textContent = `🎲 ${cat} 랜덤`;
    b.onclick = () => randomWord(cat);
    chips.appendChild(b);
  }
}
async function randomWord(cat) {
  const url = cat ? `/api/random-word?category=${encodeURIComponent(cat)}` : "/api/random-word";
  const d = await fetch(url).then(x => x.json());
  document.getElementById("q").value = d.word;
  doSmart();
}
async function doSmart() {
  const q = document.getElementById("q").value.trim();
  if (!q) return;
  const btn = document.getElementById("btn");
  btn.disabled = true; btn.textContent = "검색 중...";
  document.getElementById("route").innerHTML = "분류 + 검색 중...";
  document.getElementById("results").innerHTML = "";
  try {
    const d = await fetch(`/api/smart-search?q=${encodeURIComponent(q)}`).then(x => x.json());
    if (d.error) throw new Error(d.error);
    document.getElementById("route").innerHTML = `<div class="route">📂 분류: <b>${d.route.category}</b> (${d.route.method})<br>🧰 사용 도구: <b>${d.route.tools.join(", ")}</b><br>💡 근거: ${d.route.reason}</div>`;
    let html = "";
    for (const [tool, pack] of Object.entries(d.results_by_tool)) {
      html += `<div class="card"><h3>${pack.label} — ${pack.items.length}건</h3>`;
      html += pack.items.slice(0, 10).map(r => `<div class="result"><a href="${r.url || "#"}" target="_blank">${esc(r.title)}</a><div style="font-size:13px;color:#444;margin-top:4px">${esc(r.snippet || "")}</div><div style="font-size:12px;color:#888;word-break:break-all">${esc(r.url || "")}</div></div>`).join("") || "<p>결과 없음</p>";
      html += "</div>";
    }
    document.getElementById("results").innerHTML = html;
  } catch (e) {
    document.getElementById("route").innerHTML = "오류: " + e.message;
  } finally {
    btn.disabled = false; btn.textContent = "검색";
  }
}
function esc(s){ return (s||"").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m])); }
document.getElementById("q").addEventListener("keydown", e => { if (e.key === "Enter") doSmart(); });
loadLists();
</script>
</body>
</html>
"""


@app.route("/smart")
def smart_page():
    return render_template_string(SMART_HTML)


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
        if SMART_BACKEND == "legacy":
            return jsonify(smart_search(query))
        r = multi_search(query)
        if r.get("error") and not r.get("tools"):
            return jsonify({"error": r["error"]}), 500
        return jsonify({
            "query": r["query"],
            "route": {"category": r.get("category"), "tools": r.get("chain", []),
                      "method": r.get("method"), "reason": r.get("reason")},
            "results_by_tool": {
                t: {"label": p["label"], "items": p["items"]}
                for t, p in r.get("tools", {}).items()},
            "scores": {t: p.get("score") for t, p in r.get("tools", {}).items()},
            "order": r.get("order", []),
            "elapsed": r.get("elapsed"),
        })
    except Exception as e:
        return jsonify({"error": f"스마트 검색 오류: {e}"}), 500


_WARMED = False


def _warmup():
    """서버 시작 시 DDG 신뢰도 예열 (콜드스타트 junk 방지). 실패해도 무시."""
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
    except Exception:
        pass


if __name__ == "__main__":
    threading.Thread(target=_warmup, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=True)
