import { useEffect, useRef } from "react"
import { DicesIcon, SearchIcon, SparklesIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { Kbd } from "@/components/ui/kbd"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DEMO, type Mode } from "@/lib/api"

type Props = {
  q: string
  onQ: (q: string) => void
  mode: Mode
  onMode: (m: Mode) => void
  categories: string[]
  onRandom: (category?: string) => void
  onSubmit: () => void
  loading: boolean
}

export function SearchPanel({
  q,
  onQ,
  mode,
  onMode,
  categories,
  onRandom,
  onSubmit,
  loading,
}: Props) {
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => {
    // 터치 기기에서는 키보드가 화면을 가리므로 자동 포커스하지 않는다
    if (matchMedia("(pointer: fine)").matches)
      input.current?.focus({ preventScroll: true })
  }, [])

  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <Card className="gap-0 py-0 shadow-sm">
        <div className="p-2.5 sm:p-3">
          <InputGroup className="h-12 rounded-lg bg-background dark:bg-input/30">
            <InputGroupAddon className="pl-3.5">
              <SearchIcon className="size-4.5" />
            </InputGroupAddon>
            <InputGroupInput
              ref={input}
              value={q}
              onChange={(e) => onQ(e.target.value)}
              placeholder="검색어 입력 — 예: 갓생"
              aria-label="검색어"
              autoComplete="off"
              className="h-full text-base md:text-base"
            />
            <InputGroupAddon align="inline-end" className="gap-2 pr-1.5">
              <Kbd className="hidden sm:inline-flex">Enter</Kbd>
              <InputGroupButton
                type="submit"
                variant="default"
                size="sm"
                disabled={loading || !q.trim()}
                className="h-9 px-4"
              >
                {loading ? <Spinner /> : null}
                {loading ? "검색 중" : "검색"}
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </div>
        <Separator />
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2.5 px-3 py-2.5">
          {!DEMO && (
            <Tabs value={mode} onValueChange={(v) => onMode(v as Mode)}>
              <TabsList>
                <TabsTrigger value="smart" className="px-3">
                  <SparklesIcon />
                  스마트 라우팅
                </TabsTrigger>
                <TabsTrigger value="ddg" className="px-3">
                  DuckDuckGo
                </TabsTrigger>
              </TabsList>
            </Tabs>
          )}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs text-muted-foreground">
              랜덤 질의
            </span>
            {categories.map((c) => (
              <Button
                key={c}
                type="button"
                variant="outline"
                size="xs"
                onClick={() => onRandom(c)}
              >
                {c}
              </Button>
            ))}
            <Button
              type="button"
              variant="secondary"
              size="xs"
              onClick={() => onRandom()}
            >
              <DicesIcon />
              아무거나
            </Button>
          </div>
        </div>
      </Card>
    </form>
  )
}
