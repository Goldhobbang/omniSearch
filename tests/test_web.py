# -*- coding: utf-8 -*-
"""웹 UI 정적 서빙 스모크 테스트: 빌드 결과(static/)가 빠지면 실패. 네트워크 없이 실행."""
import re

from omnisearch.web import app

c = app.test_client()


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name


for path in ("/", "/smart"):
    r = c.get(path)
    check(f"{path} serves the SPA", r.status_code == 200 and b'id="root"' in r.data)

html = c.get("/").get_data(as_text=True)
assets = re.findall(r'(?:src|href)="(/static/[^"]+)"', html)
check("index references built assets", len(assets) >= 2)
for a in assets:
    check(f"asset served: {a}", c.get(a).status_code == 200)
