# -*- coding: utf-8 -*-
"""쿼터매니저 + Tavily/GNews 파서 단위테스트. 네트워크 없이 실행."""

from omnisearch.core import (
    _parse_gnews, _parse_tavily, _quota_period, quota_check, quota_hit,
    quota_spend_all, _db,
)


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        raise SystemExit(f"FAILED: {name}")


E = "zz_test_quota"
con = _db()
con.execute("CREATE TABLE IF NOT EXISTS q(e TEXT, p TEXT, n INT, "
            "PRIMARY KEY(e, p))")
con.execute("DELETE FROM q WHERE e=?", (E,))
con.commit()
con.close()

check("fresh quota ok", quota_check(E, 2, "day") is True)
quota_hit(E, "day")
check("1/2 still ok", quota_check(E, 2, "day") is True)
quota_hit(E, "day")
check("2/2 spent", quota_check(E, 2, "day") is False)
quota_spend_all(E, 100, "month")
check("spend-all blocks month", quota_check(E, 100, "month") is False)
check("period format",
      len(_quota_period("day")) == 10 and len(_quota_period("month")) == 7)

TAV = {"results": [
    {"title": "A", "url": "http://a", "content": "hello world"},
    {"title": "", "url": "http://b", "content": "no title"},
    "junk",
]}
check("tavily parser", _parse_tavily(TAV, 5) == [
    {"title": "A", "url": "http://a", "snippet": "hello world"}])

GN = {"articles": [
    {"title": "N", "url": "http://n", "description": "desc",
     "source": {"name": "SRC"}},
    {"title": "", "url": "http://x", "description": "skip"},
]}
check("gnews parser", _parse_gnews(GN, 8) == [
    {"title": "N", "url": "http://n", "snippet": "desc · SRC"}])

con = _db()
con.execute("DELETE FROM q WHERE e=?", (E,))
con.commit()
con.close()
print("ALL QUOTA TESTS PASSED")
