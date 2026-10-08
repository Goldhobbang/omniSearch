# -*- coding: utf-8 -*-
"""junk 탐지/스코어러 단위테스트. 네트워크 없이 실행. recorded fixture 기반."""

from omnisearch.core import looks_junk, relevance

# 실측 기록: DDG 소프트블록 시 반환된 junk (차등 프라이버시 질의)
JUNK_ZHIHU = [
    {"title": "如何评价GPT-6打破孪生素数猜想最新纪录？ - 知乎",
     "url": "https://www.zhihu.com/question/2079153750703456931", "snippet": ""},
    {"title": "gpt · GitHub Topics · GitHub",
     "url": "https://github.com/topics/gpt", "snippet": ""},
    {"title": "如何评价 OpenAI 最新发布的 GPT-6 Astra - 知乎",
     "url": "https://www.zhihu.com/question/2079054472190469850", "snippet": ""},
]
# 실측 기록: 킹받네 질의 junk
JUNK_HOME = [
    {"title": "YouTube TV Help",
     "url": "https://support.google.com/youtubetv/?hl=en", "snippet": ""},
    {"title": "Wikipedia", "url": "https://www.wikipedia.org/", "snippet": ""},
    {"title": "Wikipedia, the free encyclopedia",
     "url": "https://en.wikipedia.org/wiki/Main_Page", "snippet": ""},
]
# 정상 케이스
LEGIT_SAMGUI = [
    {"title": "삼귀다 뜻과 사용법 정리! 요즘 젊은이들은 언제 사용할까",
     "url": "https://blog.naver.com/record-0312/223739973425", "snippet": "삼귀다 의미"},
    {"title": "삼귀다 뜻 의미 유래 예시",
     "url": "https://kyungzatoday.tistory.com/375", "snippet": ""},
    {"title": "삼귀다 뜻 - 아직 사귀는 건 아니고",
     "url": "https://funsoft.co.kr/slang/xxx", "snippet": ""},
]
LEGIT_DP = [
    {"title": "차등 프라이버시 - Flower Framework",
     "url": "https://flower.ai/docs/ko/xxx", "snippet": "차등 프라이버시 설명"},
    {"title": "차등 프라이버시: AI 시대의 데이터 보호",
     "url": "https://didit.me/ko/blog/xxx", "snippet": ""},
    {"title": "차등 개인정보보호의 의미와 관련 기업 사용례",
     "url": "https://www.itworld.co.kr/news/178024", "snippet": ""},
]
LEGIT_EN_FOR_KO = [  # 한글 질의에 영문 정답 (differential privacy)
    {"title": "Differential Privacy - Wikipedia",
     "url": "https://en.wikipedia.org/wiki/Differential_privacy",
     "snippet": "differential privacy guarantees"},
    {"title": "What is Differential Privacy?",
     "url": "https://example.com/dp", "snippet": "privacy loss"},
    {"title": "Differential privacy library",
     "url": "https://example.com/lib", "snippet": "differential privacy"},
]
# 실측 기록: venv 질의에 위키가 반환한 오답 (스니펫 "O Venvs" 포함 메탈 앨범).
# 제목 매칭 없이는 고득점이 나오면 안 된다.
VENV_WIKI_JUNK = [
    {"title": "The Shit Ov God",
     "url": "https://en.wikipedia.org/wiki/The_Shit_Ov_God",
     "snippet": "\"Lvciferaeon\" 4:16 5. \"To Drown the Svn in Wine\" 3:29 6. \"O Venvs, Come!\" 5:55"},
    {"title": "Mária Széchy",
     "url": "https://en.wikipedia.org/wiki/M%C3%A1ria_Sz%C3%A9chy",
     "snippet": "Muranyi Venvs, printed in 1664 in Kassa"},
]
VENV_GOOD = [
    {"title": "파이썬의 venv 모듈로 가상 환경 사용하기",
     "url": "https://daleseo.com/python-venv/", "snippet": "가상 환경"},
]
# 실측 기록: DataLoader 질의에 위키 ETL 문서 (PyTorch 의미 아님).
# dataloader->data 과도 축약 매칭 + 스니펫 매칭으로는 0.8을 넘으면 안 된다.
DATALOADER_WIKI = [
    {"title": "Extract, transform, load",
     "url": "https://en.wikipedia.org/wiki/Extract%2C_transform%2C_load",
     "snippet": "Extract, transform, load (ETL) is a three-phase computing process where data are extracted"},
    {"title": "Data loading",
     "url": "https://en.wikipedia.org/wiki/Data_loading",
     "snippet": "Data loading, or simply loading, is a part of data processing"},
]
DATALOADER_GOOD = [
    {"title": "Dataset과 DataLoader — 파이토치 한국어 튜토리얼",
     "url": "https://tutorials.pytorch.kr/beginner/basics/data_tutorial.html", "snippet": ""},
]
# 실측 기록: 30B 질의 Sarvam AI 문서 (제목 무관, 스니펫에만 "30B").
THIRTYB_SNIPPET_ONLY = [
    {"title": "Sarvam AI",
     "url": "https://en.wikipedia.org/wiki/Sarvam_AI",
     "snippet": "the company announced Sarvam-30B, a 30-billion parameter model"},
]


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        raise SystemExit(f"FAILED: {name}")


check("zhihu-spam is junk", looks_junk("차등 프라이버시", JUNK_ZHIHU) is True)
check("homepage-spam is junk", looks_junk("킹받네", JUNK_HOME) is True)
check("legit slang not junk", looks_junk("삼귀다", LEGIT_SAMGUI) is False)
check("legit tech not junk", looks_junk("차등 프라이버시", LEGIT_DP) is False)
check("en-answer-for-ko-query not junk",
      looks_junk("차등 프라이버시", LEGIT_EN_FOR_KO) is False)
check("short-query bigram guard",
      relevance("oioi", [{"title": "Oil prices rise", "url": "http://x",
                          "snippet": "crude oil"}]) < 0.4)
check("exact still 1.0",
      relevance("차등 프라이버시", LEGIT_DP) == 1.0)
check("samgui scores",
      relevance("삼귀다", LEGIT_SAMGUI) >= 0.6)
check("snippet-only match never passes (venv)",
      relevance("venv", VENV_WIKI_JUNK) < 0.6)
check("title match still 1.0 (venv)",
      relevance("venv", VENV_GOOD) == 1.0)
check("over-stemming blocked (dataloader->data)",
      relevance("DataLoader", DATALOADER_WIKI) < 0.8)
check("title match still 1.0 (dataloader)",
      relevance("DataLoader", DATALOADER_GOOD) == 1.0)
check("snippet-only capped at 0.5 (30B)",
      relevance("30B", THIRTYB_SNIPPET_ONLY) <= 0.5)
print("ALL JUNK TESTS PASSED")
