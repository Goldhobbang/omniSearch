export type Mode = "smart" | "ddg"
export type DdgType = "text" | "images" | "news" | "videos"

export type Item = {
  title: string
  url?: string
  snippet?: string
  meta?: string
  thumb?: string
  /** 융합 결과에서 이 문서를 올린 엔진들 */
  sources?: string[]
}

export type Pack = {
  label: string
  items: Item[]
  status?: "ok" | "timeout" | "unavailable" | "error"
  detail?: string
}

export type Smart = {
  query: string
  route: { category: string; method: string; reason: string; tools: string[] }
  fused: Item[]
  results_by_tool: Record<string, Pack>
  scores: Record<string, number | null>
  order: string[]
  elapsed?: number
}

/** GitHub Pages 데모 빌드(`vite build --mode demo`): 서버 없이 브라우저에서 직접 검색 */
export const DEMO = import.meta.env.MODE === "demo"

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}

// 검색 결과는 외부 콘텐츠다: http(s) 링크만 허용한다 (javascript: 등 차단).
const http = (u?: string) => (u && /^https?:\/\//i.test(u) ? u : undefined)
const safe = (it: Item): Item => ({
  ...it,
  url: http(it.url),
  thumb: http(it.thumb),
})

export async function smartSearch(q: string): Promise<Smart> {
  const d = DEMO
    ? await import("./demo").then((m) => m.demoSmartSearch(q))
    : await getJson<Smart>(`/api/smart-search?q=${encodeURIComponent(q)}`)
  return {
    ...d,
    fused: (d.fused ?? []).map(safe),
    results_by_tool: Object.fromEntries(
      Object.entries(d.results_by_tool ?? {}).map(([t, p]) => [
        t,
        { ...p, items: p.items.map(safe) },
      ])
    ),
  }
}

interface Raw {
  title?: string
  href?: string
  url?: string
  body?: string
  image?: string
  thumbnail?: string
  source?: string
  date?: string
  width?: number
  height?: number
  content?: string
  description?: string
  duration?: string
  published?: string
  publisher?: string
  uploader?: string
  statistics?: { viewCount?: number }
  images?: Record<string, string>
}

const day = (s?: string) => {
  const d = s ? new Date(s) : null
  return d && !isNaN(+d)
    ? d.toLocaleDateString("ko-KR", { dateStyle: "medium" })
    : s
}
const compact = new Intl.NumberFormat("ko-KR", { notation: "compact" })
const join = (...p: unknown[]) => p.filter(Boolean).join(" · ")

const TO_ITEM: Record<DdgType, (r: Raw) => Item> = {
  text: (r) => ({ title: r.title ?? "", url: r.href, snippet: r.body }),
  news: (r) => ({
    title: r.title ?? "",
    url: r.url,
    snippet: r.body,
    meta: join(r.source, day(r.date)),
    thumb: r.image,
  }),
  images: (r) => ({
    title: r.title ?? "",
    url: r.url,
    thumb: r.thumbnail || r.image,
    meta: join(r.source, r.width && r.height && `${r.width}×${r.height}`),
  }),
  videos: (r) => ({
    title: r.title ?? "",
    url: r.content,
    snippet: r.description,
    meta: join(
      r.duration,
      r.publisher || r.uploader,
      day(r.published),
      r.statistics?.viewCount != null &&
        `조회 ${compact.format(r.statistics.viewCount)}`
    ),
    thumb: r.images?.medium || r.images?.small || r.images?.large,
  }),
}

export async function ddgSearch(q: string, type: DdgType): Promise<Item[]> {
  const d = await getJson<{ results: Raw[] }>(
    `/api/search?q=${encodeURIComponent(q)}&type=${type}`
  )
  return d.results.map((r) => safe(TO_ITEM[type](r)))
}

export const wordCategories = () =>
  DEMO
    ? import("./demo").then((m) => m.demoCategories())
    : getJson<Record<string, string[]>>("/api/word-lists").then(Object.keys)

export const randomWord = (category?: string) =>
  DEMO
    ? import("./demo").then((m) => m.demoRandomWord(category))
    : getJson<{ category: string; word: string }>(
        "/api/random-word" +
          (category ? `?category=${encodeURIComponent(category)}` : "")
      )
