#!/usr/bin/env bash
# 로컬 SearXNG 실행. 미설치면 install.sh 먼저 실행.
# Linux/macOS: bash searxng/start.sh   Windows: wsl -e bash searxng/start.sh
# omnitool은 서버가 꺼져 있으면 이 스크립트를 자동 실행함 (SEARXNG_AUTOSTART=0 으로 끔).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="${SEARXNG_HOME:-$HOME/searxng}"
[ -x "$DIR/venv/bin/python" ] || bash "$HERE/install.sh"
export SEARXNG_SETTINGS_PATH="$HERE/settings.yml"
export SEARXNG_SECRET="${SEARXNG_SECRET:-$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')}"
cd "$DIR"
exec venv/bin/python searx/webapp.py
