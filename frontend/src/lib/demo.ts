// GitHub Pages 데모: 서버 없이 브라우저에서 CORS를 허용하는 무료 API만 직접 호출하고,
// core.py 의 분류 · 관련도 · 가중 RRF 를 같은 식으로 옮겨 돌린다.
// (Bing/Google RSS, DuckDuckGo 등 CORS 불가 엔진은 "사용 불가"로 표시된다.)
import type { Item, Pack, Smart } from "./api"
import { WORD_LISTS } from "./demo-words"

const DEADLINE_MS = 4000
const FUSE_MIN = 0.4

const EN_STOP = new Set(
  (
    "the a an of and or for to in on at by with from as is are was were be been it its this " +
    "that these those their there here which who whom whose what when where how why will " +
    "would can could should may might must not no yes vs via per de la le les des der die " +
    "das und ein eine et al"
  ).split(" ")
)
const NEWS_KW = [
  "논란",
  "소송",
  "발표",
  "출시",
  "최신",
  "속보",
  "규제",
  "선거",
  "저작권",
  "해킹",
  "유출",
  "선언",
  "기본법",
  "딥페이크",
  "공정성",
  "할루시네이션",
]
const PAPER_HINTS = [
  "arxiv",
  "model",
  "transformer",
  "diffusion",
  "llm",
  "pre-training",
  "prompting",
  "retrieval",
  "generation",
  "bert",
  "gpt",
  "constitutional",
]
const ORG_SUFFIX = [
  "연구원",
  "연구회",
  "협회",
  "재단",
  "대학교",
  "대학",
  "청",
  "위원회",
  "센터",
  "진흥원",
  "평가원",
  "기술원",
  "안전처",
  "기획원",
  "정보원",
]
const TECH_HINTS = [
  "양자",
  "초전도",
  "데이터베이스",
  "학습",
  "칩",
  "프라이버시",
  "쿠버",
  "도커",
  "벡터",
  "rag",
  "트랜스포머",
  "뉴로모픽",
  "연합",
  "컨테이너",
  "아키텍처",
  "알고리즘",
  "네트워크",
  "반도체",
  "protein",
  "quantum",
]

const CHAIN: Record<string, string[]> = {
  기관명: [
    "wikipedia",
    "bing_web",
    "wikidata",
    "tavily",
    "duckduckgo",
    "you_search",
  ],
  기술용어: ["wikipedia", "bing_web", "tavily", "duckduckgo", "you_search"],
  entity: [
    "wikipedia",
    "bing_web",
    "wikidata",
    "tavily",
    "duckduckgo",
    "you_search",
  ],
  general: ["wikipedia", "bing_web", "tavily", "duckduckgo", "you_search"],
  "한국어 신조어": [
    "bing_define",
    "bing_news",
    "google_news",
    "wikipedia",
    "tavily",
    "duckduckgo",
    "you_search",
  ],
  "논문 제목": [
    "openalex",
    "crossref",
    "arxiv",
    "wikipedia",
    "bing_web",
    "duckduckgo",
    "you_search",
  ],
  "최신 AI뉴스나 논란": [
    "bing_news",
    "google_news",
    "gnews",
    "wikipedia",
    "duckduckgo_news",
    "tavily",
    "you_search",
  ],
}

const LABELS: Record<string, string> = {
  wikipedia: "Wikipedia (키 불필요)",
  openalex: "OpenAlex 논문 (키 불필요)",
  crossref: "Crossref 논문 (키 불필요)",
  wikidata: "Wikidata 개체 (키 불필요)",
  arxiv: "arXiv 논문 (키 불필요)",
  duckduckgo: "DuckDuckGo 일반 (키 불필요)",
  duckduckgo_news: "DuckDuckGo 뉴스 (키 불필요)",
  you_search: "You.com keyless (키 불필요)",
  tavily: "Tavily AI 검색 (keyless/무료키)",
  gnews: "GNews 뉴스 (무료키 100/일)",
  bing_web: "Bing 웹 RSS (키 불필요)",
  bing_define: "Bing 웹 RSS '뜻' 질의 (키 불필요)",
  bing_news: "Bing 뉴스 RSS (키 불필요)",
  google_news: "Google 뉴스 RSS (키 불필요)",
}

// ---------- 텍스트 유틸 (core.py norm/compact/en_tokens) ----------
const norm = (s?: string) => (s ?? "").normalize("NFKC").trim()
const compact = (s?: string) => norm(s).replace(/\s+/g, "").toLowerCase()
const hasHangul = (s: string) => /[가-힣]/.test(s)
const enTokens = (s: string) =>
  (s.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter(
    (t) => !EN_STOP.has(t) && (t.length > 1 || /\d/.test(t))
  )
const stripTags = (s: string) =>
  new DOMParser().parseFromString(s, "text/html").body.textContent?.trim() ?? ""

const SYN: Record<string, string[]> = {
  인공지능: ["ai"],
  머신러닝: ["machine", "learning"],
  딥러닝: ["deep", "learning"],
  챗봇: ["chatbot"],
  반도체: ["semiconductor", "chip"],
  양자: ["quantum"],
  초전도체: ["superconductor"],
  연합학습: ["federated", "learning"],
  차등: ["differential"],
  프라이버시: ["privacy"],
  생성형: ["generative"],
  신경망: ["neural", "network"],
  학습: ["learning"],
  데이터: ["data"],
  규제: ["regulation"],
  소송: ["lawsuit"],
  논란: ["controversy"],
  선거: ["election"],
  저작권: ["copyright"],
  해킹: ["hacking"],
  유출: ["leak"],
  기본법: ["act", "framework", "law"],
  시행: ["enforcement"],
  면접: ["interview"],
  채용: ["hiring"],
  공정성: ["fairness"],
  의료: ["medical"],
  사고: ["accident"],
  무단: ["unauthorized"],
  수집: ["collection"],
  오픈소스: ["open", "source"],
  모델: ["model"],
  거대언어모델: ["llm"],
  할루시네이션: ["hallucination"],
  딥페이크: ["deepfake"],
  벡터: ["vector"],
  데이터베이스: ["database"],
  아키텍처: ["architecture"],
}
const REV_SYN: Record<string, string[]> = {}
for (const [k, gl] of Object.entries(SYN))
  for (const g of gl) (REV_SYN[g] ??= []).push(k)

const variants = (qc: string) => {
  const v = new Set([qc])
  for (const [k, gl] of Object.entries(SYN))
    if (qc.includes(k)) for (const g of gl) v.add(qc.replaceAll(k, g))
  for (const [g, ks] of Object.entries(REV_SYN))
    if (qc.includes(g)) for (const k of ks) v.add(qc.replaceAll(g, k))
  return v
}
const bigrams = (s: string) =>
  new Set(
    Array.from({ length: Math.max(s.length - 1, 0) }, (_, i) =>
      s.slice(i, i + 2)
    )
  )

function scoreOne(
  qc: string,
  qt: string[],
  koToks: string[],
  vars: Set<string>,
  text: string,
  titleSide: boolean
) {
  const tc = compact(text)
  let sc = 0
  if (qc && [...vars].some((v) => v && (tc.includes(v) || v.includes(tc))))
    sc = 1
  const tt = enTokens(text)
  if (qt.length && tt.length) {
    let hit = 0
    for (const w of qt)
      if (
        tt.some(
          (x) =>
            w === x ||
            (w.length > 3 && w.length >= x.length - 2 && x.startsWith(w)) ||
            (x.length > 3 && x.length >= w.length - 2 && w.startsWith(x))
        )
      )
        hit++
    sc = Math.max(sc, hit / qt.length)
  }
  if (koToks.length) {
    let hit = 0
    for (const tok of koToks) {
      const gl = Object.entries(SYN)
        .filter(([k]) => tok.includes(k))
        .flatMap(([, g]) => g)
      if (tc.includes(compact(tok)) || gl.some((g) => tc.includes(g))) hit++
    }
    sc = Math.max(sc, hit / koToks.length)
  }
  if (qc.length >= 6) {
    const qb = bigrams(qc),
      tb = bigrams(tc)
    if (qb.size)
      sc = Math.max(
        sc,
        Math.min([...qb].filter((b) => tb.has(b)).length / qb.size, 0.75)
      )
  }
  if (!titleSide) sc = Math.min(sc, 0.5)
  return Math.round(sc * 1000) / 1000
}

function relevance(query: string, items: Item[], topk = 3) {
  const q = norm(query),
    qc = compact(q)
  let qt = enTokens(q)
  for (const [k, gl] of Object.entries(SYN))
    if (qc.includes(k)) qt = qt.concat(gl)
  const koToks = q
    .split(/\s+/)
    .filter((t) => hasHangul(t) && compact(t).length >= 2)
  const vars = variants(qc)
  let best = 0
  for (const it of items.slice(0, topk))
    best = Math.max(
      best,
      scoreOne(qc, qt, koToks, vars, norm(it.title), true),
      scoreOne(qc, qt, koToks, vars, norm(it.snippet), false)
    )
  return Math.round(best * 1000) / 1000
}

function classify(q: string) {
  const ql = q.toLowerCase()
  if (NEWS_KW.some((k) => q.includes(k)))
    return {
      category: "최신 AI뉴스나 논란",
      method: "rule:keyword-news",
      reason: "뉴스 키워드 포함",
    }
  const ascii =
    [...q].filter((c) => c.charCodeAt(0) < 128).length / Math.max(q.length, 1)
  const hinted = PAPER_HINTS.some((h) => ql.includes(h))
  if (
    (q.includes(":") && hinted) ||
    (q.split(/\s+/).length >= 6 && ascii > 0.6 && hinted)
  )
    return {
      category: "논문 제목",
      method: "rule:pattern-paper",
      reason: "영어 논문형 제목 패턴(콜론+학술키워드)",
    }
  if (ORG_SUFFIX.some((s) => q.endsWith(s)))
    return {
      category: "기관명",
      method: "rule:pattern-org",
      reason: "기관 접미사 패턴",
    }
  if (TECH_HINTS.some((h) => q.includes(h) || ql.includes(h)))
    return {
      category: "기술용어",
      method: "rule:keyword-tech",
      reason: "기술 키워드 포함",
    }
  const toks = q.split(/\s+/)
  if (toks.length >= 2 || (toks[0] && toks[0][0] !== toks[0][0].toLowerCase()))
    return {
      category: "entity",
      method: "rule:pattern-entity",
      reason: "복합어/대문자 개체명 패턴",
    }
  if (hasHangul(q) && q.length <= 6)
    return {
      category: "한국어 신조어",
      method: "rule:fallback-short-ko",
      reason: "짧은 한국어 (신조어 후보)",
    }
  return {
    category: "general",
    method: "rule:fallback-default",
    reason: "기본 일반 검색",
  }
}

// ---------- 가중 RRF (core.py fuse) ----------
const urlKey = (u?: string) => {
  try {
    const p = new URL(u ?? "")
    const host = p.host.toLowerCase().replace(/^www\./, "")
    return !host || host === "news.google.com"
      ? ""
      : host + p.pathname.replace(/\/$/, "")
  } catch {
    return ""
  }
}
const titleKey = (t?: string) =>
  compact(norm(t).replace(/\s[-–|]\s[^-–|]{1,30}$/, "")).slice(0, 60)

function fuse(
  packs: Record<string, [Item[], number]>,
  k = 60,
  limit = 10
): Item[] {
  const ents: { item: Item; score: number; sources: string[] }[] = []
  const idx = new Map<string, (typeof ents)[number]>()
  for (const [tool, [items, sc]] of Object.entries(packs)) {
    const w = Math.max(sc, 0.1)
    items.forEach((it, rank) => {
      const keys = [urlKey(it.url), titleKey(it.title)].filter(Boolean)
      let e = keys.map((x) => idx.get(x)).find(Boolean)
      if (!e) ents.push((e = { item: { ...it }, score: 0, sources: [] }))
      e.score += w / (k + rank + 1)
      if (!e.sources.includes(tool)) e.sources.push(tool)
      if ((it.snippet?.length ?? 0) > (e.item.snippet?.length ?? 0))
        e.item.snippet = it.snippet
      for (const x of keys) if (!idx.has(x)) idx.set(x, e)
    })
  }
  return ents
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((e) => ({ ...e.item, sources: e.sources }))
}

// ---------- 브라우저에서 호출 가능한 엔진 (CORS 허용) ----------
async function getJson(url: string, signal: AbortSignal) {
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
const qs = (o: Record<string, string | number>) =>
  new URLSearchParams(
    Object.fromEntries(Object.entries(o).map(([k, v]) => [k, String(v)]))
  ).toString()

type Raw = Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any

async function wikiLang(
  q: string,
  lang: string,
  signal: AbortSignal
): Promise<Item[]> {
  const d = await getJson(
    `https://${lang}.wikipedia.org/w/api.php?` +
      qs({
        action: "query",
        list: "search",
        srsearch: q,
        format: "json",
        formatversion: 2,
        srlimit: 8,
        origin: "*",
      }),
    signal
  )
  return (d.query?.search ?? []).map((r: Raw) => ({
    title: r.title,
    url:
      `https://${lang}.wikipedia.org/wiki/` +
      encodeURIComponent(String(r.title).replaceAll(" ", "_")),
    snippet: stripTags(r.snippet ?? ""),
  }))
}

const LIVE: Record<string, (q: string, s: AbortSignal) => Promise<Item[]>> = {
  async wikipedia(q, s) {
    const langs = hasHangul(q) ? ["ko", "en"] : ["en", "ko"]
    const got = await Promise.allSettled(langs.map((l) => wikiLang(q, l, s)))
    const out = got.flatMap((r) => (r.status === "fulfilled" ? r.value : []))
    if (!out.length && got[0].status === "rejected") throw got[0].reason
    return out
  },
  async wikidata(q, s) {
    const lang = hasHangul(q) ? "ko" : "en"
    const d = await getJson(
      "https://www.wikidata.org/w/api.php?" +
        qs({
          action: "wbsearchentities",
          search: q,
          language: lang,
          uselang: lang,
          limit: 8,
          format: "json",
          origin: "*",
        }),
      s
    )
    return (d.search ?? []).map((e: Raw) => ({
      title: e.label ?? "",
      url: "https://www.wikidata.org/wiki/" + e.id,
      snippet: e.description ?? "",
    }))
  },
  async openalex(q, s) {
    const d = await getJson(
      "https://api.openalex.org/works?" +
        qs({
          search: q,
          "per-page": 8,
          select: "id,title,doi,publication_year,cited_by_count,authorships",
        }),
      s
    )
    return (d.results ?? []).map((w: Raw) => ({
      title: w.title ?? "",
      url: w.doi || w.id || "",
      snippet: `${w.publication_year ?? "?"}년 · 인용 ${w.cited_by_count ?? 0}회 · ${(
        w.authorships ?? []
      )
        .slice(0, 3)
        .map((a: Raw) => a.author?.display_name ?? "")
        .join(", ")}`,
    }))
  },
  async crossref(q, s) {
    const d = await getJson(
      "https://api.crossref.org/works?" +
        qs({
          "query.bibliographic": q,
          rows: 8,
          select: "title,DOI,URL,issued,is-referenced-by-count",
        }),
      s
    )
    return (d.message?.items ?? []).map((w: Raw) => ({
      title: (w.title ?? []).join(" "),
      url: w.URL ?? "",
      snippet: `${w.issued?.["date-parts"]?.[0]?.[0] ?? "?"}년 · 인용 ${w["is-referenced-by-count"] ?? 0}회`,
    }))
  },
}

async function runOne(
  tool: string,
  q: string
): Promise<Pack & { score: number }> {
  const label = LABELS[tool] ?? tool
  const run = LIVE[tool]
  if (!run)
    return {
      label,
      items: [],
      score: 0,
      status: "unavailable",
      detail: "브라우저에서는 CORS로 호출 불가 (pip 버전에서 사용)",
    }
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), DEADLINE_MS)
  try {
    const items = (await run(q, ctl.signal)).filter((x) => norm(x.title))
    return {
      label,
      items: items.slice(0, 10),
      score: relevance(q, items),
      status: "ok",
    }
  } catch (e) {
    return ctl.signal.aborted
      ? {
          label,
          items: [],
          score: 0,
          status: "timeout",
          detail: `>${DEADLINE_MS / 1000}s`,
        }
      : {
          label,
          items: [],
          score: 0,
          status: "error",
          detail: String(e instanceof Error ? e.message : e).slice(0, 120),
        }
  } finally {
    clearTimeout(timer)
  }
}

export async function demoSmartSearch(query: string): Promise<Smart> {
  const t0 = performance.now()
  const q = norm(query)
  const route = classify(q)
  const chain = CHAIN[route.category] ?? CHAIN.general
  const done = await Promise.all(
    chain.map(async (t) => [t, await runOne(t, q)] as const)
  )
  const tools = Object.fromEntries(done)
  const order = [...chain].sort((a, b) => tools[b].score - tools[a].score)
  const fusable = Object.fromEntries(
    Object.entries(tools)
      .filter(
        ([, p]) => p.status === "ok" && p.items.length && p.score >= FUSE_MIN
      )
      .map(([t, p]) => [t, [p.items, p.score] as [Item[], number]])
  )
  return {
    query: q,
    route: { ...route, tools: chain },
    fused: fuse(fusable),
    results_by_tool: Object.fromEntries(
      Object.entries(tools).map(([t, p]) => [
        t,
        { label: p.label, items: p.items, status: p.status, detail: p.detail },
      ])
    ),
    scores: Object.fromEntries(
      Object.entries(tools).map(([t, p]) => [t, p.score])
    ),
    order,
    elapsed: Math.round((performance.now() - t0) / 100) / 10,
  }
}

export const demoCategories = () => Object.keys(WORD_LISTS)
export const demoRandomWord = (category?: string) => {
  const cat =
    category && WORD_LISTS[category]
      ? category
      : Object.keys(WORD_LISTS)[
          Math.floor(Math.random() * Object.keys(WORD_LISTS).length)
        ]
  const list = WORD_LISTS[cat]
  return { category: cat, word: list[Math.floor(Math.random() * list.length)] }
}
