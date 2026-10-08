# Contributing

```bash
git clone https://github.com/Goldhobbang/omniSearch && cd omniSearch
python -m venv .venv && .venv/Scripts/activate    # Linux/macOS: source .venv/bin/activate
pip install -e ".[web,mcp]"
```

## 테스트

네트워크 없이 도는 단위 테스트(CI와 동일):

```bash
python tests/test_junk.py
python tests/test_ratelimit.py
python tests/test_quota.py
python tests/test_sense.py
python tests/test_fuse.py
python tests/test_web.py
```

실제 엔진을 치는 측정은 `eval/` (README의 Development 참고).

## 웹 UI

소스는 `frontend/` (Vite + React + shadcn/ui). 컴포넌트는 `npx shadcn@latest add <name>`으로 추가한다.
UI를 바꾸면 `npm run build`로 `src/omnisearch/static/`을 다시 만들어 함께 커밋한다 (패키지 설치에 Node가 필요 없게 하려고 빌드 결과를 커밋해 둔다).
`frontend/src/lib/demo.ts`는 `core.py`의 분류·관련도·`fuse()`를 옮긴 사본이므로, 해당 로직을 바꾸면 같이 맞춘다.
