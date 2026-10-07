"""1000개 독립·상이주제 단어 수집.
원천: en.wikipedia 랜덤 문서 + ko.wikipedia 랜덤 문서 + 큐레이션 리스트.
위키 랜덤 = 주제 독립성 보장. 중복 제거 후 words_1000.json 저장.
"""
import json
import os
import time

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "words_1000.json")
UA = "OmniTool/1.0 (local research harness)"
S = requests.Session()
S.headers.update({"User-Agent": UA})


def _get(url, params, tries=5):
    for i in range(tries):
        r = S.get(url, params=params, timeout=20)
        if r.status_code == 429:
            time.sleep(5 * (i + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("429 persistent")


def fetch_random_titles(lang, n):
    titles, seen, cont, per = [], set(), None, 20
    while len(titles) < n:
        params = {"action": "query", "format": "json", "list": "random",
                  "rnnamespace": 0, "rnlimit": per}
        if cont:
            params["rncontinue"] = cont
        data = _get(f"https://{lang}.wikipedia.org/w/api.php", params)
        got = data["query"]["random"]
        for p in got:
            t = p["title"].strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                titles.append(t)
            if len(titles) >= n:
                break
        cont = data.get("continue", {}).get("rncontinue")
        time.sleep(1.0)
        if not cont:
            break
    return titles[:n]


def main():
    from omnisearch.wordlists import WORD_LISTS

    words = []
    seen = set()

    def add(w, source, expected):
        if w and w.strip().lower() not in seen:
            seen.add(w.strip().lower())
            words.append({"word": w.strip(), "source": source,
                          "expected": expected})

    print("fetch en.wikipedia random...", flush=True)
    for t in fetch_random_titles("en", 660):
        add(t, "enwiki-random", "entity")
    print(f"en done: {len(words)}", flush=True)
    print("fetch ko.wikipedia random...", flush=True)
    for t in fetch_random_titles("ko", 310):
        add(t, "kowiki-random", "entity")
    print(f"ko done: {len(words)}", flush=True)
    for cat, lst in WORD_LISTS.items():
        for w in lst:
            add(w, "curated", cat)
    print(f"total: {len(words)}", flush=True)
    if len(words) < 1000:
        print("topping up en...", flush=True)
        for t in fetch_random_titles("en", 1000 - len(words) + 50):
            add(t, "enwiki-random", "entity")
            if len(words) >= 1050:
                break
    print(f"final: {len(words)}", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=1)
    print(f"saved: {OUT}", flush=True)


if __name__ == "__main__":
    main()
