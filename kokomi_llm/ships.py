# -*- coding: utf-8 -*-
"""本地船名索引：补齐 Kokomi 上游中文名覆盖不全的问题。

背景：Kokomi 上游（43.155.60.190:8000）的 /p/search-name/ 中文名不全
（「塞德利茨」「鲁登道夫」这类俄服/新船都搜不到），而 yuyuko 用的
v3-api.wows.shinoaki.com 百科接口数据齐全，且 **shipId 与 Kokomi 完全同体系**
（实测：大和 4276041424、Ulpio Traiano 4074682096 两边一致）。

做法：把 shinoaki 百科的船名表全量扒成本地索引（data/ship_index.json，
1286 条，含 nameCn/nameCn360/nameEnglish/nameRu/shipId/level/shipType），
搜船时本地优先 —— 命中直接拿 shipId 调 Kokomi 接口，不再依赖上游搜索；
未命中再回退上游 /p/search-name/。

重建索引：tools/refresh_ship_index.py（或按本文件注释的抓取逻辑手动跑）。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
# 两服船表物理分开：ru 表只含 LESTA（俄服）条目，wg 表只含 WG（亚/国/欧/美）条目。
_INDEX_RU_PATH = os.path.join(_DATA_DIR, "ship_index_ru.json")
_INDEX_WG_PATH = os.path.join(_DATA_DIR, "ship_index_wg.json")


def _read_index(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@lru_cache(maxsize=1)
def _load_ru() -> list[dict]:
    return _read_index(_INDEX_RU_PATH)


@lru_cache(maxsize=1)
def _load_wg() -> list[dict]:
    return _read_index(_INDEX_WG_PATH)


def load_ship_index(prefer_server: str | None = None) -> list[dict]:
    """按服务器加载船名索引。

    prefer_server == "ru" → 只用 LESTA 表；否则用 WG 表。
    目标表为空时回退合并两表（避免拆表异常时整体查不到船）。
    """
    if prefer_server == "ru":
        table = _load_ru()
        if table:
            return table
    else:
        table = _load_wg()
        if table:
            return table
    return _load_ru() + _load_wg()


def _names_of(item: dict) -> list[str]:
    """取船的各语言名，过滤空值/纯空白（空串会让包含匹配命中一切）。"""
    out = []
    for k in ("nameCn", "nameCn360", "nameEnglish", "nameRu"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def find_ships(query: str, limit: int = 5,
               prefer_server: str | None = None) -> list[dict]:
    """按船名找船。优先级：全名精确 > 前缀匹配 > 包含。

    prefer_server：玩家绑定的服务器（"ru" 等）。WG 与 LESTA（俄服）是**两套
    独立船表**，shipId 互不通用 —— 查 ru 服账号必须用 LESTA 分区的 shipId，
    否则会得到错误的「没有玩过这艘船」。命中排序按分区优先。
    命中返回原始索引项（含 shipId / nameCn / nameEnglish / level / shipType），
    没命中返回空列表。
    """
    q = str(query or "").strip()
    if not q:
        return []
    ql = q.lower().replace(" ", "")

    # 严格匹配（用户定案）：只认精确与前缀，不做中缀联想
    # （「斯拉夫」绝不能联想到「伊贾斯拉夫」）。
    exact, prefix, contains = [], [], []
    qn = _lat_norm(q)
    for item in load_ship_index(prefer_server):
        names = _names_of(item)
        low = [n.lower() for n in names]
        norm = [n.replace(" ", "") for n in low if n.replace(" ", "")]
        # 俄文名的拉丁转写也参与精确比对（Zorkiy <-> Зоркий）
        translit = [_lat_norm(_translit(n)) for n in norm if any(c in _CYR_TO_LAT for c in n.lower())]
        if q in names or ql in norm or (qn and qn in translit):
            exact.append(item)
        elif ql and any(n.startswith(ql) for n in norm):
            prefix.append(item)
        elif ql and len(ql) >= 3 and any(
                n.endswith(ql) and n[:-len(ql)][-1:] in ("·", "-", " ", ".", "’", "'")
                for n in norm):
            # 尾段简称：乌尔皮乌斯·图拉真 -> 图拉真（分隔符边界）
            exact.append(item)
        elif ql and any(ql in n or n in ql for n in norm):
            # 模糊包含兜底（末位）：「斯拉夫」->「伊贾斯拉夫」这类联想。
            # 放最后 —— 前面的层命中就不会走到这里。
            contains.append(item)

    # 精确里优先「带真实外文名」的条目（nameCn 与 nameRu 都有信息量）
    exact.sort(key=lambda x: (x.get("nameRu") is None,))

    def server_weight(item):
        if not prefer_server:
            return 0
        st = str(item.get("serverType") or "").upper()
        # 俄服账号用 LESTA 表，其他服用 WG 表
        return 0 if ((prefer_server == "ru") == (st == "LESTA")) else 1

    # 别名优先（用户定案）：短前缀「尤里」会命中一堆带后缀的船
    # （尤里乌斯·恺撒 / 尤里安·格拉维 / 古斯塔夫·尤里乌斯·梅克尔），
    # 指定要优先返回「尤里·多尔戈鲁基」。
    # 值支持多写法（· / - 两表命名不同），任一命中即优先。
    _ALIAS_PREFER = {"尤里": ("尤里·多尔戈鲁基", "尤里-多尔戈鲁基")}

    def alias_weight(item):
        wants = _ALIAS_PREFER.get(q)
        if not wants:
            return 1
        cn = str(item.get("nameCn") or "").replace("-", "·")
        return 0 if any(cn == w.replace("-", "·") for w in wants) else 1

    exact.sort(key=lambda x: (alias_weight(x), server_weight(x), _level_key(x), x.get("nameRu") is None))
    prefix.sort(key=lambda x: (alias_weight(x), server_weight(x), _level_key(x)))
    contains.sort(key=lambda x: (alias_weight(x), server_weight(x), _level_key(x)))
    out = exact + prefix + contains
    return out[:limit]


def _level_key(item: dict):
    """等级降序排序键（9级排最前）；无 level 视作 0。"""
    try:
        return -int(item.get("level") or 0)
    except Exception:  # noqa: BLE001
        return 0


def find_ship_candidates(query: str, prefer_server: str | None = None,
                         limit: int = 8) -> list[dict]:
    """列出**同一服务器船表**内的候选船只（用于「1/2/3 选船」交互）。

    与 find_ships 的区别：不截断到首个命中，而是把同一分区里所有
    「高度相关」的条目按同一排序键返回，供用户按序号选择。

    严格限定单表：prefer_server == "ru" 只查 LESTA 表，否则只查 WG 表 ——
    候选绝不跨表混（用户定案）。返回项已按 shipId 去重。
    """
    q = str(query or "").strip()
    if not q:
        return []
    ql = q.lower().replace(" ", "")
    qn = _lat_norm(q)

    exact, prefix, tailseg, contains = [], [], [], []
    for item in load_ship_index(prefer_server):
        names = _names_of(item)
        low = [n.lower() for n in names]
        norm = [n.replace(" ", "") for n in low if n.replace(" ", "")]
        translit = [_lat_norm(_translit(n)) for n in norm
                    if any(c in _CYR_TO_LAT for c in n.lower())]
        if q in names or ql in norm or (qn and qn in translit):
            exact.append(item)
        elif ql and any(n.startswith(ql) for n in norm):
            prefix.append(item)
        elif ql and len(ql) >= 3 and any(
                n.endswith(ql) and n[:-len(ql)][-1:] in ("·", "-", " ", ".", "’", "'")
                for n in norm):
            tailseg.append(item)
        elif ql and len(ql) >= 3 and any(ql in n or n in ql for n in norm):
            contains.append(item)

    _ALIAS_PREFER = {"尤里": ("尤里·多尔戈鲁基", "尤里-多尔戈鲁基")}

    def alias_weight(item):
        wants = _ALIAS_PREFER.get(q)
        if not wants:
            return 1
        cn = str(item.get("nameCn") or "").replace("-", "·")
        return 0 if any(cn == w.replace("-", "·") for w in wants) else 1

    def server_weight(item):
        if not prefer_server:
            return 0
        st = str(item.get("serverType") or "").upper()
        return 0 if ((prefer_server == "ru") == (st == "LESTA")) else 1

    for bucket in (exact, prefix, tailseg, contains):
        bucket.sort(key=lambda x: (alias_weight(x), server_weight(x),
                                   _level_key(x), x.get("nameRu") is None))

    out, seen = [], set()
    for item in exact + prefix + tailseg + contains:
        sid = item.get("shipId") or item.get("ship_id")
        if sid in seen:
            continue
        seen.add(sid)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def ship_display_name(item: dict) -> str:
    cn = item.get("nameCn") or item.get("nameEnglish") or "?"
    ru = item.get("nameRu")
    return f"{cn}（{ru}）" if ru else str(cn)

# ---------- 西里尔 <-> 拉丁 转写（俄服船名用户常用拉丁写法） ----------

# 俄服船名（如 Зоркий / Москва）用户常打成拉丁转写（Zorkiy / Moskva）。
# BGN/PCGN 常见变体合并到同一目标；只做单向"西里尔->拉丁"，查名时对索引的
# 俄文名生成转写候选，与用户输入比对。
_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _translit(src: str) -> str:
    """俄文西里尔 -> 常见拉丁转写（小写）。"""
    out = []
    for ch in str(src or "").lower():
        if ch in _CYR_TO_LAT:
            out.append(_CYR_TO_LAT[ch])
        elif ch.isascii():
            out.append(ch)
    return "".join(out)


def _lat_norm(s: str) -> str:
    """拉丁名归一：小写、去空格与连字符（比对用）。"""
    return str(s or "").lower().replace(" ", "").replace("-", "")

