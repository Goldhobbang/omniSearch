# -*- coding: utf-8 -*-
"""sense 엔진 파서 + 쿼리 게이트 단위테스트. 네트워크 없이 실행."""

from omnisearch.core import (
    _build_chain, _code_token, _model_token, _parse_huggingface,
    TOOL_VERSION, _parse_stackexchange, cache_put, jina_fetch,
)


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        raise SystemExit(f"FAILED: {name}")


check("code venv", _code_token("venv") is True)
check("code DataLoader", _code_token("DataLoader") is True)
check("code Opus", _code_token("Opus") is True)
check("code rejects AI", _code_token("AI") is False)
check("code rejects hangul", _code_token("배치") is False)
check("code rejects sentence", _code_token("what is venv") is False)
check("code rejects 30B", _code_token("30B") is False)
check("model 30B", _model_token("30B") is True)
check("model Qwen3-30B", _model_token("Qwen3-30B") is True)
check("model rejects venv", _model_token("venv") is False)

check("chain venv has SE", "stackexchange" in _build_chain("general", "venv", None))
check("chain 30B fronts HF",
      _build_chain("general", "30B", None)[0] == "huggingface")
check("chain AI unchanged",
      "stackexchange" not in _build_chain("general", "AI", None)
      and "huggingface" not in _build_chain("general", "AI", None))

SE = {"items": [
    {"title": "What is venv&#39;?",
     "link": "http://x/1", "score": 5, "answer_count": 2,
     "is_answered": True, "tags": ["python", "venv"]},
    {"title": "", "link": "http://x/2"},
], "quota_remaining": 999, "quota_max": 1000}
check("se parser", _parse_stackexchange(SE, 8) == [
    {"title": "What is venv'?", "url": "http://x/1",
     "snippet": "▲5 · 답변2 · 채택됨 [python] [venv]"}])

HF = [
    {"id": "Qwen/Qwen3-30B", "downloads": 10, "likes": 2,
     "pipeline_tag": "text-generation"},
    {"no-id": True},
]
check("hf parser", _parse_huggingface(HF, 8) == [
    {"title": "Qwen/Qwen3-30B",
     "url": "https://huggingface.co/Qwen/Qwen3-30B",
     "snippet": "downloads 10 · likes 2 · text-generation"}])

check("jina bad url", jina_fetch("not-a-url") == "")
cache_put(f"v{TOOL_VERSION}:fetch:http://cached.test/x", "cached body")
check("jina cache hit", jina_fetch("http://cached.test/x") == "cached body")
print("ALL SENSE TESTS PASSED")
