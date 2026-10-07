#!/usr/bin/env bash
# WSL에서 로컬 SearXNG 실행. Windows에서: wsl -e bash searxng/start.sh
# 최초 1회 설치(~/searxng, sudo 불필요):
#   git clone --depth 1 https://github.com/searxng/searxng ~/searxng
#   cd ~/searxng && python3 -m venv venv
#   venv/bin/pip install -U pip setuptools wheel pyyaml msgspec typing-extensions pybind11
#   venv/bin/pip install --use-pep517 --no-build-isolation -e .
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
export SEARXNG_SETTINGS_PATH="$HERE/settings.yml"
export SEARXNG_SECRET="${SEARXNG_SECRET:-$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')}"
cd ~/searxng
exec venv/bin/python searx/webapp.py
