import type { CSSProperties } from "react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

// 엔진마다 고유 색 점. 알려진 엔진은 순서대로 황금각(137.5°)만큼 띄워 겹치지 않게
// 배정하고, 모르는 엔진은 이름 해시로 정한다.
const KNOWN = [
  "wikipedia",
  "wikidata",
  "bing_web",
  "bing_define",
  "bing_news",
  "google_news",
  "openalex",
  "crossref",
  "arxiv",
  "duckduckgo",
  "duckduckgo_news",
  "tavily",
  "you_search",
  "gnews",
  "stackexchange",
  "huggingface",
  "searxng",
  "searxng_news",
  "semantic_scholar",
  "gdelt",
  "marginalia",
]

const hue = (name: string) => {
  const i = KNOWN.indexOf(name)
  const n =
    i >= 0 ? i : [...name].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7)
  return (n * 137.508) % 360
}

/** "Wikipedia (키 불필요)" -> "Wikipedia" */
export const shortLabel = (label: string) => label.replace(/\s*\(.*\)\s*$/, "")

export function EngineDot({
  name,
  off,
  className,
}: {
  name: string
  off?: boolean
  className?: string
}) {
  return (
    <span
      aria-hidden
      style={{ "--h": hue(name) } as CSSProperties}
      className={cn(
        "size-2 shrink-0 rounded-full border border-[oklch(0.62_0.16_var(--h))] bg-[oklch(0.62_0.16_var(--h))] dark:border-[oklch(0.78_0.13_var(--h))] dark:bg-[oklch(0.78_0.13_var(--h))]",
        off && "bg-transparent dark:bg-transparent",
        className
      )}
    />
  )
}

/** 관련도(0~1) 막대. 엔진 색을 쓰고, 처음 그려질 때 0에서 차오른다. */
export function Meter({ name, value }: { name: string; value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <span
      aria-hidden
      className="block h-[3px] w-full overflow-hidden rounded-full bg-foreground/10"
    >
      <span
        style={{ "--h": hue(name), "--w": `${pct}%` } as CSSProperties}
        className="block h-full w-(--w) rounded-full bg-[oklch(0.62_0.16_var(--h))] transition-[width] duration-700 ease-out dark:bg-[oklch(0.78_0.13_var(--h))] starting:w-0"
      />
    </span>
  )
}

export function EngineBadge({ name, label }: { name: string; label: string }) {
  return (
    <Badge
      variant="outline"
      className="h-5 gap-1.5 px-1.5 text-[0.7rem] font-normal text-muted-foreground"
    >
      <EngineDot name={name} />
      {shortLabel(label)}
    </Badge>
  )
}
