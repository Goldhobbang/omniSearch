"""검증 하네스. 사용법:
  python verify.py --start 0 --count 100   # 0~99번 검증
  python verify.py --retry-failed          # 실패분만 재시도
통과 기준: count>=1 AND score>=0.4 (엄격: score>=0.6 별도 집계)
결과는 verify_progress.json 에 누적 (재개 가능).
"""
import argparse
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from omnisearch import search  # noqa: E402

WORDS = os.path.join(BASE_DIR, "words_1000.json")
PROG = os.path.join(BASE_DIR, "verify_progress.json")
PASS_SCORE = 0.4


def load_prog():
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_prog(p):
    tmp = PROG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False)
    os.replace(tmp, PROG)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--retry-failed", action="store_true")
    a = ap.parse_args()

    with open(WORDS, encoding="utf-8") as f:
        words = json.load(f)
    prog = load_prog()

    if a.retry_failed:
        targets = [(i, w) for i, w in enumerate(words)
                   if prog.get(w["word"], {}).get("pass") is not True]
        print(f"retry-failed targets: {len(targets)}", flush=True)
    else:
        targets = [(i, words[i]) for i in range(a.start, min(a.start + a.count, len(words)))]
        print(f"range {a.start}..{a.start + len(targets) - 1} (total words {len(words)})", flush=True)

    done = sum(1 for w in words if w["word"] in prog)
    print(f"already done: {done}/{len(words)}", flush=True)
    fails = []
    for k, (i, w) in enumerate(targets):
        q = w["word"]
        if q in prog and not a.retry_failed:
            continue
        try:
            rec = search(q)
        except Exception as e:  # search()는 raise 안 하지만 이중방어
            rec = {"query": q, "error": f"harness: {e}", "items": [],
                   "score": 0.0, "count": 0}
        ok = rec.get("count", 0) >= 1 and rec.get("score", 0.0) >= PASS_SCORE
        rec["pass"] = bool(ok)
        rec["idx"] = i
        rec["source"] = w.get("source")
        rec["expected"] = w.get("expected")
        rec["items"] = (rec.get("items") or [])[:3]
        prog[q] = rec
        if not ok:
            fails.append((q, rec.get("score"), rec.get("count"),
                          rec.get("used_tool"), rec.get("error", "")))
        time.sleep(0.5)
        if (k + 1) % 10 == 0:
            save_prog(prog)
        if (k + 1) % 20 == 0:
            so_far = [prog[x["word"]] for x in words if x["word"] in prog]
            rate = sum(1 for r in so_far if r.get("pass")) / max(len(so_far), 1)
            print(f"[{k + 1}/{len(targets)}] cumulative pass {rate:.1%} "
                  f"({len(so_far)} done) fails_this_run={len(fails)}", flush=True)
            time.sleep(0.5)
    save_prog(prog)

    so_far = [prog[x["word"]] for x in words if x["word"] in prog]
    n_pass = sum(1 for r in so_far if r.get("pass"))
    n_strict = sum(1 for r in so_far if r.get("pass") and r.get("score", 0) >= 0.6)
    print(f"DONE run={len(targets)} cumulative={len(so_far)} "
          f"pass={n_pass} ({n_pass / max(len(so_far), 1):.1%}) strict60={n_strict}", flush=True)
    print("FAIL SAMPLES (up to 10):", flush=True)
    for q, sc, cnt, tool, err in fails[:10]:
        print(f"  - {q!r} score={sc} count={cnt} tool={tool} err={err}", flush=True)


if __name__ == "__main__":
    main()
