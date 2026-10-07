# -*- coding: utf-8 -*-
import io
import os

from omnisearch import search, multi_search

OUT = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "spot.txt"), "w", encoding="utf-8")
for q in ["Musgrave railway station", "데론가 제도", "갓생",
          "양자 얽힘", "Attention Is All You Need", "생성형 AI 저작권 소송",
          "토스뱅크"]:
    r = search(q)
    OUT.write(f"{q} -> tool={r.get('used_tool')} score={r.get('score')} "
              f"pass={r.get('count', 0) >= 1 and r.get('score', 0) >= 0.4}\n")
m = multi_search("StayFree", extra=["marginalia"])
OUT.write(f"multi+extra tools={list(m['tools'].keys())}\n")
OUT.close()
print("ok")
