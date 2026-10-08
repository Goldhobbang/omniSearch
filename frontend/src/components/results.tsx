import type { ComponentType } from "react"
import { CircleAlertIcon, RotateCwIcon, SearchXIcon } from "lucide-react"

import { EngineBadge } from "@/components/engine"
import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import type { Item } from "@/lib/api"

function hostPath(url?: string) {
  if (!url) return null
  try {
    const u = new URL(url)
    return {
      host: u.host.replace(/^www\./, ""),
      path: decodeURI(u.pathname + u.search).replace(/\/$/, ""),
    }
  } catch {
    return { host: url, path: "" }
  }
}

function Row({
  item,
  rank,
  labels,
}: {
  item: Item
  rank: number
  labels?: Record<string, string>
}) {
  const u = hostPath(item.url)
  const src = item.sources ?? []
  return (
    <li
      style={{ animationDelay: `${Math.min(rank - 1, 10) * 35}ms` }}
      className="group/row relative flex gap-3 px-4 py-4 transition-colors fill-mode-both hover:bg-accent/40 has-[a:focus-visible]:bg-accent/40 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-1 sm:gap-4 sm:px-5"
    >
      <span className="w-6 shrink-0 pt-px text-right font-display text-2xl leading-none text-muted-foreground/70 tabular-nums">
        {rank}
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <h3 className="leading-snug font-medium text-pretty">
          {item.url ? (
            // 마우스: 제목만 링크(스니펫 드래그 선택 가능). 터치: 행 전체가 눌리는 영역.
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="outline-none group-hover/row:text-primary focus-visible:text-primary focus-visible:underline pointer-coarse:after:absolute pointer-coarse:after:inset-0"
            >
              {item.title}
            </a>
          ) : (
            item.title
          )}
        </h3>
        {u && (
          <p className="truncate font-mono text-xs text-muted-foreground">
            {u.host}
            <span className="opacity-60">{u.path}</span>
          </p>
        )}
        {item.snippet && (
          <p className="line-clamp-3 text-sm/relaxed text-pretty text-muted-foreground">
            {item.snippet}
          </p>
        )}
        {item.meta && (
          <p className="font-mono text-xs text-muted-foreground">{item.meta}</p>
        )}
        {src.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {src.length > 1 && (
              <Badge className="h-5 bg-primary/10 text-[0.7rem] text-primary-ink">
                {src.length}개 엔진 일치
              </Badge>
            )}
            {src.map((s) => (
              <EngineBadge key={s} name={s} label={labels?.[s] ?? s} />
            ))}
          </div>
        )}
      </div>
      {item.thumb && (
        <img
          src={item.thumb}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          className="hidden aspect-video w-32 shrink-0 self-start rounded-md bg-muted object-cover sm:block"
        />
      )}
    </li>
  )
}

export function ResultList({
  items,
  labels,
}: {
  items: Item[]
  labels?: Record<string, string>
}) {
  return (
    <Card className="gap-0 py-0">
      <ul className="divide-y">
        {items.map((it, i) => (
          <Row
            key={`${it.url ?? it.title}-${i}`}
            item={it}
            rank={i + 1}
            labels={labels}
          />
        ))}
      </ul>
    </Card>
  )
}

export function ImageGrid({ items }: { items: Item[] }) {
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {items.map((it, i) => (
        <li
          key={`${it.url ?? it.title}-${i}`}
          style={{ animationDelay: `${Math.min(i, 12) * 30}ms` }}
          className="group/img relative overflow-hidden rounded-lg bg-card ring-1 ring-foreground/10 transition-shadow fill-mode-both hover:ring-primary/50 motion-safe:animate-in motion-safe:zoom-in-95 motion-safe:fade-in"
        >
          <div className="aspect-[4/3] overflow-hidden bg-muted">
            {it.thumb && (
              <img
                src={it.thumb}
                alt=""
                loading="lazy"
                referrerPolicy="no-referrer"
                className="size-full object-cover transition-transform duration-300 group-hover/img:scale-[1.04]"
              />
            )}
          </div>
          <div className="space-y-1 p-2.5">
            <h3 className="line-clamp-2 text-xs/snug font-medium">
              {it.url ? (
                <a
                  href={it.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="outline-none after:absolute after:inset-0 focus-visible:underline"
                >
                  {it.title}
                </a>
              ) : (
                it.title
              )}
            </h3>
            {it.meta && (
              <p className="truncate font-mono text-[0.68rem] text-muted-foreground">
                {it.meta}
              </p>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

export function EmptyState({
  icon: Icon = SearchXIcon,
  title,
  children,
}: {
  icon?: ComponentType
  title: string
  children?: React.ReactNode
}) {
  return (
    <Empty className="border bg-card/50">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        {children && <EmptyDescription>{children}</EmptyDescription>}
      </EmptyHeader>
    </Empty>
  )
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string
  onRetry: () => void
}) {
  return (
    <Alert variant="destructive">
      <CircleAlertIcon />
      <AlertTitle>검색에 실패했습니다</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
      <AlertAction>
        <Button size="xs" variant="outline" onClick={onRetry}>
          <RotateCwIcon />
          다시 시도
        </Button>
      </AlertAction>
    </Alert>
  )
}

export function RowsSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <Card className="gap-0 py-0" aria-hidden>
      <ul className="divide-y">
        {Array.from({ length: rows }, (_, i) => (
          <li key={i} className="flex gap-4 px-5 py-4">
            <Skeleton className="h-6 w-6 shrink-0" />
            <div className="flex-1 space-y-2.5">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
