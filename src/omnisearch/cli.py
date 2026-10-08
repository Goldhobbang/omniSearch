"""omnisearch CLI.

  omnisearch "질의"                 best-pick 결과
  omnisearch "질의" --multi         엔진별 전체 결과
  omnisearch "질의" --json          JSON 출력
  omnisearch "질의" --fetch         상위 1건 본문 발췌 추가 (Jina, 느림)
  omnisearch "질의" --extra marginalia
"""
import argparse
import json
import sys

from .core import jina_fetch, multi_search, search


def _print_items(items, n):
    for i, it in enumerate(items[:n], 1):
        print(f"{i}. {it.get('title', '')}")
        if it.get("url"):
            print(f"   {it['url']}")
        if it.get("snippet"):
            print(f"   {it['snippet'][:160]}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="omnisearch", description="keyless multi-engine search")
    p.add_argument("query")
    p.add_argument("--multi", action="store_true", help="run every engine in the chain")
    p.add_argument("--json", action="store_true", help="print raw JSON")
    p.add_argument("--extra", action="append", default=None,
                   help="opt-in engine (repeatable), e.g. marginalia")
    p.add_argument("-n", type=int, default=5, help="items to show per engine")
    p.add_argument("--fetch", action="store_true",
                   help="fetch top-1 page body excerpt (Jina, slow)")
    a = p.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):  # Windows cp949 콘솔 대비
        sys.stdout.reconfigure(encoding="utf-8")
    r = (multi_search if a.multi else search)(a.query, extra=a.extra)
    if a.fetch and not a.multi and r.get("items"):
        top = r["items"][0]
        top["extract"] = jina_fetch(top.get("url") or "")[:500]
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if not r.get("error") else 1
    if r.get("error") and not r.get("items") and not r.get("tools"):
        print(f"error: {r['error']}", file=sys.stderr)
        return 1
    print(f"[{r.get('category')}] {r.get('elapsed')}s")
    if a.multi:
        for t in r.get("order", []):
            pack = r["tools"][t]
            print(f"\n== {pack['label']}  score={pack['score']}  ({pack['status']})")
            _print_items(pack["items"], a.n)
    else:
        print(f"engine={r.get('used_tool')} score={r.get('score')}\n")
        _print_items(r.get("items", []), a.n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
