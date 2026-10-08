import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"

import {
  EmptyState,
  ErrorState,
  ImageGrid,
  ResultList,
  RowsSkeleton,
} from "@/components/results"
import { SearchPanel } from "@/components/search-panel"
import { Footer, Header, Hero, Steps } from "@/components/site"
import { SmartResults, SmartSkeleton } from "@/components/smart-results"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import {
  DEMO,
  ddgSearch,
  randomWord,
  smartSearch,
  wordCategories,
  type DdgType,
  type Item,
  type Mode,
  type Smart,
} from "@/lib/api"

type Run =
  | { s: "idle" }
  | { s: "loading" }
  | { s: "error"; msg: string }
  | { s: "smart"; data: Smart; id: number }
  | { s: "ddg"; type: DdgType; items: Item[] }

const DDG_TABS: [DdgType, string][] = [
  ["text", "일반"],
  ["images", "이미지"],
  ["news", "뉴스"],
  ["videos", "비디오"],
]

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function App() {
  const [q, setQ] = useState("")
  const [last, setLast] = useState("") // 마지막으로 검색한 질의: 탭 전환 시 재검색에 쓴다
  const [mode, setMode] = useState<Mode>("smart")
  const [type, setType] = useState<DdgType>("text")
  const [run, setRun] = useState<Run>({ s: "idle" })
  const [categories, setCategories] = useState<string[]>([])
  const seq = useRef(0)
  const cache = useRef(new Map<string, Run>())

  useEffect(() => {
    wordCategories()
      .then(setCategories)
      .catch(() => {})
  }, [])

  // cached=true 는 탭 전환용: 이미 받은 결과가 있으면 다시 호출하지 않는다.
  const go = useCallback(
    async (query: string, m: Mode, t: DdgType, cached = false) => {
      const key = `${m}|${t}|${query}`
      const id = ++seq.current
      setLast(query)
      const hit = cached ? cache.current.get(key) : undefined
      if (hit) return setRun(hit)
      setRun({ s: "loading" })
      try {
        const next: Run =
          m === "smart"
            ? { s: "smart", data: await smartSearch(query), id }
            : { s: "ddg", type: t, items: await ddgSearch(query, t) }
        cache.current.set(key, next)
        if (id === seq.current) setRun(next)
      } catch (e) {
        if (id === seq.current) setRun({ s: "error", msg: errMsg(e) })
      }
    },
    []
  )

  useEffect(() => {
    document.title = last ? `${last} — omniSearch` : "omniSearch"
  }, [last])

  const start = (query: string) => {
    window.scrollTo({ top: 0 })
    go(query, mode, type)
  }
  const submit = () => q.trim() && start(q.trim())
  const switchMode = (m: Mode) => {
    setMode(m)
    if (last) go(last, m, type, true)
  }
  const switchType = (t: DdgType) => {
    setType(t)
    go(last, mode, t, true)
  }
  const random = async (category?: string) => {
    try {
      const word = (await randomWord(category)).word.trim()
      setQ(word)
      start(word)
    } catch (e) {
      setLast("랜덤 질의")
      setRun({ s: "error", msg: errMsg(e) })
    }
  }

  const searched = run.s !== "idle"
  let body: ReactNode = null
  let status = ""
  if (run.s === "loading") {
    status = "검색 중"
    body =
      mode === "smart" ? (
        <SmartSkeleton />
      ) : type === "images" ? (
        <div
          className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
          aria-hidden
        >
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="aspect-[4/3] rounded-lg" />
          ))}
        </div>
      ) : (
        <RowsSkeleton />
      )
  } else if (run.s === "error") {
    status = run.msg
    body = <ErrorState message={run.msg} onRetry={() => go(last, mode, type)} />
  } else if (run.s === "smart") {
    status = `통합 결과 ${run.data.fused.length}건`
    body = <SmartResults key={run.id} data={run.data} />
  } else if (run.s === "ddg") {
    status = `${run.items.length}건`
    body = !run.items.length ? (
      <EmptyState title="결과가 없습니다">
        다른 검색어로 다시 시도해 보세요.
      </EmptyState>
    ) : run.type === "images" ? (
      <ImageGrid items={run.items} />
    ) : (
      <ResultList items={run.items} />
    )
  }

  return (
    <>
      {DEMO && (
        <p className="bg-primary px-4 py-2 text-center text-xs text-primary-foreground">
          브라우저 데모 — 서버·키 없이 CORS가 허용된 Wikipedia · Wikidata ·
          OpenAlex · Crossref만 호출합니다. 전체 엔진은{" "}
          <a
            href="https://github.com/Goldhobbang/omniSearch#install"
            className="underline underline-offset-2"
          >
            pip 설치 버전
          </a>
          에서 쓸 수 있습니다.
        </p>
      )}
      <Header />
      <main className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        {!searched && <Hero />}
        <SearchPanel
          q={q}
          onQ={setQ}
          mode={mode}
          onMode={switchMode}
          categories={categories}
          onRandom={random}
          onSubmit={submit}
          loading={run.s === "loading"}
        />
        <p role="status" className="sr-only">
          {status}
        </p>
        {searched ? (
          <section className="mt-10 sm:mt-12">
            <div className="mb-6 sm:mb-8">
              <p className="eyebrow">
                Results · {mode === "smart" ? "Smart routing" : "DuckDuckGo"}
              </p>
              <h1
                className={cn(
                  "mt-3 font-display leading-[1.05] tracking-tight text-balance",
                  last.length > 36
                    ? "text-2xl sm:text-4xl"
                    : "text-4xl sm:text-5xl"
                )}
              >
                {last}
              </h1>
            </div>
            {mode === "ddg" && (
              <Tabs
                value={type}
                onValueChange={(v) => switchType(v as DdgType)}
                className="mb-4"
              >
                <div className="flex items-center justify-between gap-4">
                  <TabsList>
                    {DDG_TABS.map(([v, label]) => (
                      <TabsTrigger key={v} value={v} className="px-3">
                        {label}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  {run.s === "ddg" && (
                    <span className="shrink-0 font-mono text-xs whitespace-nowrap text-muted-foreground tabular-nums">
                      {run.items.length}건
                      <span className="hidden sm:inline"> · duckduckgo</span>
                    </span>
                  )}
                </div>
              </Tabs>
            )}
            {body}
          </section>
        ) : (
          <Steps />
        )}
      </main>
      <Footer />
    </>
  )
}
