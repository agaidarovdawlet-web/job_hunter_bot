#!/usr/bin/env python3
"""Точка входа для запуска Telegram-бота (long polling, запускается локально/на сервере)."""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def run() -> None:
    from job_hunter_bot.bot import main

    asyncio.run(main())

if __name__ == "__main__":
    run()
