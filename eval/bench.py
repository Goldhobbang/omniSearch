# -*- coding: utf-8 -*-
"""Rate-limit aware latency/quality bench on the REAL search().

  python eval/bench.py run paced 0      # human pacing (10s between queries), query set 0
  python eval/bench.py run burst 1      # agent pacing (back-to-back), query set 1
  python eval/bench.py run burst 0 my_queries.json   # custom set: [[ [query, intended], ... ]]
  python eval/bench.py report eval/bench_out/*.json

Records every engine call, every _polite wait and every cooldown; report replays
search() selection at several deadlines. Query sets: eval/bench_queries.json
(two disjoint sets, equal count per category). Uses a fresh cache per run.
"""
import collections
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else float("nan")


def ok_pass(score, n, th=0.4):
    return n >= 1 and score >= th


def sim(run, by_q, D):
    """Replay search() selection with deadline D from logged engine finish times."""
    from omnisearch.core import CHAIN
    chain = CHAIN.get(run["cat"], CHAIN["general"])
    waited, best = 0.0, (0.0, 0)
    for t in chain:
        x = by_q.get((run["q"], t))
        if x is None:  # lazy engine not reached in the real run -> no data, skip
            continue
        fin = (x["end"] - run["start"]) if x["end"] is not None else 1e9
        if fin > D:
            waited = D
            continue
        waited = max(waited, fin)
        if x["status"] == "ok":
            best = max(best, (x["score"], x["n"]))
            if x["score"] >= 0.6:
                return waited, best
    return waited, best


def run(mode, half, qfile=None):
    out = os.path.join(HERE, "bench_out", f"{mode}{half}_{time.strftime('%m%d_%H%M')}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    os.environ["OMNI_CACHE"] = out + ".db"
    import omnisearch.core as c

    T0 = time.time()
    LOCK = threading.Lock()
    CALLS, POLITE, COOLS = [], [], []

    def classify_err(e):
        s = str(e).lower()
        if "busy" in s:
            return "busy_skip"
        if "cooling down" in s:
            return "cooldown_skip"
        if "429" in s or "rate limited" in s or "quota" in s:
            return "ratelimit"
        if "blocked" in s or "junk" in s:
            return "softblock"
        if "timed out" in s or "timeout" in s:
            return "timeout"
        return "error"

    def wrap(name, fn):
        def w(query, *a, **k):
            rec = {"tool": name, "q": query, "start": time.time() - T0, "end": None,
                   "status": None, "n": 0, "score": 0.0, "detail": ""}
            with LOCK:
                CALLS.append(rec)
            try:
                res = fn(query, *a, **k)
            except Exception as e:
                rec.update(end=time.time() - T0, status=classify_err(e), detail=str(e)[:100])
                raise
            items = [x for x in res if c.norm(x.get("title"))]
            rec.update(end=time.time() - T0, status="ok" if items else "empty",
                       n=len(items), score=c.relevance(query, items))
            return res
        return w

    for k in list(c.ENGINES):
        c.ENGINES[k] = wrap(k, c.ENGINES[k])

    _orig_polite = c._polite

    def polite(key, mi):
        t = time.time()
        _orig_polite(key, mi)
        with LOCK:
            POLITE.append({"key": key, "at": t - T0, "wait": time.time() - t})

    c._polite = polite

    _orig_cool = c._cool

    def cool(label, seconds=c.COOLDOWN):
        with LOCK:
            COOLS.append({"label": label, "at": time.time() - T0, "sec": seconds})
        _orig_cool(label, seconds)

    c._cool = cool

    queries = json.load(open(qfile or os.path.join(HERE, "bench_queries.json"), encoding="utf-8"))[half]
    runs = []
    for i, (q, intended) in enumerate(queries):
        qs = time.time()
        r = c.search(q)
        lat = time.time() - qs
        runs.append({"i": i, "q": c.norm(q), "intended": intended, "cat": r.get("category"),
                     "start": qs - T0, "lat": lat, "tool": r.get("used_tool"),
                     "score": r.get("score") or 0.0, "count": r.get("count") or 0,
                     "tried": r.get("tried", {})})
        print(f"{i:2} {lat:5.1f}s {r.get('used_tool')}/{r.get('score')} {q[:30]}", flush=True)
        if mode == "paced":
            time.sleep(max(0.0, 10.0 - lat))

    end = time.time() + 90  # let background engine threads finish
    while time.time() < end and any(x["end"] is None for x in CALLS):
        time.sleep(1)
    json.dump({"mode": mode, "runs": runs, "calls": CALLS, "polite": POLITE, "cools": COOLS,
               "total": time.time() - T0}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print("saved", out, "unfinished", sum(x["end"] is None for x in CALLS), flush=True)
    os._exit(0)  # straggler threads must not block exit


def report(paths):
    from omnisearch.core import CHAIN
    for path in paths:
        d = json.load(open(path, encoding="utf-8"))
        runs, calls, pol, cools = d["runs"], d["calls"], d["polite"], d["cools"]
        by_q = {(x["q"], x["tool"]): x for x in calls}
        lats = [r["lat"] for r in runs]
        n = len(runs)
        print(f"\n=== {d['mode']}  queries={n}  wall={d['total']:.0f}s")
        print(f"search(): p50 {pct(lats, .5):.1f}s  p90 {pct(lats, .9):.1f}s  max {max(lats):.1f}s  "
              f"mean {sum(lats) / n:.1f}s | pass {sum(ok_pass(r['score'], r['count']) for r in runs)}/{n}  "
              f"strict {sum(ok_pass(r['score'], r['count'], .6) for r in runs)}/{n}  "
              f"avg {sum(r['score'] for r in runs) / n:.3f}")
        half = n // 2
        for name, part in (("first half", runs[:half]), ("second half", runs[half:])):
            pl = [r["lat"] for r in part]
            print(f"  {name}: p50 {pct(pl, .5):.1f}s p90 {pct(pl, .9):.1f}s "
                  f"pass {sum(ok_pass(r['score'], r['count']) for r in part)}/{len(part)}")

        print("by category:")
        by = collections.defaultdict(list)
        for r in runs:
            by[r["cat"]].append(r)
        for cat, rs in sorted(by.items()):
            pl = [r["lat"] for r in rs]
            print(f"  {cat:12} n={len(rs):2} pass={sum(ok_pass(r['score'], r['count']) for r in rs):2} "
                  f"p50={pct(pl, .5):4.1f}s max={max(pl):4.1f}s  winners={dict(collections.Counter(r['tool'] for r in rs))}")

        print("engines: calls | status counts | duration(ok/empty) p50 p90 max | score>=0.6")
        per = collections.defaultdict(list)
        for x in calls:
            per[x["tool"]].append(x)
        for t, xs in sorted(per.items(), key=lambda kv: -len(kv[1])):
            st = collections.Counter(x["status"] or "unfinished" for x in xs)
            du = [x["end"] - x["start"] for x in xs if x["status"] in ("ok", "empty")]
            print(f"  {t:16} {len(xs):3} | {dict(st)} | {pct(du, .5):5.1f} {pct(du, .9):5.1f} "
                  f"{max(du) if du else float('nan'):5.1f} | {sum(1 for x in xs if x['status'] == 'ok' and x['score'] >= .6)}")

        print("polite waits (per-engine call spacing):")
        pk = collections.defaultdict(list)
        for p in pol:
            pk[p["key"]].append(p["wait"])
        for k, ws in sorted(pk.items()):
            print(f"  {k:16} n={len(ws):3} mean {sum(ws) / len(ws):5.2f}s p90 {pct(ws, .9):5.2f}s "
                  f"max {max(ws):5.2f}s total {sum(ws):6.1f}s")
        print("cooldowns:", dict(collections.Counter(c["label"] for c in cools)),
              "at", [round(c["at"]) for c in cools][:15])

        print("deadline replay (search selection):  D | pass | strict | avg | lat p50 p90")
        for D in (1, 1.5, 2, 2.5, 3, 4, 6):
            res = [sim(r, by_q, D) for r in runs]
            ls = [w for w, _ in res]
            print(f"    {D:4}s  {sum(ok_pass(s, c) for _, (s, c) in res):2}/{n}  "
                  f"{sum(ok_pass(s, c, .6) for _, (s, c) in res):2}/{n}  "
                  f"{sum(s for _, (s, c) in res) / n:.3f}  {pct(ls, .5):4.1f}s {pct(ls, .9):4.1f}s")
        fin_all = []
        for r in runs:
            fs = [(by_q[(r["q"], t)]["end"] or 1e9) - r["start"]
                  for t in CHAIN.get(r["cat"], CHAIN["general"]) if (r["q"], t) in by_q]
            fin_all.append(max(fs) if fs else 0)
        print(f"multi_search natural latency (all engines done): p50 {pct(fin_all, .5):.1f}s "
              f"p90 {pct(fin_all, .9):.1f}s max {max(fin_all):.1f}s")


if __name__ == "__main__":
    if sys.argv[1:2] == ["run"]:
        run(sys.argv[2], int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else None)
    elif sys.argv[1:2] == ["report"]:
        report(sys.argv[2:])
    else:
        print(__doc__)
