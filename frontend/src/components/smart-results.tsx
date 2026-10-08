import { useState, useSyncExternalStore, type ReactNode } from "react"
import {
  LayersIcon,
  PlugZapIcon,
  RouteIcon,
  TimerIcon,
  TimerOffIcon,
  TriangleAlertIcon,
} from "lucide-react"

import { EngineDot, Meter, shortLabel } from "@/components/engine"
import { EmptyState, ResultList, RowsSkeleton } from "@/components/results"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Pack, Smart } from "@/lib/api"

// lg 이상에서는 엔진 목록이 세로 사이드바, 그 미만에서는 가로 스크롤 칩이 된다.
const WIDE = "(min-width: 1024px)"
const subscribe = (cb: () => void) => {
  const m = matchMedia(WIDE)
  m.addEventListener("change", cb)
  return () => m.removeEventListener("change", cb)
}
const useWide = () =>
  useSyncExternalStore(
    subscribe,
    () => matchMedia(WIDE).matches,
    () => true
  )

const STATUS = {
  timeout: {
    text: "시간 초과",
    icon: TimerOffIcon,
    title: "응답이 늦어 이번 검색에서는 제외됐습니다",
    hint: "엔진은 백그라운드에서 계속 실행되어, 끝나면 결과가 캐시에 쌓입니다.",
  },
  unavailable: {
    text: "사용 불가",
    icon: PlugZapIcon,
    title: "지금은 사용할 수 없는 엔진입니다",
    hint: "쿨다운 중이거나 쿼터를 다 썼거나, 키가 필요한 상태일 수 있습니다.",
  },
  error: {
    text: "오류",
    icon: TriangleAlertIcon,
    title: "엔진 호출에 실패했습니다",
    hint: "",
  },
} as const

/** 정상(또는 status 없음)이면 null, 아니면 상태 설명 */
const problem = (p: Pack) =>
  !p.status || p.status === "ok" ? null : STATUS[p.status]

function PanelHead({
  title,
  desc,
  count,
}: {
  title: ReactNode
  desc: string
  count: number
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-4">
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 text-lg font-medium tracking-tight">
          {title}
        </h2>
        <p className="mt-0.5 text-sm text-muted-foreground">{desc}</p>
      </div>
      <Badge variant="secondary" className="shrink-0 font-mono tabular-nums">
        {count}건
      </Badge>
    </div>
  )
}

const TRIGGER =
  "h-auto min-w-52 shrink-0 flex-col items-stretch gap-1.5 px-2.5 py-2 text-left lg:w-full lg:min-w-0"

export function SmartResults({ data }: { data: Smart }) {
  const wide = useWide()
  const { route, fused, results_by_tool: packs } = data
  const order = (data.order?.length ? data.order : Object.keys(packs)).filter(
    (t) => packs[t]
  )
  const labels = Object.fromEntries(order.map((t) => [t, packs[t].label]))
  const score = (t: string) => data.scores?.[t] ?? 0
  const [sel, setSel] = useState(() =>
    fused.length
      ? "fused"
      : (order.find((t) => packs[t].items.length) ?? "fused")
  )
  const merged = new Set(fused.flatMap((f) => f.sources ?? [])).size

  return (
    <Tabs
      value={sel}
      onValueChange={setSel}
      orientation={wide ? "vertical" : "horizontal"}
      className="gap-5 lg:grid lg:grid-cols-[17.5rem_minmax(0,1fr)] lg:items-start lg:gap-8"
    >
      <aside className="min-w-0 space-y-3 lg:sticky lg:top-6">
        <Card size="sm" className="gap-3">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <RouteIcon className="size-4 text-primary" />
              라우팅
            </CardTitle>
            {data.elapsed != null && (
              <CardAction className="flex items-center gap-1 font-mono text-xs text-muted-foreground tabular-nums">
                <TimerIcon className="size-3.5" />
                {data.elapsed}s
              </CardAction>
            )}
          </CardHeader>
          <CardContent className="gap-2.5">
            <div className="flex flex-wrap gap-1.5">
              <Badge>{route.category}</Badge>
              <Badge variant="outline" className="font-mono font-normal">
                {route.method}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">{route.reason}</p>
          </CardContent>
        </Card>

        <TabsList className="w-full [scrollbar-width:none] justify-start gap-0.5 overflow-x-auto group-data-horizontal/tabs:h-auto lg:flex-col lg:items-stretch lg:overflow-visible">
          <TabsTrigger value="fused" className={TRIGGER}>
            <span className="flex w-full items-center gap-2">
              <LayersIcon className="size-3.5 text-primary" />
              <span className="flex-1 text-left">통합 결과</span>
              <span className="font-mono text-[0.7rem] text-muted-foreground tabular-nums">
                {fused.length}
              </span>
            </span>
            <span className="text-[0.7rem] font-normal text-muted-foreground">
              가중 RRF 융합 · 엔진 {merged}개
            </span>
          </TabsTrigger>
          {order.map((t) => {
            const p = packs[t]
            const bad = problem(p)
            return (
              <TabsTrigger key={t} value={t} className={TRIGGER}>
                <span className="flex w-full items-center gap-2">
                  <EngineDot name={t} off={!!bad} />
                  <span className="min-w-0 flex-1 truncate text-left">
                    {shortLabel(p.label)}
                  </span>
                  <span className="font-mono text-[0.7rem] text-muted-foreground tabular-nums">
                    {bad ? bad.text : score(t).toFixed(2)}
                  </span>
                </span>
                <Meter name={t} value={bad ? 0 : score(t)} />
              </TabsTrigger>
            )
          })}
        </TabsList>
      </aside>

      <section className="min-w-0">
        <TabsContent value="fused">
          <PanelHead
            title="통합 결과"
            desc="여러 엔진이 함께 올린 문서가 위로 올라옵니다."
            count={fused.length}
          />
          {fused.length ? (
            <ResultList items={fused} labels={labels} />
          ) : (
            <EmptyState title="융합할 결과가 없습니다">
              관련도 0.4 이상인 엔진이 없어 통합 순위를 만들지 못했습니다.
              왼쪽에서 엔진별 결과를 확인하세요.
            </EmptyState>
          )}
        </TabsContent>

        {order.map((t) => {
          const p = packs[t]
          const s = problem(p)
          return (
            <TabsContent key={t} value={t}>
              <PanelHead
                title={
                  <>
                    <EngineDot name={t} off={!!s} className="size-2.5" />
                    {shortLabel(p.label)}
                  </>
                }
                desc={
                  s
                    ? [s.text, p.detail].filter(Boolean).join(" · ")
                    : `관련도 ${score(t).toFixed(2)} · ${p.label.match(/\((.*)\)/)?.[1] ?? "키 불필요"}`
                }
                count={p.items.length}
              />
              {p.items.length ? (
                <ResultList items={p.items} />
              ) : (
                <EmptyState
                  icon={s?.icon}
                  title={s?.title ?? "이 엔진은 결과를 주지 않았습니다"}
                >
                  {s?.hint}
                </EmptyState>
              )}
            </TabsContent>
          )
        })}
      </section>
    </Tabs>
  )
}

export function SmartSkeleton() {
  return (
    <div
      aria-hidden
      className="grid gap-5 lg:grid-cols-[17.5rem_minmax(0,1fr)] lg:gap-8"
    >
      <div className="space-y-3">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-14 rounded-lg lg:h-60" />
      </div>
      <RowsSkeleton />
    </div>
  )
}
