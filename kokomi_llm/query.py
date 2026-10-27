# -*- coding: utf-8 -*-
"""身份解析与取数渲染。

## 决策树（顺序敏感，勿调整）

    输入：消息里的 @组件、LLM 填的 server / nickname、发起人自己

    1. 消息带 @          -> 目标 = 被@的人的 QQ 号        -> QQ 号分支
    2. server + nickname -> 按名称搜人（/b/search-user/） -> 名称分支
    3. 仅 nickname       -> 群成员昵称匹配到 QQ 号        -> QQ 号分支
                          匹配不到 -> need_server（反问服务器）
    4. 都没有            -> 自己                          -> QQ 号分支

    QQ 号分支：get_bind_data(platform, uid)
        NO BIND DATA -> not_bound（提示先绑定）
        SUCCESS      -> 拿到 aid/server，正常查询
    名称分支：search-user(server, nickname)
        data 非空    -> 拿到 aid（多个同名取第一个，附带提示）
        data 为空    -> no_such_player（回复「无」）

    语义纪律：「查无此人」和「未绑定」是两种不同的没找到，绝不能混。

## 取数渲染：一次 API 调用喂两头

    call_api(params, path)          -> 原始 JSON（提取给模型）
    scripts.<mod>.get_png(result=…)  -> 渲染图（发给用户）

这正是原插件 get_data 内部的流程，这里只把它拆开复用，
保证与真寻侧行为逐字节一致（get_png 的输出已被 md5 验证过）。
"""

from __future__ import annotations

import asyncio
import os

from astrbot.api import logger
from astrbot.core.message.components import At, AtAll

# ---------------------------------------------------------------------
# 参数归一表
# ---------------------------------------------------------------------

# battle_type：指令参数 -> API 参数值（照抄 select_func_cn.py:1101）
_BATTLE_TYPE_API = {
    "pvp": "pvp", "随机": "pvp", "随机战": "pvp",
    "rank": "rank", "排位": "rank", "排位战": "rank",
    "solo": "pvp_solo", "单野": "pvp_solo", "单人": "pvp_solo",
    "div2": "pvp_div2", "自行车": "pvp_div2", "双排": "pvp_div2", "二人组队": "pvp_div2",
    "div3": "pvp_div3", "三轮车": "pvp_div3", "三排": "pvp_div3", "三人组队": "pvp_div3",
}

# recent 返回数据的模式键 -> 中文名（给模型看）
_BATTLE_TYPE_CN = {
    "pvp": "随机(全部)", "pvp_solo": "单野", "pvp_div2": "双排(自行车)",
    "pvp_div3": "三排(三轮车)", "rank": "排位", "rank_solo": "排位(单排)",
}

# recent 天数：这里只是防滥用的宽松钳制（防 LLM 填 99999 打爆上游），
# **真正的可查范围由上游服务器的数据留存决定** —— 超出时服务器返回
# DATE NOT FOUND，由话术层如实转告，不要在这里替服务器做决定。
# 实测：60/90/180 天均正常返回，365 天服务器返回 DATE NOT FOUND。
MAX_RECENT_DAYS = 365


def normalize_server(text: str | None, kp=None) -> str | None:
    """「俄服/ru/RU」-> 'ru'。优先用原插件 Message.server_dict，不足处补别名。"""
    if not text:
        return None
    key = str(text).strip().lower()
    if kp is not None:
        try:
            server_dict = kp._load("data_source").Message.server_dict
            if key in server_dict:
                return server_dict[key]
        except Exception:  # noqa: BLE001
            pass
    fallback = {"asia": "asia", "亚服": "asia", "na": "na", "美服": "na",
                "eu": "eu", "欧服": "eu", "ru": "ru", "俄服": "ru",
                "cn": "cn", "国服": "cn"}
    return fallback.get(key)


def normalize_battle_mode(text: str | None) -> str | None:
    """「单野/RANK/随机」-> API battle_type 值；识别不了返回 None。"""
    if not text:
        return None
    return _BATTLE_TYPE_API.get(str(text).strip().lower()) or _BATTLE_TYPE_API.get(str(text).strip())


def battle_mode_cn(key: str) -> str:
    return _BATTLE_TYPE_CN.get(str(key).lower(), str(key))


def clamp_days(days) -> int:
    try:
        d = int(days)
    except (TypeError, ValueError):
        return 7
    return max(1, min(d, MAX_RECENT_DAYS))


# 船型别名 -> API 的 ship_type 值（/b/ships-data/ 用英文枚举）
_SHIP_TYPE_ALIASES = {
    "submarine": "Submarine", "潜艇": "Submarine",
    "cruiser": "Cruiser", "巡洋": "Cruiser", "巡洋舰": "Cruiser",
    "battleship": "Battleship", "战列": "Battleship", "战列舰": "Battleship",
    "destroyer": "Destroyer", "驱逐": "Destroyer", "驱逐舰": "Destroyer",
    "aircarrier": "AirCarrier", "航母": "AirCarrier", "航空母舰": "AirCarrier",
    "battlecruiser": "BattleCruiser", "战巡": "BattleCruiser", "战列巡洋舰": "BattleCruiser",
}


def normalize_ship_type(text: str | None) -> str | None:
    """「潜艇/Submarine」-> 'Submarine'；识别不了返回 None。"""
    if not text:
        return None
    key = str(text).strip().lower()
    return _SHIP_TYPE_ALIASES.get(key) or _SHIP_TYPE_ALIASES.get(str(text).strip())


# ---------------------------------------------------------------------
# 身份解析
# ---------------------------------------------------------------------

def _extract_at_qq(event) -> str | None:
    """从消息组件里取第一个被@的普通成员。

    排除两类：@全体成员、**@机器人自己**。
    后者很重要 —— 用户经常为了唤醒 bot 而 @ 它（「@bot 查我的米诺陶」），
    那是唤醒动作不是查询目标；不排除的话 bot 的 QQ 会覆盖用户显式声明的
    qq_id，跑去查 bot 自己的绑定（多半未绑定，实测踩过）。
    """
    try:
        comps = event.message_obj.message or []
        self_id = str(getattr(event.message_obj, "self_id", "") or "")
        if not self_id:
            self_id = str(getattr(event, "get_self_id", lambda: "")() or "")
    except AttributeError:
        return None
    for c in comps:
        if isinstance(c, At) and not isinstance(c, AtAll):
            qq = str(c.qq)
            if qq.isdigit() and qq != self_id:
                return qq
    return None


async def _match_group_member(event, nickname: str) -> str | None:
    """把群昵称/群名片匹配成 QQ 号。仅 aiocqhttp 类平台可用，失败静默。"""
    try:
        gid = event.get_group_id()
        if not gid:
            return None
        members = await event.bot.call_action("get_group_member_list", group_id=int(gid))
        want = str(nickname).strip()
        for m in members or []:
            card = str(m.get("card") or "").strip()
            nick = str(m.get("nickname") or "").strip()
            if want and want in (card, nick):
                return str(m.get("user_id"))
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[kokomi-llm] 群成员匹配不可用: {type(e).__name__}")
    return None


async def resolve_target(kp, event, server: str | None = None,
                         nickname: str | None = None,
                         qq_id: str | None = None,
                         prefix: str = "wws") -> dict:
    """解析「这次查谁」。返回统一结构：

    {
      "status": "ok" | "no_such_player" | "not_bound" | "need_server" | "error",
      "aid": int|None, "server": str|None, "lang": str,
      "target_desc": str,          # 给模型的称呼，如「你自己」「被@的人」「玩家XXX(俄服)」
      "detail": str | None,        # 非 ok 时的解释
    }

    目标优先级：@某人 > 显式声明的 QQ 号（qq_id） > 服务器+昵称搜人 >
    仅昵称（群成员匹配/反问服务器） > 查自己。
    只有**显式声明**（@、<@!格式、明说「QQ xxx」）才走 QQ 绑定查询；
    未声明的纯数字默认按游戏 ID 走搜索。
    """
    gb = kp._load("common.get_bind")
    platform = "qq_bot"

    async def via_qq(uid: str, desc: str) -> dict:
        bind = await gb.get_bind_data(platform=platform, uid=uid)
        if bind.get("status") == "ok" and bind.get("message") == "NO BIND DATA":
            return {"status": "not_bound", "aid": None, "server": None,
                    "target_desc": desc,
                    "detail": f"{desc}还没有绑定游戏账号，请让 TA 先发送：{prefix} bind 服务器 游戏昵称"}
        if bind.get("status") != "ok" or bind.get("message") != "SUCCESS":
            return {"status": "error", "aid": None, "server": None, "target_desc": desc,
                    "detail": f"绑定信息查询失败：{bind.get('message')}"}
        d = bind["data"]
        return {"status": "ok", "aid": d.get("aid"), "server": d.get("server"),
                "lang": d.get("lang") or "cn", "target_desc": desc, "detail": None}

    # 1) @某人（最明确，优先级最高）
    at_qq = _extract_at_qq(event)
    if at_qq:
        return await via_qq(at_qq, "被@的群成员")

    me_qq = str(event.get_sender_id() or "")

    # 2) 用户**显式声明**了 QQ 号（工具参数 qq_id，来自「查QQ xxx」这类说法）
    #    -> 直接走 QQ 绑定查询。
    #    注意：没有声明的纯数字默认按游戏 ID/昵称走搜索 —— 有玩家昵称就是
    #    纯数字，不能自动劫持（用户 16:48 明确纠正过这个优先级）。
    if qq_id and str(qq_id).strip().isdigit():
        q = str(qq_id).strip()
        return await via_qq(q, f"QQ {q} 的绑定账号")

    # 3) 服务器 + 昵称 -> 搜人
    srv = normalize_server(server, kp)
    if srv and nickname:
        su = kp._load("common.search_user")
        r = await su.search_user(server=srv, nickname=str(nickname).strip())
        if r.get("status") != "ok" or r.get("message") != "SUCCESS":
            return {"status": "error", "aid": None, "server": srv,
                    "target_desc": str(nickname),
                    "detail": f"玩家搜索失败：{r.get('message')}"}
        cands = r.get("data") or []
        if not cands:
            return {"status": "no_such_player", "aid": None, "server": srv,
                    "target_desc": str(nickname),
                    "detail": f"在{srv}服没有找到名为「{nickname}」的玩家"}
        # 多个同名：与原插件行为一致取第一个，但把情况告诉模型
        first = cands[0]
        note = f"（同名玩家共 {len(cands)} 个，已取第一个）" if len(cands) > 1 else ""
        return {"status": "ok", "aid": first.get("aid"), "server": srv,
                "lang": "cn", "target_desc": f"{srv}服玩家「{nickname}」{note}",
                "detail": None}

    # 3) 仅昵称 -> 尝试群成员匹配
    if nickname and not srv:
        uid = await _match_group_member(event, str(nickname))
        if uid:
            return await via_qq(uid, f"群成员「{nickname}」")
        return {"status": "need_server", "aid": None, "server": None,
                "target_desc": str(nickname),
                "detail": f"群里没有叫「{nickname}」的成员；按游戏名搜索需要知道服务器，请先问清是哪个服务器（亚服/国服/欧服/美服/俄服）"}

    # 4) 默认查自己
    return await via_qq(me_qq, "你自己")


# ---------------------------------------------------------------------
# 取数 + 渲染（一次调用喂两头）
# ---------------------------------------------------------------------

async def fetch_and_render(kp, *, script: str, path: str, params: dict,
                           render_args: dict, want_image: bool = True) -> dict:
    """调 call_api 拿 JSON，并（可选）用原插件的 get_png 渲染同一份结果。

    返回 {"status","message","data","img"} ——
    data 是给提取层的原始 JSON；img 是给用户看的渲染图路径（可能为 None）。
    """
    call_api = kp._load("common.call_api").call_api
    res = await call_api(params=params, path=path)
    out = {"status": res.get("status"), "message": res.get("message"),
           "data": res.get("data"), "img": None,
           # 部分接口把 nickname 放在响应顶层而非 data 里（如 pvp-data）
           "nickname": res.get("nickname") or (res.get("data") or {}).get("nickname")}

    # ★ 船名中文化（2026-10-16）：俄服 API 返回的 ship_name 是俄语，
    #    用本地索引（ships_lesta 权威汉化）的 nameCn 覆盖，渲染层直接读。
    #    仅处理 ship_name 为字符串的接口（/b/ship-data、/r1/ship-recent-data 等）；
    #    /p/ships-data 的 ship_name 是 {cn,en,...} 字典，不在此覆盖。
    try:
        _si = (res.get("data") or {}).get("ship_info")
        if isinstance(_si, dict) and isinstance(_si.get("ship_name"), str):
            _sid = _si.get("ship_id") or _si.get("shipId") or params.get("ship_id")
            if _sid is not None:
                _cn = kp._load("common.ship_cn").ship_cn_name(_sid)
                if _cn:
                    _si["ship_name"] = _cn
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[kokomi-llm] 船名中文化跳过: {type(e).__name__}: {e}")

    # ★ 行级船名中文化（2026-10-16 v2）：近期战绩等卡片的 ships[] 行带 ship_index
    #   （如 PGSB211），用「代号→中文名」映射覆盖 ship_name，卡片回退与 LLM 文本同步。
    try:
        _rows = (res.get("data") or {}).get("ships")
        if isinstance(_rows, list):
            _cmap = kp._load("common.ship_code_name").code_cn_map()
            for _r in _rows:
                _ri = _r.get("ship_info") if isinstance(_r, dict) else None
                if isinstance(_ri, dict) and isinstance(_ri.get("ship_name"), str):
                    _cnc = _cmap.get(str(_ri.get("ship_index") or ""))
                    if _cnc:
                        _ri["ship_name"] = _cnc
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[kokomi-llm] 行级船名中文化跳过: {type(e).__name__}: {e}")

    if out["status"] != "ok" or out["message"] != "SUCCESS" or not want_image:
        return out

    # 渲染放线程池：PIL 画图是同步 CPU 活
    def _render():
        mod = kp.module(script)
        get_png = getattr(mod, "get_png", None)
        if get_png is None:
            return None
        # Picture 类定义在原插件 data_source.py，由包级 __init__ 再导出；
        # shim 顶层命名空间里拿（common.picture 模块里没有它）
        data_source = kp._load("data_source")
        img = get_png(result=res, **render_args)
        ret = data_source.Picture.return_img(img=img)
        return ret.get("img") if isinstance(ret, dict) else None

    try:
        out["img"] = await asyncio.to_thread(_render)
        if out["img"] and not os.path.isfile(out["img"]):
            out["img"] = None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[kokomi-llm] 渲染失败（不影响数据返回）: {type(e).__name__}: {e}")
        out["img"] = None
    return out
