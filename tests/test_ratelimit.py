# -*- coding: utf-8 -*-
"""_polite / cooldown 단위테스트. 네트워크 없이 실행."""
import threading
import time

import omnisearch.core as c


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name


# 1) 한 엔진의 대기가 다른 엔진을 막지 않는다 (예전 버그: 전역 잠금 안에서 sleep)
c._polite("slow", 0)          # slot 기록
t = threading.Thread(target=c._polite, args=("slow", 1.5))
t.start()
time.sleep(0.05)              # slow가 1.5초 대기 중
t0 = time.time()
c._polite("fast", 0.1)
check("other engine not blocked", time.time() - t0 < 0.3)
t.join()

# 2) 같은 엔진 동시 호출은 간격만큼 벌어진다 (슬롯 예약)
c._LAST_CALL.pop("same", None)
stamps = []
ths = [threading.Thread(target=lambda: (c._polite("same", 0.3), stamps.append(time.time())))
       for _ in range(3)]
for x in ths:
    x.start()
for x in ths:
    x.join()
stamps.sort()
check("same engine spaced", stamps[2] - stamps[0] >= 0.55)

# 3) 대기열이 DEADLINE보다 길면 기다리지 않고 건너뜀
c._LAST_CALL["queue"] = time.time() + c.DEADLINE + 5
t0 = time.time()
try:
    c._polite("queue", 1.0)
    skipped = False
except c.ToolUnavailable:
    skipped = True
check("long queue skipped instantly", skipped and time.time() - t0 < 0.1)

# 4) 연속 차단은 쉬는 시간 2배, 성공하면 초기화
c._ok("eng")
c._cool("eng", 10)
first = c._COOL_UNTIL["eng"] - time.time()
c._cool("eng", 10)
second = c._COOL_UNTIL["eng"] - time.time()
check("cooldown doubles", 9 < first <= 10 and 19 < second <= 20)
for _ in range(10):
    c._cool("eng", 10)
check("cooldown capped at 600s", c._COOL_UNTIL["eng"] - time.time() <= 600)
c._ok("eng")
c._cool("eng", 10)
check("reset after success", c._COOL_UNTIL["eng"] - time.time() <= 10)
try:
    c._check_cool("eng")
    cooled = False
except c.ToolUnavailable:
    cooled = True
check("cooling engine skipped", cooled)

print("ALL RATELIMIT TESTS PASSED")
