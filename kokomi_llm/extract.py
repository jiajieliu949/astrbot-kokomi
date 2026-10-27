# -*- coding: utf-8 -*-
"""API JSON -> 模型可读文本。

设计要点：
- 白名单提取，剥离 *_color / *_text / *_dis / *_index 等纯渲染字段，省 token；
- 数值上游已格式化好（"59.09%"、"121 261"），直接透传，不做二次换算；
- 输出是紧凑的中文键值文本（不是大 JSON），模型读完就能点评；
- 总长超过 _MAX_CHARS 截断 —— 超长文本对点评质量没有帮助。
"""

from __future__ import annotations

import json

_MAX_CHARS = 3500

# 纯渲染辅助字段：对点评毫无信息量
_RENDER_KEYS = ("_color", "_text", "_dis", "_des", "_index")

# 战斗模式键 -> 中文
_MODE_CN = {
    "pvp": "随机(全部)", "pvp_solo": "单野", "pvp_div2": "双排",
    "pvp_div3": "三排", "rank": "排位", "rank_solo": "排位(单排)",
}

# 船型英文 -> 中文（模板前端写死的映射，Python 侧备一份）
_SHIP_TYPE_CN = {
    "AirCarrier": "航空母舰", "Battleship": "战列舰", "BattleCruiser": "战列巡洋舰",
    "Cruiser": "巡洋舰", "Destroyer": "驱逐舰", "Submarine": "潜艇",
}


def _strip_render_fields(d: dict) -> dict:
    return {k: v for k, v in d.items() if not any(k.endswith(s) for s in _RENDER_KEYS)}


def _fmt_mode_block(mode_key: str, mode_data: dict) -> str:
    m = _strip_render_fields(mode_data)
    cn = _MODE_CN.get(mode_key, mode_key)
    return (
        f"  {cn}: 场次={m.get('battles_count','-')} 胜率={m.get('win_rate','-')} "
        f"场均伤害={m.get('avg_damage','-')} 场均击杀={m.get('avg_frags','-')} "
        f"场均经验={m.get('avg_exp','-')} PR={m.get('avg_pr','-')}"
    )


def _pr_line(pr: dict | None) -> str:
    if not pr:
        return "  总览: 无数据"
    m = _strip_render_fields(pr)
    return (
        f"  总览: 场次={m.get('battles_count','-')} 胜率={m.get('win_rate','-')} "
        f"场均伤害={m.get('avg_damage','-')} 场均击杀={m.get('avg_frags','-')} "
        f"场均经验={m.get('avg_exp','-')} PR={m.get('avg_pr','-')}"
    )


def extract_account(data: dict, nickname: str | None = None) -> str:
    """水表（/b/pvp-data/）-> 模型文本。"""
    if not isinstance(data, dict):
        return "数据为空"
    parts = [f"玩家: {nickname or data.get('nickname') or '?'}"]

    parts.append(_pr_line(data.get("pr")))

    bt = data.get("battle_type") or {}
    if isinstance(bt, dict) and bt:
        parts.append("分模式战绩:")
        for k in sorted(bt):
            parts.append(_fmt_mode_block(k, bt[k]))

    st = data.get("ship_type") or {}
    if isinstance(st, dict) and st:
        parts.append("分船型战绩(场次>=10 的):")
        rows = []
        for k, v in st.items():
            try:
                n = int(str(v.get("battles_count", "0")).replace(" ", "") or 0)
            except (ValueError, AttributeError):
                n = 0
            if n >= 10:
                rows.append((n, k, v))
        for n, k, v in sorted(rows, reverse=True)[:6]:
            cn = _SHIP_TYPE_CN.get(k, k)
            m = _strip_render_fields(v)
            parts.append(
                f"  {cn}: {n}场 胜率={m.get('win_rate','-')} "
                f"场均伤害={m.get('avg_damage','-')} PR={m.get('avg_pr','-')}"
            )

    tier = data.get("ship_tier") or {}
    if isinstance(tier, dict) and tier:
        top = sorted(tier.items(), key=lambda kv: -int(kv[1]))[:3]
        top_s = ", ".join(f"{k}级{v}场" for k, v in top if int(v) > 0)
        if top_s:
            parts.append(f"主要活动等级: {top_s}")

    return _truncate("\n".join(parts))


def extract_recent(data: dict, nickname: str | None = None) -> str:
    """近期汇总（/r1/recent-data/）-> 模型文本。"""
    if not isinstance(data, dict):
        return "数据为空"
    parts = [f"玩家: {nickname or data.get('nickname') or '?'}"]

    t = data.get("time") or {}
    if t.get("start_time") and t.get("end_time"):
        import datetime
        try:
            s = datetime.datetime.fromtimestamp(int(t["start_time"])).strftime("%m-%d %H:%M")
            e = datetime.datetime.fromtimestamp(int(t["end_time"])).strftime("%m-%d %H:%M")
            parts.append(f"统计区间: {s} ~ {e}")
        except (ValueError, OSError, OverflowError):
            pass

    parts.append(_pr_line(data.get("pr")))

    bt = data.get("battle_type") or {}
    if isinstance(bt, dict) and bt:
        parts.append("分模式战绩:")
        for k in sorted(bt):
            parts.append(_fmt_mode_block(k, bt[k]))

    ships = data.get("ships") or []
    if ships:
        parts.append(f"逐船明细（共 {len(ships)} 艘，按场次取前 8）:")
        def _b(x):
            try:
                return int(str((x or {}).get("ship_data", {}).get("battles_count", "0")).replace(" ", "") or 0)
            except (ValueError, AttributeError):
                return 0
        for s in sorted(ships, key=_b, reverse=True)[:8]:
            info = s.get("ship_info") or {}
            sd = _strip_render_fields(s.get("ship_data") or {})
            name = info.get("ship_name", "?")
            tier = info.get("ship_tier", "?")
            parts.append(
                f"  {name}({tier}级): {sd.get('battles_count','-')}场 "
                f"胜率={sd.get('win_rate','-')} 场均伤害={sd.get('avg_damage','-')} "
                f"场均击杀={sd.get('avg_frags','-')} PR={sd.get('avg_pr','-')}"
            )

    return _truncate("\n".join(parts))


def extract_ship(data: dict) -> str:
    """单船（/b/ship-data/）-> 模型文本。"""
    if not isinstance(data, dict):
        return "数据为空"
    info = data.get("ship_info") or {}
    name = info.get("ship_name", "?")
    tier = info.get("ship_tier", "?")
    stype = _SHIP_TYPE_CN.get(info.get("ship_type", ""), info.get("ship_type", "?"))
    parts = [f"船只: {name}（{tier}级 {stype}）"]

    parts.append(_pr_line(data.get("pr")))

    bt = data.get("battle_type") or {}
    if isinstance(bt, dict) and bt:
        parts.append("分模式战绩:")
        for k in sorted(bt):
            parts.append(_fmt_mode_block(k, bt[k]))

    dd = _strip_render_fields(data.get("detailed_data") or {})
    if dd:
        keep = ("survival_rate", "avg_planes_killed", "avg_potential_dmage",
                "avg_spotting_damage", "main_battery", "torpedo")
        bits = []
        cn_map = {"survival_rate": "存活率", "avg_planes_killed": "场均击落飞机",
                  "avg_potential_dmage": "场均潜在伤害", "avg_spotting_damage": "场均发现伤害",
                  "main_battery": "主炮命中", "torpedo": "鱼雷命中"}
        for k in keep:
            if k in dd and dd[k] not in ("-", None):
                bits.append(f"{cn_map.get(k, k)}={dd[k]}")
        if bits:
            parts.append("详细数据: " + " ".join(bits))

    return _truncate("\n".join(parts))


def extract_ships(data: dict, nickname: str | None = None) -> str:
    """舰种筛选列表（/b/ships-data/）-> 模型文本。"""
    if not isinstance(data, dict):
        return "数据为空"
    parts = [f"玩家: {nickname or data.get('nickname') or '?'}"]

    fc = data.get("filter_criteria") or {}
    if fc:
        bits = [f"{k}={v}" for k, v in _strip_render_fields(fc).items() if v not in ("-", None)]
        if bits:
            parts.append("筛选条件: " + " ".join(bits))

    pr = data.get("pr") or {}
    if pr.get("battles_count"):
        parts.append(_pr_line(pr))

    ships = data.get("ships") or []
    parts.append(f"命中 {len(ships)} 艘船:")
    rows = []
    for s in ships:
        info = s.get("ship_info") or {}
        sd = _strip_render_fields(s.get("ship_data") or {})
        try:
            n = int(str(sd.get("battles_count", "0")).replace(" ", "") or 0)
        except (ValueError, AttributeError):
            n = 0
        rows.append((n, info, sd))
    for n, info, sd in sorted(rows, key=lambda r: -r[0])[:12]:
        parts.append(
            f"  {info.get('ship_name','?')}({info.get('ship_tier','?')}级): "
            f"{n}场 胜率={sd.get('win_rate','-')} 场均伤害={sd.get('avg_damage','-')} "
            f"场均击杀={sd.get('avg_frags','-')} 存活率={sd.get('survival_rate','-')} "
            f"PR={sd.get('avg_pr','-')}"
        )
    if len(ships) > 12:
        parts.append(f"…（其余 {len(ships) - 12} 艘场次较少，已省略）")

    return _truncate("\n".join(parts))


def _truncate(text: str) -> str:
    if len(text) <= _MAX_CHARS:
        return text
    return text[:_MAX_CHARS] + "\n…（数据过长已截断）"


def _strip_render_deep(o):
    """递归剥离 *_color / *_text / *_dis / *_des 等渲染字段。"""
    if isinstance(o, dict):
        return {k: _strip_render_deep(v) for k, v in o.items()
                if not any(str(k).endswith(s) for s in _RENDER_KEYS)}
    if isinstance(o, list):
        return [_strip_render_deep(x) for x in o]
    return o


def generic_dump(data, nickname: str | None = None) -> str:
    """没有专用提取器的接口：递归剥渲染字段后整体给模型（模型自己读 JSON）。"""
    if data is None:
        return "无数据"
    parts = []
    if nickname:
        parts.append(f"玩家: {nickname}")
    parts.append(json.dumps(_strip_render_deep(data), ensure_ascii=False,
                            separators=(",", ":")))
    return _truncate("\n".join(parts))
