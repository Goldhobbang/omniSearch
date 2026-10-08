# -*- coding: utf-8 -*-
"""RRF 융합 + RSS 파서 + 체인 구성 단위테스트. 네트워크 없이 실행."""
from omnisearch.core import (
    CHAIN, ENGINES, _bing_params, _fusable, _parse_rss, _unwrap_bing, _url_key, fuse,
)


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name


def it(title, url, snip=""):
    return {"title": title, "url": url, "snippet": snip}


# 1) 같은 문서(URL 표준화: www/끝 슬래시/쿼리 무시)는 병합되고 sources가 합쳐진다
a = [it("A page", "https://www.example.com/x/"), it("Only A", "https://a.com/1")]
b = [it("A page copy", "http://example.com/x"), it("Only B", "https://b.com/1")]
r = fuse({"e1": (a, 1.0), "e2": (b, 1.0)})
check("dup url merged", len([x for x in r if "example.com" in x["url"]]) == 1)
check("shared doc ranked first", r[0]["sources"] == ["e1", "e2"])

# 2) 중계 URL(Google 뉴스)은 URL이 아니라 제목으로 중복 제거 (" - 매체" 꼬리 무시)
g = [it("티몬 정산 지연 사태 - 한국경제", "https://news.google.com/rss/articles/AAA")]
bn = [it("티몬 정산 지연 사태", "https://www.hankyung.com/article/1")]
r = fuse({"google_news": (g, 0.8), "bing_news": (bn, 0.8)})
check("syndicated title merged", len(r) == 1 and len(r[0]["sources"]) == 2)

# 3) 관련도 높은 엔진의 1위가 낮은 엔진의 1위보다 앞선다
hi = [it("exact", "https://h.com/1")]
lo = [it("weak", "https://l.com/1")]
r = fuse({"lo": (lo, 0.2), "hi": (hi, 1.0)})
check("relevance weighting", r[0]["title"] == "exact")

# 4) 빈 입력/limit
check("empty", fuse({}) == [])
check("limit", len(fuse({"e": ([it(f"t{i}", f"https://x.com/{i}") for i in range(20)], 1.0)}, limit=5)) == 5)
check("url key google news empty", _url_key("https://news.google.com/rss/articles/X") == "")

# 5) Bing 뉴스 중계 링크는 원문으로 풀린다
wrapped = "http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&url=https%3a%2f%2fwww.etnews.com%2f2026&c=1"
check("bing unwrap", _unwrap_bing(wrapped) == "https://www.etnews.com/2026")
check("plain url untouched", _unwrap_bing("https://a.com/x") == "https://a.com/x")

# 6) RSS 파서: 제목 반복 설명 제거, 빈 제목 스킵, 최대 개수
xml = """<?xml version="1.0"?><rss><channel>
<item><title>Hello &amp; World</title><link>https://a.com/1</link>
<description>Hello &amp; World</description><source>Src</source></item>
<item><title></title><link>https://a.com/2</link></item>
<item><title>Second</title><link>https://a.com/3</link><description>&lt;b&gt;real&lt;/b&gt; summary text that is long enough</description></item>
</channel></rss>""".encode("utf-8")
r = _parse_rss(xml, 8)
check("rss skips empty title", len(r) == 2)
check("rss unescape + dup desc dropped", r[0]["title"] == "Hello & World" and r[0]["snippet"] == "Src · ")
check("rss strips tags", "real summary" in r[1]["snippet"])
check("rss max_results", len(_parse_rss(xml, 1)) == 1)

# 7) Bing 파라미터: 영어에는 setmkt 금지 (실측: en-US 지정시 무관한 결과)
check("bing ko market", _bing_params("갓생").get("setmkt") == "ko-KR")
check("bing en no market", "setmkt" not in _bing_params("Kubernetes operator"))

# 8) 기본 체인에 SearXNG 없음 + RSS 엔진 등록
check("no searxng by default", all("searxng" not in c and "searxng_news" not in c for c in CHAIN.values()))
check("rss engines registered", all(e in ENGINES for e in ("bing_web", "bing_news", "google_news")))
check("every chain engine exists", all(e in ENGINES for c in CHAIN.values() for e in c))
# 9) 융합 게이팅: 강한 엔진(1.0)이 있으면 약한 엔진(0.5)은 제외, 모두 약하면 유지
strong = ([it("good", "https://g.com/1")], 1.0)
weak = ([it("noise", "https://n.com/1")], 0.5)
check("weak engine gated out", set(_fusable("q", {"s": strong, "w": weak})) == {"s"})
check("all-weak kept", set(_fusable("q", {"a": weak, "b": ([it("n2", "https://n.com/2")], 0.45)})) == {"a", "b"})
check("below FUSE_MIN dropped", _fusable("q", {"x": ([it("z", "https://z.com/1")], 0.2)}) == {})

# 10) 신조어는 '뜻' 질의 엔진이 1순위
check("slang chain leads with define", CHAIN["한국어 신조어"][0] == "bing_define" and "bing_define" in ENGINES)
print("ALL FUSE TESTS PASSED")
