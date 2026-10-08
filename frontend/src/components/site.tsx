import { MoonIcon, RouteIcon, SunIcon } from "lucide-react"

import { EngineDot, Meter } from "@/components/engine"
import { useTheme } from "@/components/theme-provider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

const REVEAL =
  "fill-mode-both duration-700 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-3"
const delay = (i: number) => ({ animationDelay: `${i * 90}ms` })

function LogoMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="size-6">
      <g className="origin-center transition-transform duration-700 ease-out group-hover/logo:rotate-120">
        <circle
          cx="12"
          cy="12"
          r="9"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          opacity=".3"
        />
        <circle cx="12" cy="3" r="1.9" className="fill-primary" />
        <circle cx="19.8" cy="16.5" r="1.9" className="fill-primary" />
        <circle cx="4.2" cy="16.5" r="1.9" className="fill-primary" />
      </g>
      <circle cx="12" cy="12" r="4.2" className="fill-primary" />
    </svg>
  )
}

function ThemeToggle() {
  const { setTheme } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="테마 전환"
      title="테마 전환 (D)"
      onClick={() =>
        setTheme(
          document.documentElement.classList.contains("dark") ? "light" : "dark"
        )
      }
    >
      <SunIcon className="dark:hidden" />
      <MoonIcon className="hidden dark:block" />
    </Button>
  )
}

export function Header() {
  return (
    <header className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
      <a
        href="./"
        className="group/logo flex items-center gap-2.5"
        aria-label="omniSearch 홈"
      >
        <LogoMark />
        <span className="font-display text-[1.65rem] leading-none tracking-tight">
          <i>omni</i>Search
        </span>
      </a>
      <ThemeToggle />
    </header>
  )
}

// 정적 예시(실제 검색 결과 아님): 결과 화면이 어떤 모양인지 첫 화면에서 미리 보여준다.
const SAMPLE = [
  { k: "bing_define", label: "Bing 웹 RSS '뜻' 질의", score: 1 },
  { k: "bing_news", label: "Bing 뉴스 RSS", score: 1 },
  { k: "google_news", label: "Google 뉴스 RSS", score: 1 },
  { k: "wikipedia", label: "Wikipedia", score: 0.5 },
  { k: "tavily", label: "Tavily AI 검색", score: 0, off: "사용 불가" },
]

function Preview() {
  return (
    <Card
      size="sm"
      aria-hidden
      style={delay(3)}
      className={cn("hidden gap-3.5 shadow-lg lg:flex", REVEAL)}
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <RouteIcon className="size-4 text-primary" />
          예시 · “갓생”
        </CardTitle>
        <CardAction className="font-mono text-xs text-muted-foreground">
          1.8s
        </CardAction>
      </CardHeader>
      <CardContent className="gap-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge>한국어 신조어</Badge>
          <Badge variant="outline" className="font-mono font-normal">
            rule:fallback-short-ko
          </Badge>
        </div>
        <ul className="space-y-3">
          {SAMPLE.map((e) => (
            <li key={e.k} className="space-y-1.5">
              <div className="flex items-center gap-2 text-sm">
                <EngineDot name={e.k} off={!!e.off} />
                <span className="flex-1 truncate">{e.label}</span>
                <span className="font-mono text-xs text-muted-foreground tabular-nums">
                  {e.off ?? e.score.toFixed(2)}
                </span>
              </div>
              <Meter name={e.k} value={e.score} />
            </li>
          ))}
        </ul>
      </CardContent>
      <Separator />
      <CardFooter className="gap-3">
        <span className="font-display text-2xl leading-none text-muted-foreground/70">
          1
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">갓생 - 나무위키</p>
          <p className="truncate font-mono text-xs text-muted-foreground">
            namu.wiki/w/갓생
          </p>
        </div>
        <Badge className="bg-primary/10 text-primary-ink">2개 엔진 일치</Badge>
      </CardFooter>
    </Card>
  )
}

export function Hero() {
  return (
    <section className="grid items-end gap-10 pt-8 pb-8 sm:pt-14 sm:pb-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:gap-14">
      <div>
        <p className={cn("eyebrow", REVEAL)}>Keyless hybrid search router</p>
        <h1
          lang="en"
          style={delay(1)}
          className={cn(
            "mt-5 font-display text-[3.25rem] leading-[0.92] tracking-tight text-balance sm:text-7xl",
            REVEAL
          )}
        >
          Ask once.
          <br />
          <i className="text-primary">Search everywhere.</i>
        </h1>
        <p
          style={delay(2)}
          className={cn(
            "mt-6 max-w-xl text-base/relaxed text-pretty text-muted-foreground sm:text-lg/relaxed",
            REVEAL
          )}
        >
          규칙 분류기가 질의 종류를 판단하고, API 키가 필요 없는 엔진 여러 개를
          동시에 실행해 하나의 순위로 융합합니다.
        </p>
      </div>
      <Preview />
    </section>
  )
}

const STEPS = [
  {
    n: "01",
    title: "분류",
    body: "규칙 분류기가 질의를 기관명 · 기술용어 · 신조어 · 논문 제목 · 뉴스로 판별해 엔진 체인을 고릅니다.",
  },
  {
    n: "02",
    title: "병렬 검색",
    body: "체인의 엔진을 동시에 호출합니다. 데드라인(기본 4초)을 넘긴 엔진은 건너뛰고 캐시만 채웁니다.",
  },
  {
    n: "03",
    title: "융합",
    body: "관련도 0.4 이상인 엔진을 가중 RRF로 합쳐, 여러 엔진이 함께 올린 문서를 위로 올립니다.",
  },
]

export function Steps() {
  return (
    <ol className="mt-14 grid gap-8 sm:grid-cols-3 sm:gap-6">
      {STEPS.map((s, i) => (
        <li
          key={s.n}
          style={delay(4 + i)}
          className={cn("border-t pt-4", REVEAL)}
        >
          <span className="font-mono text-xs text-primary">{s.n}</span>
          <h2 className="mt-3 text-base font-medium">{s.title}</h2>
          <p className="mt-1.5 text-sm/relaxed text-pretty text-muted-foreground">
            {s.body}
          </p>
        </li>
      ))}
    </ol>
  )
}

export function Footer() {
  return (
    <footer className="mx-auto mt-20 flex w-full max-w-6xl flex-wrap items-center justify-between gap-2 border-t px-4 py-6 text-xs text-muted-foreground sm:px-6">
      <span className="font-mono">
        omniSearch · keyless hybrid search router
      </span>
      <a
        href="https://github.com/Goldhobbang/omniSearch"
        target="_blank"
        rel="noopener noreferrer"
        className="underline-offset-4 hover:text-foreground hover:underline"
      >
        GitHub
      </a>
    </footer>
  )
}
