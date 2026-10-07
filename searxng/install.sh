#!/usr/bin/env bash
# SearXNG를 ~/searxng 에 설치 (sudo 불필요, 재실행 안전).
# 필요: git, python3 (3.10+), python3-venv
set -e
DIR="${SEARXNG_HOME:-$HOME/searxng}"
if [ ! -d "$DIR/.git" ]; then
  git clone --depth 1 https://github.com/searxng/searxng "$DIR"
fi
cd "$DIR"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q -U pip setuptools wheel pyyaml msgspec typing-extensions pybind11
venv/bin/pip install -q --use-pep517 --no-build-isolation -e .
echo "searxng installed: $DIR"
