# -*- coding: utf-8 -*-
"""面向 LLM 的查询层：自然语言战绩查询。

职责边界（不重复造轮子）：
- 取数/渲染全部复用原 Kokomi 插件（call_api / scripts.get_png / 绑定表 / 时区）
- 本包只做：身份解析（谁查谁）、参数归一（服务器/模式/日期）、
  字段提取（JSON -> 模型可读文本）、限流与话术。

模块划分（参照 AstrByWowsYuyukoBot 的 yuyuko_llm 布局）：
- query.py    身份解析 + 参数拼装 + 取数渲染
- extract.py  API JSON -> 模型字段
- guide.py    限流 / 开关 / 错误话术
"""

from .guide import RateLimiter, humanize_api_error
from .query import (
    clamp_days,
    fetch_and_render,
    normalize_battle_mode,
    normalize_server,
    normalize_ship_type,
    resolve_target,
)
from .extract import (extract_account, extract_recent, extract_ship,
                     extract_ships, generic_dump)

__all__ = [
    "RateLimiter",
    "humanize_api_error",
    "resolve_target",
    "fetch_and_render",
    "normalize_server",
    "normalize_battle_mode",
    "normalize_ship_type",
    "clamp_days",
    "extract_account",
    "extract_recent",
    "extract_ship",
    "extract_ships",
    "generic_dump",
]
