#!/usr/bin/env python3
"""Точка входа для запуска поиска вакансий (используется в GitHub Actions)."""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def run() -> None:
    from job_hunter_bot.search_runner import run_search

    asyncio.run(run_search())

if __name__ == "__main__":
    run()
