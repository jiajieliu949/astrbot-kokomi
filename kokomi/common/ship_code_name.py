# -*- coding: utf-8 -*-
"""船代号（ship_index，如 PGSB211）-> 权威简体中文名。

2026-10-16：战绩类卡片的「船只」列靠预烤预览图（ship_preview_cn.png）显示，
图里没有的船会退化成显示原始代号。本模块用「游戏代号→GameParams id→本地索引
nameCn」映射（由 tools 侧从客户端 GameParams dump + ship_index_ru.json 生成，
940 条）提供中文名，供各卡片在查无预览格时回退显示。

数据文件：kokomi_llm/data/ship_code_cn.json（{code: nameCn}）。
"""
import json
from pathlib import Path

_MAP = None


def code_cn_map():
    global _MAP
    if _MAP is None:
        _MAP = {}
        try:
            fp = Path(__file__).resolve().parents[2] / "kokomi_llm" / "data" / "ship_code_cn.json"
            if fp.is_file():
                data = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    _MAP = data
        except Exception:
            _MAP = {}
    return _MAP


def code_cn_name(code):
    """查代号的中文名；查无返回 None（调用方自行回退）。"""
    try:
        return code_cn_map().get(str(code))
    except Exception:
        return None
