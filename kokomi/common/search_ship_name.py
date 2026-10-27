import gc
from .call_api import call_api
from .. import (
    write_error
)

def _foreign_name(it: dict, fallback: str) -> str:
    """取外文名：Lesta 索引的 nameEnglish 可能是中文，此时用 nameRu。"""
    def _has_cjk(s: str) -> bool:
        return any("\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff"
                   for c in str(s or ""))
    en = it.get("nameEnglish")
    ru = it.get("nameRu")
    if en and not _has_cjk(en):
        return str(en)
    if ru and not _has_cjk(ru):
        return str(ru)
    return str(en or ru or fallback)


def _local_ship_search(shipname: str) -> list:
    """本地船名索引兜底（自包含实现，不依赖模块加载状态）。

    ★ 2026-10-16 v2：初版走 sys.modules/相对导入去拿 kokomi_llm.ships，
    在 kokomi 假包环境里拿不到（静默 0 命中）→ 改为直接读索引 JSON 并
    内联实现与 find_ship_candidates 相同的匹配（精确/前缀/尾段）。
    """
    import json
    from pathlib import Path
    try:
        base = Path(__file__).resolve().parents[2] / "kokomi_llm" / "data"
        print(f"[diag-shipname] base={base} exists={base.is_dir()}", flush=True)
        q = str(shipname or "").strip()
        if not q:
            return []
        ql = q.lower().replace(" ", "")

        def _has_cjk(s):
            return any("\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff"
                       for c in str(s or ""))

        def _names_of(item):
            out = []
            for k in ("nameCn", "nameCn360", "nameEnglish", "nameRu", "alias"):
                v = item.get(k)
                if k == "nameEnglish" and isinstance(v, str) and _has_cjk(v):
                    continue  # ★ 索引的 nameEnglish 有时混入中文别名（如「塔林PV」->彼得罗扎沃茨克），不作匹配名（2026-10-16）
                v = item.get(k)
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
                elif isinstance(v, list):
                    out.extend(str(x).strip() for x in v if str(x).strip())
            return out

        merged, seen = [], set()
        for fname in ("ship_index_ru.json", "ship_index_wg.json"):
            fp = base / fname
            if not fp.is_file():
                continue
            try:
                items = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if isinstance(items, dict):
                items = list(items.values())
            if not isinstance(items, list):
                continue
            exact, prefix, tailseg = [], [], []
            for item in items:
                if not isinstance(item, dict):
                    continue
                names = _names_of(item)
                norm = [n.lower().replace(" ", "") for n in names if n.replace(" ", "")]
                if ql in norm:
                    exact.append(item)
                elif any(n.startswith(ql) for n in norm):
                    prefix.append(item)
                elif len(ql) >= 3 and any(
                        n.endswith(ql) and n[:-len(ql)][-1:] in ("·", "-", " ", ".", "’", "'")
                        for n in norm):
                    tailseg.append(item)
            for item in exact + prefix + tailseg:
                sid = item.get("shipId") or item.get("ship_id")
                if sid in seen:
                    continue
                seen.add(sid)
                entry = dict(item)
                entry["ship_id"] = sid
                entry["name"] = (item.get("nameCn") or item.get("nameEnglish")
                                 or item.get("nameRu") or shipname)
                merged.append(entry)
        merged.sort(key=lambda x: (
            0 if str(x.get("serverType") or "").upper() == "LESTA" else 1,
            -(int(x.get("level") or 0))))
        print(f"[diag-shipname] local-search merged={len(merged)}", flush=True)
        return merged[:20]
    except Exception as e:  # noqa: BLE001
        print(f"[diag-shipname] local-search 异常: {type(e).__name__}: {e}", flush=True)
        return []


async def search_ship_name(
    lang:str,
    shipname:str
) -> dict:
    parameter = [lang,shipname]
    try:
        path = '/p/search-name/'
        params = {
            'ship_name':shipname,
            'lang':lang
        }
        res = await call_api(
            params=params,
            path=path
        )
        if (
            res['status'] != 'ok' or 
            res['message'] != 'SUCCESS'
        ):
            return res
        result = res
        # ★ 接口∪本地并集（2026-10-16 v4，用户定案）：上游条目为主（先入并集、
        #   去重时保留上游条目及其字段），本地只补上游没有的船；
        #   但 cn/en 展示名一律按本地索引（ships_lesta.json）回填 —— 上游
        #   「拉扎列夫上将」→ 显示「拉扎列夫」；本地也没有的船保持上游名。
        #   并集 ≥3 条时命令引擎自动走候选列表交互。
        try:
            data = result.get("data") if isinstance(result, dict) else None
            if (isinstance(result, dict)
                    and result.get("status") == "ok"
                    and result.get("message") == "SUCCESS"
                    and isinstance(data, dict)):
                api_ships = data.get("ships") if isinstance(data.get("ships"), list) else []
                local = _local_ship_search(shipname)
                # 本地名字回填表：shipId(str) -> {cn, en}（来自本地索引，权威中文名）
                import json as _json
                _name_map = {}
                try:
                    from pathlib import Path as _P
                    _base = _P(__file__).resolve().parents[2] / "kokomi_llm" / "data"
                    for _fn in ("ship_index_ru.json", "ship_index_wg.json"):
                        _fp = _base / _fn
                        if not _fp.is_file():
                            continue
                        try:
                            _items = _json.loads(_fp.read_text(encoding="utf-8"))
                        except Exception:
                            continue
                        if not isinstance(_items, list):
                            continue
                        for _it in _items:
                            if isinstance(_it, dict) and _it.get("shipId") is not None:
                                _cn = str(_it.get("nameCn") or "").strip()
                                _en = str(_it.get("nameEnglish") or "").strip()
                                _ru = str(_it.get("nameRu") or "").strip()
                                _ctry = str(_it.get("country") or "").strip()
                                if _cn or _en or _ru:
                                    _name_map.setdefault(str(_it["shipId"]),
                                                         {"cn": _cn, "en": _en,
                                                          "ru": _ru, "nation": _ctry})
                except Exception as _e:
                    print(f"[diag-shipname] 名字回填表构建失败: {_e}", flush=True)
                # 排除黑名单（build 脚本生成的 ship_blocklist.json）：内部克隆/
                # 未实装船的 shipId —— 上游命名与 lesta 不同（基辅PV vs 基辅（活动）），
                # 按名字拦不住，须按 ID 拦（2026-10-16 v4.6）。
                _block = set()
                try:
                    _bp = _base / "ship_blocklist.json"
                    if _bp.is_file():
                        _block = {str(x) for x in _json.loads(_bp.read_text(encoding="utf-8"))}
                except Exception as _e:
                    print(f"[diag-shipname] 黑名单加载失败: {_e}", flush=True)
                merged, seen = [], set()
                for it in list(api_ships) + list(local):
                    if not isinstance(it, dict):
                        continue
                    sid = it.get("ship_id") or it.get("shipId")
                    sid_cmp = str(sid)  # ★ 归一化比较（int/str 混型去重，2026-10-16）
                    if sid_cmp in seen:
                        continue
                    seen.add(sid_cmp)
                    if isinstance(it.get("ship_data"), dict):
                        # 接口条目：原样（已带 ship_data 结构）
                        entry = dict(it)
                        entry["ship_id"] = sid
                    else:
                        # 本地索引条目：补成接口同构结构（候选图渲染读 ship_data.*）
                        lv = 0
                        try:
                            lv = int(it.get("level") or 0)
                        except Exception:  # noqa: BLE001
                            lv = 0
                        nm = (it.get("nameCn") or it.get("nameEnglish")
                              or it.get("nameRu") or shipname)
                        entry = {
                            "ship_id": sid,
                            "name": nm,
                            "level": lv,
                            "ship_data": {
                                "tier": lv,
                                "type": it.get("shipType") or "",
                                "cn": it.get("nameCn") or nm,
                                "en": _foreign_name(it, nm),
                                "ja": it.get("nameCn") or nm,
                            },
                        }
                    merged.append(entry)
                # ★ 展示名回填（2026-10-16 v4）：合并后按本地索引覆盖 cn/en，
                #   本地索引中文名即 ships_lesta.json 的 name_zh-cn（用户定案）。
                for entry in merged:
                    _sid = entry.get("ship_id") or entry.get("shipId")
                    _ov = _name_map.get(str(_sid)) if _sid is not None else None
                    if not _ov:
                        continue
                    _sd = entry.get("ship_data")
                    if not isinstance(_sd, dict):
                        continue
                    if _ov["cn"]:
                        entry["name"] = _ov["cn"]
                        _sd["cn"] = _ov["cn"]
                    if _ov["en"]:
                        _sd["en"] = _ov["en"]
                    # ★ 俄语名 + 国别回填（2026-10-16 v4.7）：俄系船候选图显示俄语名
                    if _ov.get("ru"):
                        _sd["ru"] = _ov["ru"]
                    if _ov.get("nation"):
                        _sd["nation"] = _ov["nation"]
                # ★ 排除内部活动克隆/方括号船（2026-10-16 v4.5，用户定案）：
                #   中文名以 EM/Test 结尾（彼得罗巴甫洛夫斯克EM、中途岛Test 等）
                #   或被方括号包裹（[藏王] 等公会奖励船）的不进候选，
                #   本地索引已不含它们，这里再拦上游回退的同类条目。
                import re as _re
                merged = [e for e in merged
                          if not (_re.search(r"(EM|Test)$",
                                             str((e.get("ship_data") or {}).get("cn")
                                                 or e.get("name") or "").strip())
                                  or _re.match(r"^\[.*\]$",
                                               str((e.get("ship_data") or {}).get("cn")
                                                   or e.get("name") or "").strip()))]
                if merged:
                    def _lvl(x):
                        try:
                            if x.get("level"):
                                return int(x.get("level"))
                            sd = x.get("ship_data") or {}
                            return int(sd.get("tier") or 0)
                        except Exception:  # noqa: BLE001
                            return 0
                    merged.sort(key=lambda x: (
                        0 if str(x.get("serverType") or "").upper() == "LESTA" else 1,
                        -_lvl(x)))
                    # ★ 精确名优先（2026-10-16）：查询词与某条目中文名归一化相等时，
                    #   只保留排序后的第一艘（通常即用户要查的本尊）→ 直查，不出候选。
                    _qn = str(shipname or "").lower().replace(" ", "")
                    _exact = [x for x in merged
                              if str((x.get("ship_data") or {}).get("cn") or "")
                              .lower().replace(" ", "") == _qn]
                    if _exact:
                        merged = [_exact[0]]
                        print(f"[diag-shipname] 精确名优先锁定: "
                              f"{(_exact[0].get('ship_data') or {}).get('cn')}", flush=True)
                    else:
                        # ★ 候选上限 20（2026-10-16 v4.3，用户定案）；
                        #   渲染器 name_list.get_png 高度随行数自适应，20 行已实测。
                        #   与 _local_ship_search 的 [:20] 上限一致。
                        merged = merged[:20]
                    result = {
                        "status": "ok",
                        "message": "SUCCESS",
                        "data": {"data_num": len(merged), "ships": merged},
                    }
                    print(f"[diag-shipname] 并集 data_num={len(merged)} "
                          f"api={len(api_ships)} local={len(local)}", flush=True)
                else:
                    # 全部被过滤（如查询本身就是 EM/Test 克隆）→ 返回空集，
                    # 不回落到含克隆船的上游原始结果（2026-10-16 v4.4）
                    result = {"status": "ok", "message": "SUCCESS",
                              "data": {"data_num": 0, "ships": []}}
        except Exception as e:  # noqa: BLE001
            print(f"[diag-shipname] 并集异常: {type(e).__name__}: {e}", flush=True)
        gc.collect()
        return result
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        track_id = write_error(
            error_file=__file__,
            error_params=parameter,
            error_name=str(type(e).__name__),
            error_info=error_info
        )
        return {
            'status': 'error', 
            'message': 'PROGRAM ERROR', 
            'error':f'{str(type(e).__name__)}', 
            'track_id': f'{track_id}'
        }
    finally:
        gc.collect()
