#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建本地船名索引（按服务器物理拆表）。

数据源：yuyuko 百科船名搜索接口
    https://v3-api.wows.shinoaki.com/public/wows/encyclopedia/ship/search
    - 不带 server 参数 → WG 系（asia/eu/na/360/cn），986~991 条
    - 带 &server=ru   → LESTA（俄服），~982 条

⚠️ 两服 shipId 体系不通用（约 746 条同船两服均收录、仅名字本地化差异）。
   若合并去重，会把只在俄服的船误标成 WG，污染 ru 表。
   故本脚本 **不做合并去重**，两服结果各自独立写入：

    WG 结果  → kokomi_llm/data/ship_index_wg.json
    RU 结果  → kokomi_llm/data/ship_index_ru.json

写入前自动把旧文件另存时间戳备份（*.bak-YYYYmmdd-HHMMSS）。

用法：python3 tools/refresh_ship_index.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.request
from datetime import datetime

BASE_URL = "https://v3-api.wows.shinoaki.com/public/wows/encyclopedia/ship/search"

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_PLUGIN_ROOT, "kokomi_llm", "data")

_TARGETS = [
    # (url, 目标文件, 期望 serverType)
    (BASE_URL, "ship_index_wg.json", "WG"),
    (BASE_URL + "?server=ru", "ship_index_ru.json", "LESTA"),
]


def _fetch(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "kokomi-refresh/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        raise RuntimeError(f"接口返回格式异常: {url}")
    return data


def _backup(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = f"{path}.bak-{stamp}"
    shutil.copy2(path, dst)
    return dst


def _write(path: str, ships: list[dict]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ships, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main() -> int:
    for url, fname, expect_type in _TARGETS:
        path = os.path.join(_DATA_DIR, fname)
        try:
            ships = _fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {fname} 抓取失败: {exc}", file=sys.stderr)
            return 1

        bad = [s for s in ships if s.get("serverType") != expect_type]
        if bad:
            print(
                f"[FAIL] {fname} serverType 校验不通过："
                f"期望 {expect_type}，混入 {len(bad)} 条（如 {bad[0].get('serverType')}）",
                file=sys.stderr,
            )
            return 1

        bak = _backup(path)
        _write(path, ships)
        print(f"[OK] {fname}: {len(ships)} 条 -> {path}" + (f"（备份 {bak}）" if bak else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
