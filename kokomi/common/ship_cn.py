# -*- coding: utf-8 -*-
"""shipId -> 权威简体中文名（本地索引 ship_index_ru.json / ship_index_wg.json）。

2026-10-16：Kokomi API 对俄服查询返回的 ship_name 是俄语名；
战绩图需要显示简体中文 —— 用本地索引（ships_lesta 权威汉化）覆盖。
"""
import json
from pathlib import Path

_MAP = None


def ship_cn_map():
    global _MAP
    if _MAP is None:
        _MAP = {}
        try:
            base = Path(__file__).resolve().parents[2] / "kokomi_llm" / "data"
            for fn in ("ship_index_ru.json", "ship_index_wg.json"):
                fp = base / fn
                if not fp.is_file():
                    continue
                try:
                    items = json.loads(fp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(items, list):
                    continue
                for it in items:
                    if isinstance(it, dict) and it.get("shipId") is not None:
                        cn = str(it.get("nameCn") or "").strip()
                        if cn:
                            _MAP.setdefault(str(it["shipId"]), cn)
        except Exception:
            _MAP = {}
    return _MAP


def ship_cn_name(sid):
    """查 shipId 的中文名；查无返回 None（调用方回退 API 原名）。"""
    try:
        return ship_cn_map().get(str(sid))
    except Exception:
        return None
