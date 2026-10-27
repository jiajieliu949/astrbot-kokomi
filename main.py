# -*- coding: utf-8 -*-


"""Kokomi 战绩渲染 —— AstrBot 插件入口。





## 这个插件是什么





把 NoneBot2 版 **Kokomi_bot_plugin**（原本跑在真寻上）的**全部渲染能力**


搬进 AstrBot，代码一行未改，靠 ``kokomi_loader.py`` 绕开原插件的 NoneBot 胶水层。





指令、取数、画图、素材全部来自原插件；本文件只负责：





1. 接住 AstrBot 的指令事件；


2. 把消息交给原插件的指令路由（``command_select.select_funtion``）；


3. 按原插件的返回协议（``{"type": "img"|"msg", ...}``）把结果发出去。





## 与原插件的职责边界（重要）





| 职责 | 由谁负责 |


|---|---|


| 消息切词、子指令识别、参数解析 | 原插件 ``command_select`` |


| 调用上游 API 取数据 | 原插件 ``scripts/*.py`` |


| 完整绘图（含舰徽三层叠加） | 原插件 ``scripts/*.py`` + ``common/dog_tag.py`` |


| 接指令 / 发图片 / 异常兜底 | **本文件** |





## AstrBot 插件发现机制（踩坑提示）





AstrBot 按 ``data.plugins.<插件目录>.main`` 匹配处理器，判定条件是


``handler.__module__ == metadata.module_path``。


所以**带 ``@filter.command`` / ``@llm_tool`` 的方法必须写在 main.py 里**，


拆到子模块会因为模块路径对不上而静默不生效。





## 绑定数据





绑定走上游 API（按 ``platform + user_id`` 查），所以**真寻侧绑过的账号在


AstrBot 侧可直接复用**，无需重复绑定。未绑定时原插件会返回提示文案。


"""





import asyncio


import functools


import os


import re


import time



from astrbot.api import AstrBotConfig, logger, llm_tool


from astrbot.api.event import filter, AstrMessageEvent


from astrbot.api.star import Context, Star


from astrbot.core.message.components import At, AtAll, Plain


from astrbot.core.message.message_event_result import MessageChain





from .kokomi_loader import KokomiLoadError, KokomiPlugin, audit_assets


from .kokomi_llm import (


    RateLimiter,


    clamp_days,


    extract_account,


    extract_recent,


    extract_ship,


    extract_ships,


    fetch_and_render,


    generic_dump,


    humanize_api_error,


    normalize_battle_mode,


    normalize_server,


    normalize_ship_type,


    resolve_target,


)





# 指令前缀。yuyuko 插件移除后，wws 由本插件独占，默认回归 wws。


# 面板可改；改成别的值时会动态注册，wws 仍保留（见 initialize）。


DEFAULT_COMMAND = "wws"





# 免唤醒监听接受的前缀（对齐真寻 on_startswith 的裸前缀行为）


_PLAIN_PREFIXES = ("wwsx", "wws")





# LLM 工具名 -> 面板开关键（抄 yuyuko 的 TOOL_SWITCH_FIELDS 模式）


TOOL_SWITCH_FIELDS = {


    "kokomi_account": "llm_tool_enable_account",


    "kokomi_recent": "llm_tool_enable_recent",


    "kokomi_recent_random": "llm_tool_enable_recent_random",


    "kokomi_recent_rank": "llm_tool_enable_recent_rank",


    "kokomi_recent_battles": "llm_tool_enable_recent_battles",


    "kokomi_ship": "llm_tool_enable_ship",


    "kokomi_ships": "llm_tool_enable_ships",


    "kokomi_ship_recent": "llm_tool_enable_ship_recent",


    "kokomi_bind": "llm_tool_enable_bind",


    "kokomi_ship_batch": "llm_tool_enable_ship_batch",


    "kokomi_info": "llm_tool_enable_info",


    "kokomi_card": "llm_tool_enable_card",


    "kokomi_oper": "llm_tool_enable_oper",


    "kokomi_cw": "llm_tool_enable_cw",


    "kokomi_rank": "llm_tool_enable_rank",


    "kokomi_rank_season": "llm_tool_enable_rank_season",


    "kokomi_clan_info": "llm_tool_enable_clan_info",


    "kokomi_clan_season": "llm_tool_enable_clan_season",


    "kokomi_clan_history": "llm_tool_enable_clan_history",


    "kokomi_me_ship_rank": "llm_tool_enable_me_ship_rank",


    "kokomi_ship_server_rank": "llm_tool_enable_ship_server_rank",


    "kokomi_ship_server_stats": "llm_tool_enable_ship_server_stats",


    "kokomi_online": "llm_tool_enable_online",


    "kokomi_search_ship": "llm_tool_enable_search_ship",


    "kokomi_server_ships": "llm_tool_enable_server_ships",


}





# Kokomi 代码所在目录（与本文件同级）


KOKOMI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kokomi")








class _NoOpLock:


    """空操作异步锁：保持 `async with self._lock` 代码结构，但不阻塞。





    并发安全性由原插件自身保证（NoneBot 侧多用户并发运行多年，


    字体启动时加载、渲染每请求独立对象）。曾经的 asyncio.Lock() 会让


    并发查询排队（每个 5-10 秒），连发消息只出第一个 —— 已移除。


    """





    async def __aenter__(self):


        return self





    async def __aexit__(self, *exc):


        return False








def _find_clan_id(data, _depth=0):


    """递归在任意结构里找第一个 clan_id 值。"""


    if _depth > 6 or data is None:


        return None


    if isinstance(data, dict):


        for k, v in data.items():


            if k == "clan_id" and v:


                return v


        for v in data.values():


            r = _find_clan_id(v, _depth + 1)


            if r:


                return r


    elif isinstance(data, list):


        for x in data:


            r = _find_clan_id(x, _depth + 1)


            if r:


                return r


    return None








def _norm_ship_text(s: str) -> str:


    """归一化：去掉分隔符/空白/大小写差异，用于高置信比对。"""


    return re.sub(r"[\s·・\-—_.,、，/|]+", "", (s or "").lower())








def _is_high_confidence(cand: str, hit: dict) -> bool:


    """直查层专用：判断「候选串」与「命中的船」是否属于高置信匹配。





    直查层绕过 LLM，必须极度保守 —— 只接受整段就是船名（或其别名）的情况：


      ① 归一化后完全相等；或


      ② 候选是**单个词**且是船名的前缀（如「北安普」→「北安普敦」）；或


      ③ 候选等于船名以分隔符（·）切出的某个分段（如「图拉真」→「乌尔皮乌斯·图拉真」）。


    **明确排除模糊包含** —— 「一下qq123的乌沙科夫」这种残片只是恰好包含了船名，


    它不是裸船名，必须交给 LLM 解析语义。判据：残片归一化后既不等、也不是前缀、


    也不是分段，就会被判为低置信而放行 LLM。


    """


    c = _norm_ship_text(cand)


    if not c:


        return False


    names = []


    for key in ("nameCn", "nameCn360", "nameEnglish", "nameRu"):


        v = hit.get(key)


        if isinstance(v, str) and v.strip():


            names.append(v)


    alias = hit.get("aliases") or hit.get("alias")


    if isinstance(alias, list):


        names.extend([a for a in alias if isinstance(a, str)])


    for n in names:


        nn = _norm_ship_text(n)


        if not nn:


            continue


        if c == nn:                                   # 完全相等


            return True


        # 前缀匹配：候选必须够长（≥2 字）且是船名前缀，避免「德」命中一切


        if len(c) >= 2 and nn.startswith(c):


            return True


    # 分隔符分段：船名里以「·」等分隔，候选等于其中某一段（图拉真 ← 乌尔皮乌斯·图拉真）


    for n in names:


        if not isinstance(n, str) or "·" not in n:


            continue


        for seg in n.split("·"):


            if _norm_ship_text(seg) == c:


                return True


    # 候选自身带分隔符时，尾段等于船名（乌尔皮乌斯·图拉真 ← 图拉真）


    if "·" in cand:


        tail = _norm_ship_text(cand.rsplit("·", 1)[-1])


        for n in names:


            if tail and tail == _norm_ship_text(n):


                return True


    return False








def tool_guard(func):


    """LLM 工具统一异常兜底：任何异常都变成给模型的文本，不让事件循环炸掉。"""





    @functools.wraps(func)


    async def wrapper(self, event, *args, **kwargs):


        try:


            return await func(self, event, *args, **kwargs)


        except Exception as e:  # noqa: BLE001


            logger.error(f"[kokomi-llm] 工具 {func.__name__} 异常: {e!r}", exc_info=True)


            return f"查询程序出现内部异常（{type(e).__name__}），请稍后再试或反馈给管理员。"





    return wrapper








class KokomiBridge(Star):


    """Kokomi 渲染后端接入层。"""





    def __init__(self, context: Context, config: AstrBotConfig):


        super().__init__(context)


        self.config = config





        def _cfg(key: str, default):


            if config is None:


                return default


            try:


                v = config.get(key, default)


            except AttributeError:


                v = getattr(config, key, default)


            return default if v is None else v





        self.command = str(_cfg("command", DEFAULT_COMMAND)).strip() or DEFAULT_COMMAND





        self._kp: KokomiPlugin | None = None


        # 串行化对原插件的调用：原插件用固定的 temp/ 目录与全局字体缓存，


        # 并发调用虽然基本安全，但排队最稳（也避免同一账号重复打上游接口）。


        self._lock = _NoOpLock()


        # 上游并发限流：同一时刻最多 2 个请求在途（实测 4 连发同打上游会挂起）


        self._upstream_sem = asyncio.Semaphore(2)


        # LLM 工具限流（每会话；<=0 不限流，对齐 yuyuko 的 llm_tool_rate_limit）


        rate = int(_cfg("llm_tool_rate_limit", 10))


        self._limiter = RateLimiter(max_calls=rate)


        self._llm_enabled = bool(_cfg("llm_tool_enable", True))


        self._llm_auto_image = bool(_cfg("llm_auto_image", True))


        # 关闭点评 = 返回文本里附带「只汇报数据」的指令，约束模型别自由发挥


        self._llm_evaluate = bool(_cfg("llm_tool_evaluate", True))

        # 多命中候选交互：session_key -> 待选状态 / 超时任务
        self._pick_pending: dict = {}
        self._pick_tasks: dict = {}


    # ------------------------------------------------------------------


    # 生命周期


    # ------------------------------------------------------------------





    async def initialize(self):


        """插件加载时把随包分发的 Kokomi 代码 shim 进来。"""


        try:


            # 放 to_thread：__init__ 段会加载 12+ 个字体文件与素材索引，


            # 是同步阻塞 IO，直接在事件循环里做会卡住 AstrBot。


            self._kp = await asyncio.to_thread(KokomiPlugin, KOKOMI_DIR)


        except KokomiLoadError as e:


            logger.error(f"[kokomi] 加载失败：{e}")


            self._kp = None


            return





        cfg = self._kp.plugin_config


        scripts = KokomiPlugin.available_scripts(KOKOMI_DIR)


        logger.info(


            f"[kokomi] 加载成功：{len(scripts)} 个指令 · "


            f"上游 {cfg.API_URL} · Kokomi {cfg.VERSON}"


        )





        # 素材完整性：缺 dog_tag_custom 之类不会报错，只会静默换背景，


        # 所以在这里提前告警，别等用户来投诉。


        missing = audit_assets(KOKOMI_DIR)


        if missing:


            for rel, why in missing:


                logger.warning(f"[kokomi] 素材缺失 {rel} —— {why}")





        # ------------------------------------------------------------------


        # 动态注册面板配置的指令前缀


        #


        # 为什么不能用装饰器读配置：@filter.command 在类定义时求值，那时


        # config 还没传进来。为什么这里安全：注册表按「模块_函数名」去重，


        # 对同一个已绑定方法再注册一次只会**追加**新的 CommandFilter 到


        # 现有 handler metadata（实例绑定发生在本方法之前，不受影响），


        # 静态注册的 wwsx 保底仍在。


        # ------------------------------------------------------------------


        cmd = (self.command or "").strip()


        if cmd and cmd != DEFAULT_COMMAND:


            try:


                filter.command(cmd)(self.wwsx)


                logger.info(


                    f"[kokomi] 指令前缀已生效：{cmd}（默认 {DEFAULT_COMMAND} 仍可用）"


                )


                if cmd == "wws":


                    # 只有 yuyuko 插件还在时才真的冲突（用户删了它就没事）


                    yuyuko_alive = os.path.isdir(


                        os.path.join(os.path.dirname(KOKOMI_DIR),


                                     "AstrByWowsYuyukoBot")


                    )


                    if yuyuko_alive:


                        logger.warning(


                            "[kokomi] 前缀 wws 与 AstrByWowsYuyukoBot 冲突："


                            "同一条 wws 指令两个插件都会响应（双图）。"


                            "如非有意替换 yuyuko，建议改回 wwsx 或先停用 yuyuko 插件。"


                        )


                    else:


                        logger.info("[kokomi] yuyuko 插件已移除，wws 前缀由本插件独占")


            except Exception as e:  # noqa: BLE001


                logger.warning(


                    f"[kokomi] 动态注册指令 {cmd!r} 失败: {type(e).__name__}: {e}"


                )





        # per-tool 独立开关（抄 yuyuko 的 TOOL_SWITCH_FIELDS 模式）：


        # 关闭的工具直接从模型视野消失（deactivate），省 token 也防误调。


        for tool_name, field in TOOL_SWITCH_FIELDS.items():


            if not self._tool_enabled(field):


                try:


                    await self.context.deactivate_llm_tool_async(tool_name)


                    logger.info(f"[kokomi] LLM 工具 {tool_name} 已按面板配置停用")


                except Exception as e:  # noqa: BLE001


                    logger.warning(f"[kokomi] 停用 {tool_name} 失败: {e}")





    def _tool_enabled(self, field: str) -> bool:


        """读面板的 per-tool 开关，缺省视为启用。"""


        try:


            v = self.config.get(field, True) if self.config else True


        except AttributeError:


            v = getattr(self.config, field, True)


        if isinstance(v, str):


            return v.strip().lower() not in ("false", "0", "no", "off", "")


        return True if v is None else bool(v)

    def _is_group_blacklisted(self, event: AstrMessageEvent) -> bool:
        """黑名单按群号匹配；私聊和未配置群不受影响。"""
        try:
            group_id = str(event.get_group_id() or "").strip()
            entries = self.config.get("group_blacklist", []) if self.config else []
        except (AttributeError, TypeError):
            return False
        if not group_id or not isinstance(entries, (list, tuple, set)):
            return False
        return group_id in {str(item).strip() for item in entries if item is not None}





    async def terminate(self):


        """卸载。渲染产物留在 kokomi/temp/，由运维清理。"""


        self._kp = None


        logger.info("[kokomi] 已卸载")





    # ------------------------------------------------------------------


    # 指令入口


    # ------------------------------------------------------------------





    @filter.command(DEFAULT_COMMAND)


    async def wwsx(self, event: AstrMessageEvent):


        """`wws <子指令>` —— 完整复用原 Kokomi 插件的指令集。





        例：wws me / wws me info / wws rank / wws bind ru <昵称>


        """


        if self._is_group_blacklisted(event):
            return

        if self._kp is None:


            yield event.plain_result("Kokomi 渲染后端未加载成功，请查看 AstrBot 日志。")


            return





        # 取出前缀之后的正文，再还原成原插件约定的 `wws ...`


        # （唤醒消息可能带 '!' 前缀，剥掉以免干扰后面的切词）


        raw = (event.message_str or "").strip().lstrip("!").strip()


        parts = raw.split(maxsplit=1)


        body = parts[1].strip() if len(parts) > 1 else ""





        if not body:


            yield event.plain_result(


                f"Kokomi 战绩查询\n"


                f"用法：{self.command} <子指令>\n"


                f"例：{self.command} me（个人卡）/ {self.command} me info（总表）\n"


                f"    {self.command} rank（排行榜）/ {self.command} bind ru <昵称>（绑定）"


            )


            return





        try:


            result = await self._dispatch(event, f"wws {body}")


        except Exception as e:  # noqa: BLE001


            logger.error(f"[kokomi] 处理 {body!r} 异常：{e!r}", exc_info=True)


            yield event.plain_result(f"查询出错：{type(e).__name__}")


            return





        kind = result.get("type")

        if kind == "pick_candidates":
            try:
                _img = await self._register_pick_from_candidates(event, result)
                if _img:
                    yield event.image_result(_img)
                else:
                    yield event.plain_result(self._pick_text_from_candidates(result))
            except Exception as _e:  # noqa: BLE001
                logger.error(f"[kokomi] 候选注册失败：{_e!r}", exc_info=True)
                yield event.plain_result("候选列表生成失败，请看日志。")
            return

        if kind == "img":


            img = result.get("img")


            if isinstance(img, str) and os.path.isfile(img):


                yield event.image_result(img)


            elif isinstance(img, (bytes, bytearray)):


                yield event.image_result(self._dump_bytes(img))


            else:


                logger.error(f"[kokomi] 图片产物无法识别：{img!r}")


                yield event.plain_result("渲染完成但图片无法读取，请查看日志。")


        else:


            yield event.plain_result(str(result.get("msg") or "没有拿到结果。"))





    # ------------------------------------------------------------------


    # 内部


    # ------------------------------------------------------------------





    async def _dispatch(self, event: AstrMessageEvent, plugin_msg: str) -> dict:


        """把一条 `wws xxx` 交给原插件路由，返回其原始结果字典。"""


        assert self._kp is not None


        async with self._lock:


            sender_id = str(event.get_sender_id() or "")


            try:


                group_id = str(event.get_group_id() or "") or "123456"


            except Exception:  # 某些适配器没有群概念


                group_id = "123456"





            return await self._kp.route(


                msg=plugin_msg.split(),


                user_id=sender_id,


                platform="qq_bot",


                platform_id="123456",


                channel_id=group_id,


            )





    @staticmethod


    def _dump_bytes(data: bytes) -> str:


        """把内存图片落到临时目录，返回路径（原插件一般直接给路径，这是兜底）。"""


        import hashlib


        import tempfile





        d = os.path.join(tempfile.gettempdir(), "kokomi_bridge")


        os.makedirs(d, exist_ok=True)


        p = os.path.join(d, f"{hashlib.md5(data).hexdigest()[:16]}.png")


        if not os.path.isfile(p):


            with open(p, "wb") as f:


                f.write(data)


        return p





    # ------------------------------------------------------------------


    # 免唤醒监听（对齐真寻 on_startswith 的裸前缀行为）


    #


    # 为什么需要：AstrBot 的指令 handler 默认要求唤醒（@机器人 或 '!' 前缀），


    # 而真寻是 on_startswith 直接匹配 —— 用户发 `wws <@!123> ship i2`（at 的是


    # 别人）在真寻有反应、在 AstrBot 没反应，就是这个差异。


    #


    # 做法：监听全部消息，识别 wws/wwsx 前缀后**按组件顺序重建 token 流**——


    # At 组件转成 CQ 码（原插件 command_select 认这个格式并会解析出被 at 的人），


    # 文本按空格切词。手打的 `<@!123>` 保持原文（原插件同样认）。


    # 已唤醒的消息跳过（留给 command handler，避免双响应）。


    # ------------------------------------------------------------------





    @filter.event_message_type(filter.EventMessageType.ALL, priority=999)


    async def on_wws_plain(self, event: AstrMessageEvent):


        if self._is_group_blacklisted(event):
            return

        if self._kp is None:


            return


        # ---- 候选序号回复（最前置，命中即消费）----


        try:


            if await self._handle_ship_pick(event):


                return


        except Exception as e:  # noqa: BLE001


            logger.debug(f"[kokomi] 候选选择处理异常: {type(e).__name__}: {e}")





        # ---- 原有：免唤醒 wws 前缀分支 ----


        if event.is_at_or_wake_command:


            return





        # 按组件顺序重建 token 流


        tokens: list[str] = []


        for comp in (event.message_obj.message or []):


            if isinstance(comp, At) and not isinstance(comp, AtAll):


                tokens.append(f"[CQ:at,qq={comp.qq}]")


            elif isinstance(comp, Plain):


                tokens.extend(str(getattr(comp, "text", comp)).split())


        if not tokens or tokens[0] not in _PLAIN_PREFIXES:


            return





        # 手打的前缀可能是 wwsx —— 原插件只认 wws/*，归一成 wws


        if tokens[0] == "wwsx":


            tokens[0] = "wws"


        if len(tokens) == 1:


            yield event.plain_result(


                f"Kokomi 战绩查询：{self.command} me / {self.command} me info / "


                f"{self.command} rank / {self.command} bind 服务器 昵称"


            )


            event.stop_event()


            return





        try:


            result = await self._dispatch_tokens(event, tokens)


        except Exception as e:  # noqa: BLE001


            logger.error(f"[kokomi] 免唤醒处理 {tokens!r} 异常：{e!r}", exc_info=True)


            yield event.plain_result(f"查询出错：{type(e).__name__}")


            event.stop_event()


            return





        kind = result.get("type")

        if kind == "pick_candidates":
            try:
                _img = await self._register_pick_from_candidates(event, result)
                if _img:
                    yield event.image_result(_img)
                else:
                    yield event.plain_result(self._pick_text_from_candidates(result))
            except Exception as _e:  # noqa: BLE001
                logger.error(f"[kokomi] 候选注册失败：{_e!r}", exc_info=True)
                yield event.plain_result("候选列表生成失败，请看日志。")
            return

        if kind == "img":


            img = result.get("img")


            if isinstance(img, str) and os.path.isfile(img):


                yield event.image_result(img)


            else:


                yield event.plain_result("渲染完成但图片无法读取，请查看日志。")


        else:


            yield event.plain_result(str(result.get("msg") or "没有拿到结果。"))


        # 命中指令后终止传播，别让 LLM 对同一条消息再接话


        event.stop_event()





    async def _dispatch_tokens(self, event: AstrMessageEvent, tokens: list[str]) -> dict:


        """把重建好的 token 列表交给原插件路由（_dispatch 的列表版）。"""


        assert self._kp is not None


        async with self._lock:


            sender_id = str(event.get_sender_id() or "")


            try:


                group_id = str(event.get_group_id() or "") or "123456"


            except Exception:  # 某些适配器没有群概念


                group_id = "123456"


            return await self._kp.route(


                msg=tokens,


                user_id=sender_id,


                platform="qq_bot",


                platform_id="123456",


                channel_id=group_id,


            )





    # ==================================================================


    # LLM 工具层（自然语言查询）


    #


    # 分工：本文件只放 @llm_tool 声明（AstrBot 按模块路径匹配，拆走会失效）；


    # 解析/取数/提取逻辑在 kokomi_llm/ 包里。


    # 目标解析决策树见 kokomi_llm/query.py 的 resolve_target：


    #   @某人 -> QQ号绑定表；服务器+昵称 -> 搜人；仅昵称 -> 群成员匹配；


    #   都没有 -> 查自己。名称查不到回「无」，未绑定提示绑定，两者不混。


    # ==================================================================





    def _cfg_bool(self, key: str, default: bool) -> bool:


        try:


            v = self.config.get(key, default) if self.config else default


        except AttributeError:


            v = getattr(self.config, key, default)


        if isinstance(v, str):


            return v.strip().lower() not in ("false", "0", "no", "off", "")


        return default if v is None else bool(v)





    async def _send_image(self, event: AstrMessageEvent, img_path: str) -> None:


        """渲染图直接发给用户（不经过模型），文本另走返回值。"""


        try:


            await event.send(MessageChain().file_image(img_path))


        except Exception as e:  # noqa: BLE001


            logger.warning(f"[kokomi-llm] 发图失败（不影响文本）: {type(e).__name__}: {e}")





    @tool_guard


    async def _query_account(self, event: AstrMessageEvent, server=None, nickname=None, qq_id=None) -> str:


        """水表查询的公共流程（kokomi_account 工具体）。"""


        tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


        if tg["status"] != "ok":


            return tg.get("detail") or "无法确定查询目标。"





        lang = tg.get("lang") or "cn"


        params = {"aid": tg["aid"], "server": tg["server"], "lang": lang,


                  "use_pr": True, "use_ac": False, "ac": []}


        # 照原插件 get_data 的规则：use_ac=False 时从 params 删键


        params.pop("use_ac", None); params.pop("ac", None)





        res = await fetch_and_render(


            self._kp, script="wws_basic", path="/b/pvp-data/", params=params,


            render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


            want_image=self._llm_auto_image,


        )


        if res["img"]:


            await self._send_image(event, res["img"])


        if res["status"] != "ok" or res["message"] != "SUCCESS":


            return f"{tg['target_desc']}的查询未成功：{humanize_api_error(res)}"


        return await self._deliver_data_or_return(


                event, extract_account(res["data"], nickname=res.get("nickname")),


                img_sent=bool(res.get("img")))





    @tool_guard


    async def _query_recent(self, event: AstrMessageEvent, days=None,


                            battle_mode=None, server=None, nickname=None, qq_id=None) -> str:


        """近期汇总查询的公共流程（kokomi_recent 工具体）。"""


        tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


        if tg["status"] != "ok":


            return tg.get("detail") or "无法确定查询目标。"





        lang = tg.get("lang") or "cn"


        mode = normalize_battle_mode(battle_mode) or "pvp"


        n = clamp_days(days)


        tz = self._kp._load("common.time_zone")


        start_date, end_date = tz.get_str_server_time(server=tg["server"], date_num=n)





        params = {"aid": tg["aid"], "server": tg["server"], "lang": lang,


                  "battle_type": mode, "start_date": start_date, "end_date": end_date,


                  "use_pr": True, "use_ac": False, "ac": []}


        params.pop("use_ac", None); params.pop("ac", None)





        res = await fetch_and_render(


            self._kp, script="wws_recent", path="/r1/recent-data/", params=params,


            render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


            want_image=self._llm_auto_image,


        )


        if res["img"]:


            await self._send_image(event, res["img"])


        if res["status"] != "ok" or res["message"] != "SUCCESS":


            return (f"{tg['target_desc']}最近{n}天的查询未成功：{humanize_api_error(res)}")


        text = extract_recent(res["data"], nickname=res.get("nickname"))


        return await self._deliver_data_or_return(


                event, f"[统计范围: 最近{n}天, 模式: {mode}]\n{text}",


                img_sent=bool(res.get("img")))





    @tool_guard


    async def _query_ship(self, event: AstrMessageEvent, ship_name: str,


                          server=None, nickname=None, qq_id=None) -> str:


        """单船查询的公共流程（kokomi_ship 工具体）。"""


        tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


        if tg["status"] != "ok":


            return tg.get("detail") or "无法确定查询目标。"





        lang = tg.get("lang") or "cn"


        # 多命中 → 列候选让用户选（唯一命中/0 命中走原流程）


        try:


            pick_text = await self._list_ship_candidates(event, ship_name, tg)


            if pick_text:


                try:


                    await event.send(MessageChain().message(pick_text))


                except Exception:  # noqa: BLE001


                    pass


                return ("候选列表已直接发送给用户（文字形式）。本轮不要再输出任何内容——"
                        "不要发「查QQ…」类前言、不要复述候选、不要加解释；"
                        "如果系统强制要求有回复，只发一个「。」。")


        except Exception as e:  # noqa: BLE001


            logger.debug(f"[kokomi] 候选列举失败: {type(e).__name__}: {e}")


        sid, found = await self._resolve_ship_id(ship_name, lang, server=tg.get("server"))


        if not sid:


            return f"没有找到名为「{ship_name}」的船只，请确认名称。"


        note = ""





        params = {"aid": tg["aid"], "server": tg["server"], "lang": lang,


                  "ship_id": sid, "use_pr": True}


        res = await fetch_and_render(


            self._kp, script="wws_ship", path="/b/ship-data/", params=params,


            render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


            want_image=self._llm_auto_image,


        )


        if res["img"]:


            await self._send_image(event, res["img"])


        if res["status"] != "ok" or res["message"] != "SUCCESS":


            return f"{tg['target_desc']}的「{found}」查询未成功：{humanize_api_error(res)}"


        return await self._deliver_data_or_return(


                event, f"[船只: {found}{note}]\n{extract_ship(res['data'])}",


                img_sent=bool(res.get("img")))





    # ------------------------------------------------------------------


    # @llm_tool 声明（schema 由 docstring 的 Args: 段生成，无 enum 支持，


    # 取值范围必须写进描述里，运行时再做别名归一）


    # ------------------------------------------------------------------





    @llm_tool(name="kokomi_account")


    async def kokomi_account(self, event: AstrMessageEvent, server: str = None,


                             nickname: str = None, qq_id: str = None) -> str:


        """查询玩家的实时总体战绩（水表）：总场次、胜率、场均伤害、PR 评级与分模式统计。





        回答任何战绩问题都应当调用本工具获取实时数据 —— 群聊历史消息里出现过的


        战绩数据可能已经过期，不要拿历史数据当现状来点评。


        当用户问「我的水表」「查XX的总战绩」「XX打得怎么样」（没有提到时间范围）时调用。





        Args:


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己；群内查别人也可以直接@对方。


            qq_id(string): 当用户明确说是 QQ 号时填写（如「查qq 2773646198 的 i2」填 2773646198，等效于 wws <@!2773646198>）。此时忽略 server/nickname，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            return await self._query_account(event, server=server, nickname=nickname, qq_id=qq_id)





    @llm_tool(name="kokomi_recent")


    async def kokomi_recent(self, event: AstrMessageEvent, days: int = None,


                            battle_mode: str = None, server: str = None,


                            nickname: str = None, qq_id: str = None) -> str:


        """查询玩家最近一段时间（按天）的实时战绩汇总，含逐船明细。





        回答任何「最近战绩」问题都必须调用本工具获取实时数据 —— 群聊历史消息里


        出现过的战绩数据可能已经过期，不要拿历史数据当现状来点评。


        当用户提到时间范围时调用，例如「最近7天怎么样」「这周水表」「上旬表现」。


        如果用户说的是「最近N场」（按场次计数），应改用 kokomi_recent_battles。





        Args:


            days(number): 统计最近多少天，默认 7。能查多久取决于上游服务器的数据留存，超出范围时会返回无数据。


            battle_mode(string): 只关注某个模式时填写，可选：随机（全部随机战）、排位、单野（1人）、自行车（2人组队）、三轮车（3人组队）。不填默认统计全部随机战。


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 当用户明确说是 QQ 号时填写（如「查qq 2773646198 的 i2」填 2773646198，等效于 wws <@!2773646198>）。此时忽略 server/nickname，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            return await self._query_recent(event, days=days, battle_mode=battle_mode,


                                            server=server, nickname=nickname, qq_id=qq_id)





    @llm_tool(name="kokomi_recent_battles")


    async def kokomi_recent_battles(self, event: AstrMessageEvent, server: str = None,


                                    nickname: str = None, qq_id: str = None) -> str:


        """查询玩家最近 24 小时内的逐场战斗记录（每一场用什么船、胜负、伤害）。





        必须调用本工具才能拿到逐场数据，历史消息里不会有。


        当用户按场次提问时调用，例如「最近10场打得如何」「昨天几场战绩」。


        注意：此查询只覆盖最近 24 小时，更早的请改用 kokomi_recent。


        结果以图片形式直接发给用户。





        Args:


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 当用户明确说是 QQ 号时填写（如「查qq 2773646198 的 i2」填 2773646198，等效于 wws <@!2773646198>）。此时忽略 server/nickname，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"


            lang = tg.get("lang") or "cn"


            mod = self._kp.module("wws_recents")


            res = await mod.get_data(parameter=[


                tg["aid"], tg["server"], lang, True, False, [], 1


            ])


            img = res.get("img") if isinstance(res, dict) else None


            if img and self._llm_auto_image:


                await self._send_image(event, img)


            if not isinstance(res, dict) or res.get("status") != "ok" or res.get("message") != "SUCCESS":


                return f"{tg['target_desc']}最近24小时的逐场查询未成功：{humanize_api_error(res)}"


            return (f"已把{tg['target_desc']}最近24小时的逐场战斗图发送给用户（仅覆盖24小时内，"


                    f"该图包含每场的船只/胜负/伤害）。请基于图片内容或让用户自行查看，做简短点评。")





    @llm_tool(name="kokomi_ship")


    async def kokomi_ship(self, event: AstrMessageEvent, ship_name: str,


                          server: str = None, nickname: str = None, qq_id: str = None) -> str:


        """查询玩家某艘指定船只的实时战绩（场次、胜率、场均伤害、PR、详细数据）。





        回答单船战绩问题必须调用本工具获取实时数据 —— 群聊历史消息里出现过的


        战绩数据可能已经过期，也不允许改用 execute_shell/python 自己跑脚本查。


        当用户点名某艘船时调用，例如「XX的大和怎么样」「我 affection 驱逐舰玩得如何」。


        如果用户问的是「潜艇/巡洋/驱逐这类整体表现」，应改用 kokomi_ships。





        ⚠️ 「QQ号 + 船名」组合（如「看一下qq2773646198的i2」）必须同时传


        `qq_id=2773646198` **和** `ship_name=i2` —— 两者缺一不可。只传 qq_id 会退化成


        查总表，用户问的那艘船就被丢了。船名支持中文名/英文名/简称/代号（i2、I-2 均可）。





        Args:


            ship_name(string): 船只名称，**必填**，支持中文（大和）或英文名（Yamato）、简称代号（i2）。


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 当用户明确说是 QQ 号时填写（如「查qq 2773646198 的 i2」填 2773646198，等效于 wws <@!2773646198>）。此时忽略 server/nickname，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            return await self._query_ship(event, ship_name, server=server, nickname=nickname, qq_id=qq_id)





    @llm_tool(name="kokomi_ships")


    async def kokomi_ships(self, event: AstrMessageEvent, ship_type: str,


                           ship_tier: int = None, server: str = None,


                           nickname: str = None, qq_id: str = None) -> str:


        """按舰种（可叠加等级）筛选查询玩家的一批船只战绩。





        回答「潜艇/巡洋/驱逐/战列/航母打得怎么样」这类**按舰种**的战绩问题


        必须调用本工具 —— 群聊历史消息里出现过的战绩数据可能已经过期，


        也不允许改用 execute_shell/python 自己跑脚本查（那会绕过限流与话术层）。





        Args:


            ship_type(string): 舰种，可选：潜艇、巡洋舰、战列舰、驱逐舰、航母、战巡。


            ship_tier(number): 只要某个等级时填写（如 10）。不填则返回该舰种全部。


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 当用户明确说是 QQ 号时填写（如「查qq 2773646198 的 i2」填 2773646198，等效于 wws <@!2773646198>）。此时忽略 server/nickname，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"





            lang = tg.get("lang") or "cn"


            stype = normalize_ship_type(ship_type)


            if not stype:


                return f"舰种「{ship_type}」无法识别，可选：潜艇/巡洋舰/战列舰/驱逐舰/航母/战巡。"





            params = {"aid": tg["aid"], "server": tg["server"], "lang": lang,


                      "non_zero": True, "non_old": False, "ship_type": stype,


                      "use_pr": True}


            tier_desc = "全部等级"


            if ship_tier is not None:


                try:


                    params["ship_tier"] = int(ship_tier)


                    tier_desc = f"{int(ship_tier)}级"


                except (TypeError, ValueError):


                    pass





            res = await fetch_and_render(


                self._kp, script="wws_ships", path="/b/ships-data/", params=params,


                render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


                want_image=self._llm_auto_image,


            )


            if res["img"]:


                await self._send_image(event, res["img"])


            if res["status"] != "ok" or res["message"] != "SUCCESS":


                return f"{tg['target_desc']}的{stype}筛选查询未成功：{humanize_api_error(res)}"


            return await self._deliver_data_or_return(


                event, f"[舰种: {stype}, {tier_desc}]\n{extract_ships(res['data'], nickname=res.get('nickname'))}",


                img_sent=bool(res.get("img")))





    @staticmethod
    def _agent_has_followup(event: AstrMessageEvent) -> bool:
        """当前会话的活动 agent run 是否攒着未消费的 follow-up 消息。

        AstrBot follow-up 机制（astrbot/core/pipeline/process_stage/follow_up.py）：
        agent run 进行中，同一会话同一发送者再发消息会被捕获为 ticket 挂到
        runner._pending_follow_ups，等工具结果返回时注入下一轮 LLM 上下文。
        若工具体在此期间 stop_event 中止 agent，下一轮 LLM 永远不会发生，
        用户那些消息就被静默吞掉（2026-10-04 11:28 实测：「你是谁」无回应）。
        pending 非空 ⟺ 有未消费 follow-up（消费时列表会被整体清空）。
        """
        try:
            from astrbot.core.pipeline.process_stage.follow_up import (
                _ACTIVE_AGENT_RUNNERS,
            )
            runner = _ACTIVE_AGENT_RUNNERS.get(event.unified_msg_origin)
            if runner is None:
                return False
            return bool(getattr(runner, "_pending_follow_ups", None))
        except Exception:  # noqa: BLE001
            return False

    # ==================== DSML 泄露兜底（on_decorating_result，2026-10-04） ====================
    # 背景：自定义中转端点偶发把 DeepSeek 内部 DSML tool-call 标记当正文吐出
    # （HTTP 200 但 tool_calls 缺失），AstrBot 解析不到就原样发给用户。
    # 本钩子在消息发送前（respond 装饰阶段）做最后拦截：剥除污染文本；
    # 若能解析出 kokomi_* 工具调用，则手动执行补救，让用户拿到真实结果而不是乱码。

    _DSML_TAG = "<｜DSML｜"
    _DSML_INVOKE_RE = re.compile(
        r'<｜DSML｜invoke\s+name="([^"]+)">(.*?)</｜DSML｜invoke>', re.S
    )
    _DSML_PARAM_RE = re.compile(
        r'<｜DSML｜parameter\s+name="([^"]+)"[^>]*>(.*?)</｜DSML｜parameter>', re.S
    )

    @classmethod
    def _parse_dsml_calls(cls, text: str) -> list:
        """从泄露的 DSML 文本中解析 [(tool_name, {param: value}), ...]。"""
        import json as _json
        calls = []
        for m in cls._DSML_INVOKE_RE.finditer(text or ""):
            args = {}
            for pm in cls._DSML_PARAM_RE.finditer(m.group(2)):
                raw = pm.group(2).strip()
                try:
                    val = _json.loads(raw)
                except Exception:  # noqa: BLE001
                    val = raw.strip('"')
                args[pm.group(1)] = val
            calls.append((m.group(1), args))
        return calls

    @filter.on_decorating_result()
    async def dsml_leak_guard(self, event: AstrMessageEvent) -> None:
        """发送前最后防线：拦截 LLM 结果链里的 DSML 泄露文本并尽力补救。"""
        try:
            result = event.get_result()
            if result is None or not result.chain:
                return
            if not result.is_llm_result():
                return
            if not any(
                isinstance(c, Plain) and self._DSML_TAG in (c.text or "")
                for c in result.chain
            ):
                return
            plain = "\n".join(
                c.text for c in result.chain
                if isinstance(c, Plain) and c.text
            )
            logger.warning(
                f"[dsml-guard] 拦截 DSML 泄露 (len={len(plain)}) "
                f"umo={event.unified_msg_origin}"
            )
            calls = self._parse_dsml_calls(plain)
            executed = 0
            for name, kwargs in calls[:3]:
                if not name.startswith("kokomi_"):
                    continue
                method = getattr(self, name, None)
                if not callable(method):
                    continue
                try:
                    ret = method(event, **kwargs)
                    if asyncio.iscoroutine(ret):
                        await ret
                    executed += 1
                    logger.warning(
                        f"[dsml-guard] 手动补救执行 {name}({list(kwargs.keys())})"
                    )
                except Exception:  # noqa: BLE001
                    logger.error(
                        f"[dsml-guard] 手动执行 {name} 失败（参数={kwargs}），已放弃补救"
                    )
            # 重写 chain：截掉 DSML 及其后的内容，保留干净正文与其他组件
            new_chain = []
            for c in result.chain:
                if isinstance(c, Plain) and self._DSML_TAG in (c.text or ""):
                    head = (c.text or "").split(self._DSML_TAG, 1)[0].rstrip()
                    if head:
                        new_chain.append(Plain(head))
                else:
                    new_chain.append(c)
            if not new_chain and executed == 0:
                new_chain.append(Plain("（刚才的查询输出出错了，请重新发送指令）"))
            result.chain.clear()
            result.chain.extend(new_chain)
        except Exception:  # noqa: BLE001
            import traceback as _tb
            logger.error(
                f"[dsml-guard] 钩子异常（不影响原消息发送）:\n{_tb.format_exc()}"
            )

    async def _deliver_data_or_return(self, event: AstrMessageEvent, text: str,


                                      *, img_sent: bool = False) -> str:


        """按「是否点评」开关决定数据去向。





        开（默认）：数据文本返回给模型，AI 顺带点评；


        关（纯图模式）：渲染图已经包含全部数据 ——


          - 图已发送：什么都不再发，模型只收到一句确认（手上没数据，想点评也没料）；


          - 图没发（auto_image 关了）：把数据文本直接发给用户兜底，


            否则用户什么都收不到。


        """


        if self._llm_evaluate:


            return text + "\n\n（请基于以上数据顺带点评玩家表现。）"


        # ★ follow-up 防吞（2026-10-04）：用户在工具执行期间又发的消息已被 AstrBot
        #   捕获为 follow-up、即将注入 agent 的下一轮上下文；若这里 stop_event，
        #   下一轮 LLM 不会发生，那些消息就被静默吞掉。此时改为放行模型收尾，
        #   让它确认数据已发送并回应新消息；其余场景维持「命中 → 静默」。
        if self._agent_has_followup(event):
            return ("渲染图已直接发送给用户（图内含完整数据），请先用一句话向用户确认"
                    "数据已发送，然后优先回应用户在工具执行期间发来的新消息，"
                    "不要复述图内数据。")
        if not img_sent:
            # ★ 失败反馈（2026-10-16）：图没发出来（无战绩/查询失败等），
            #   text 就是要给用户的内容 —— 直发，别静默。
            try:
                await event.send(MessageChain().message(text))
            except Exception:  # noqa: BLE001
                pass
            return text
        # ★ 多工具保护（2026-10-13）：模型可能一轮连发多个查询（如「bb cv 9巡 10巡」
        #   → 4 个 kokomi_ships 串行执行）；第一个工具完成就 stop_event 会触发
        #   runner 的 abort 信号，杀掉其余未执行的工具调用（实测四连查询只出 1 张
        #   图）。runner 未向插件暴露「剩余工具数」，无法精确判断 → 一律放行模型
        #   收尾，靠指引文本压住复读。代价：每次查询多一轮收尾 LLM（可接受）。
        #   下面的 stop_event 分支成为死代码，保留备用。
        return ("渲染图已直接发送给用户（图内含完整数据）。请只回一句简短确认"
                "（如「已查收」），不要复述图内数据。")
        # 命中分支（内容已直发用户）→ 终止事件：不生成模型的后续确认回复。


        # 语义（用户定）：命中 → 静默；未命中 → 才由模型解释。


        # 已知副作用：本次对话不保存历史（战绩查询场景可接受）。


        try:


            event.stop_event()


        except Exception:  # noqa: BLE001


            pass


        if img_sent:


            return ("渲染图已直接发送给用户（图内含完整数据）。请简单确认即可，"


                    "不要复述或编造数据。")


        try:


            await event.send(MessageChain().message(text))


        except Exception as e:  # noqa: BLE001


            logger.warning(f"[kokomi-llm] 直接发送数据失败，退回模型路径: {e}")


            return text


        return "查询结果已直接发送给用户（仅数据，未附点评）。请简单确认即可，不要编造数据。"





    @llm_tool(name="kokomi_recent_random")


    async def kokomi_recent_random(self, event: AstrMessageEvent, days: int = None,


                                   server: str = None, nickname: str = None, qq_id: str = None) -> str:


        """查询玩家最近一段时间的随机战战绩（仅统计随机战 PVP，不含排位）。





        当用户明确说「最近随机战」「随机打得怎么样」时调用。


        如果用户只是泛泛地说「最近战绩」，应优先用 kokomi_recent。





        Args:


            days(number): 统计最近多少天，默认 7。能查多久取决于上游服务器的数据留存。


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 当用户明确说是 QQ 号时填写（如「查qq 2773646198 的 i2」填 2773646198，等效于 wws <@!2773646198>）。此时忽略 server/nickname，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            return await self._query_recent(event, days=days, battle_mode="随机",


                                            server=server, nickname=nickname, qq_id=qq_id)





    @llm_tool(name="kokomi_recent_rank")


    async def kokomi_recent_rank(self, event: AstrMessageEvent, days: int = None,


                                 server: str = None, nickname: str = None, qq_id: str = None) -> str:


        """查询玩家最近一段时间的排位战战绩。





        当用户明确说「最近排位」「排位打得怎么样」时调用。


        泛泛地问「最近战绩」应优先用 kokomi_recent。





        Args:


            days(number): 统计最近多少天，默认 7。能查多久取决于上游服务器的数据留存。


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 当用户明确说是 QQ 号时填写（如「查qq 2773646198 的 i2」填 2773646198，等效于 wws <@!2773646198>）。此时忽略 server/nickname，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            return await self._query_recent(event, days=days, battle_mode="排位",


                                            server=server, nickname=nickname, qq_id=qq_id)





    @llm_tool(name="kokomi_ship_recent")


    async def kokomi_ship_recent(self, event: AstrMessageEvent, ship_name: str,


                                 days: int = None, server: str = None,


                                 nickname: str = None, qq_id: str = None) -> str:


        """查询玩家某艘船最近一段时间（按天）的战绩表现。





        当用户问「XX的大和最近一周打得如何」这类**单船 + 时间范围**的问题时调用。


        只问单船总战绩用 kokomi_ship；按舰种筛选用 kokomi_ships。





        Args:


            ship_name(string): 船只名称，支持中文（大和）或英文名（Yamato）。


            days(number): 统计最近多少天，默认 7。能查多久取决于上游服务器的数据留存。


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 当用户明确说是 QQ 号时填写（如「查qq 2773646198 的 i2」填 2773646198，等效于 wws <@!2773646198>）。此时忽略 server/nickname，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"





            lang = tg.get("lang") or "cn"


            sid, found = await self._resolve_ship_id(ship_name, lang, server=tg.get("server"))


            if not sid:


                return f"没有找到名为「{ship_name}」的船只，请确认名称。"





            n = clamp_days(days)


            tz = self._kp._load("common.time_zone")


            start_date, end_date = tz.get_str_server_time(server=tg["server"], date_num=n)





            params = {"aid": tg["aid"], "server": tg["server"], "lang": lang,


                      "ship_id": sid, "start_date": start_date, "end_date": end_date,


                      "use_pr": True}  # use_ac=False 时原脚本自行删键


            params.pop("use_ac", None); params.pop("ac", None)





            res = await fetch_and_render(


                self._kp, script="wws_ship_recent", path="/r1/ship-recent-data/",


                params=params,


                render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


                want_image=self._llm_auto_image,


            )


            if res["img"]:


                await self._send_image(event, res["img"])


            if res["status"] != "ok" or res["message"] != "SUCCESS":


                return f"{tg['target_desc']}的「{ship_name}」近期查询未成功：{humanize_api_error(res)}"


            return await self._deliver_data_or_return(


                event,


                f"[船只: {ship_name}, 统计范围: 最近{n}天]\n"


                + extract_recent(res["data"], nickname=res.get("nickname")),


                img_sent=bool(res.get("img")),


            )





    @llm_tool(name="kokomi_bind")


    async def kokomi_bind(self, event: AstrMessageEvent, server: str,


                          nickname: str) -> str:


        """把当前用户绑定为指定的游戏账号（之后查询默认查这个账号）。





        仅当用户**明确要求绑定**时调用，例如「帮我绑定俄服 XXX」「我要绑定亚服 YY」。


        绑定成功后渲染确认图发给用户。





        Args:


            server(string): 游戏账号所在服务器：亚服/国服/欧服/美服/俄服。


            nickname(string): 要绑定的游戏昵称。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        srv = normalize_server(server, self._kp)


        if not srv or not nickname:


            return "绑定需要服务器和游戏昵称。例：绑定 俄服 XXX"


        async with self._lock:


            res = await self._dispatch_tokens(


                event, ["wws", "bind", srv, str(nickname).strip()]


            )


            kind = res.get("type")


            if kind == "img" and isinstance(res.get("img"), str):


                if os.path.isfile(res["img"]):


                    await self._send_image(event, res["img"])


                return "绑定成功，确认图已发给用户。之后查询默认使用这个账号。"


            msg = str(res.get("msg") or res.get("message") or "")


            return f"绑定未成功：{msg or '原因未知'}。若提示找不到玩家，请确认服务器和昵称拼写。"





    async def _resolve_clan_id(self, event, server, clan_tag, clan_id):


        """clan 系列的 clan_id 解析：显式 ID > 标签搜索 > 自己水表里的公会。"""


        srv = normalize_server(server, self._kp)


        if clan_id and str(clan_id).strip().isdigit():


            if not srv:


                tg = await resolve_target(self._kp, event, prefix=self.command)


                if tg["status"] != "ok":


                    return None, None, "给了公会 ID 时也需要说明服务器"


                srv = tg["server"]


            return str(clan_id).strip(), srv, None


        if clan_tag:


            if not srv:


                return None, None, "按标签搜索公会需要指定服务器（亚服/国服/欧服/美服/俄服）"


            sc = self._kp._load("common.search_clan")


        if clan_tag:


            srv = normalize_server(server, self._kp)


            if not srv:


                return None, "按标签搜索公会需要指定服务器（亚服/国服/欧服/美服/俄服）"


            r = await sc.search_clan(server=srv, clan_tag=str(clan_tag).strip())


            if r.get("status") != "ok" or r.get("message") != "SUCCESS":


                return None, f"公会搜索失败：{r.get('message')}"


            cid = _find_clan_id(r.get("data"))


            if cid:


                return str(cid), srv, None


            return None, None, f"没有找到标签为「{clan_tag}」的公会"


        tg = await resolve_target(self._kp, event, prefix=self.command)


        if tg["status"] != "ok":


            return None, None, tg.get("detail") or "无法确定查询目标。"


        call_api = self._kp._load("common.call_api").call_api


        p = {"aid": tg["aid"], "server": tg["server"],


             "lang": tg.get("lang") or "cn", "use_pr": True}


        r = await call_api(params=p, path="/b/pvp-data/")


        if r.get("status") != "ok" or r.get("message") != "SUCCESS":


            return None, None, "查询你的账号信息失败，无法定位所属公会"


        clans = (r.get("data") or {}).get("clans") or {}


        cid = clans.get("clan_id")


        if not cid:


            return None, None, "该账号还没有加入公会"


        return str(cid), tg["server"], None





    async def _resolve_ship_id(self, ship_name: str, lang: str = "cn",


                               server: str | None = None):


        """船名 -> (ship_id, 显示名)。本地索引优先（中文名覆盖全），未命中回退上游。





        为什么本地优先：Kokomi 上游 /p/search-name/ 的中文名不全（俄服/新船搜不到），


        本地索引来自 shinoaki 百科（shipId 与 Kokomi 同体系），命中即可直接查。


        server：目标玩家的服务器 —— WG 与 LESTA 是两套船表，按服分区取 shipId。


        """


        try:


            from .kokomi_llm.ships import find_ships, ship_display_name


            hits = find_ships(str(ship_name).strip(), prefer_server=server)


            if hits:


                h = hits[0]


                return h.get("shipId") or h.get("ship_id"), ship_display_name(h)


        except Exception as e:  # noqa: BLE001


            logger.warning(f"[kokomi-llm] 本地船名索引异常，回退上游: {e}")


        # 兜底：上游搜索


        ssn = self._kp._load("common.search_ship_name")


        sr = await ssn.search_ship_name(lang=lang, shipname=str(ship_name).strip())


        ships = ((sr.get("data") or {}).get("ships") or []) if sr.get("status") == "ok" else []


        if ships:


            return ships[0].get("ship_id"), ship_name


        return None, None





    async def _run_query_tool(self, event, *, script, path, params, render_args,


                              label, nickname=None) -> str:


        """通用查询工具执行器：取数渲染 + 通用数据汇报（无专用提取器的接口）。"""


        res = await fetch_and_render(self._kp, script=script, path=path, params=params,


                                     render_args=render_args,


                                     want_image=self._llm_auto_image)


        if res["img"]:


            await self._send_image(event, res["img"])


        if res["status"] != "ok" or res["message"] != "SUCCESS":


            return humanize_api_error(res)


        data_text = (f"{label}\n"


                     + generic_dump(res.get("data"), nickname=res.get("nickname")))


        return await self._deliver_data_or_return(event, data_text,


                                                  img_sent=bool(res.get("img")))








    @llm_tool(name="kokomi_info")


    async def kokomi_info(self, event: AstrMessageEvent, server: str = None, qq_id: str = None,


                          nickname: str = None) -> str:


        """查询账号总水表（详细版/玩家总表）：PR 总览、各模式、船型/等级分布、纪录等完整面板。





        调用条件（必须同时满足）：


          - 用户要的是**整个账号**的汇总（「wws me info」「详细总表」「玩家总表」）；


          - 请求中**没有点名任何一艘具体船只**。





        ⚠️ 只要消息里出现了船名（中文名/英文名/简称/代号，如「大和」「Yamato」「i2」「I-2」），


        就必须改用 `kokomi_ship`（单船）或 `kokomi_ship_batch`（多船），**绝不能用本工具代替**——


        本工具没有任何船只参数，传进来的船名会被直接丢弃，用户会拿到一张与问题无关的总表。


        「我的水表」这类简略汇总查询用 kokomi_account。





        Args:


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 用户明确说是 QQ 号时填写（如「查qq 2773646198」填 2773646198），直接查该 QQ 绑定的账号。注意：只填 QQ 号、船名交给 kokomi_ship。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"


            lang = tg.get("lang") or "cn"


            params = {"aid": tg["aid"], "server": tg["server"], "lang": lang, "use_pr": True}


            return await self._run_query_tool(


                event, script="wws_info", path="/b/info-data/", params=params,


                render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


                label=f"[{tg['target_desc']} 玩家总表(详细)]")





    @llm_tool(name="kokomi_card")


    async def kokomi_card(self, event: AstrMessageEvent, server: str = None, qq_id: str = None,


                          nickname: str = None) -> str:


        """查询当前绑定及账户数据卡片（wws me bind）。





        当用户问「我的绑定信息」「绑定状态」「账户数据卡片」时调用。





        Args:


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 用户明确说是 QQ 号时填写，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"


            lang = tg.get("lang") or "cn"


            params = {"aid": tg["aid"], "server": tg["server"], "lang": lang, "use_pr": True}


            return await self._run_query_tool(


                event, script="wws_card", path="/b/card-data/", params=params,


                render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


                label=f"[{tg['target_desc']} 绑定及账户数据]")





    @llm_tool(name="kokomi_oper")


    async def kokomi_oper(self, event: AstrMessageEvent, server: str = None, qq_id: str = None,


                          nickname: str = None) -> str:


        """查询账号的剧情模式数据（wws me oper）。





        当用户问「剧情数据」「战役打得怎么样」时调用。





        Args:


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 用户明确说是 QQ 号时填写，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"


            lang = tg.get("lang") or "cn"


            params = {"aid": tg["aid"], "server": tg["server"], "lang": lang}


            return await self._run_query_tool(


                event, script="wws_oper", path="/b/oper-data/", params=params,


                render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


                label=f"[{tg['target_desc']} 剧情数据]")





    @llm_tool(name="kokomi_cw")


    async def kokomi_cw(self, event: AstrMessageEvent, server: str = None, qq_id: str = None,


                        nickname: str = None) -> str:


        """查询账号参加过的公会战（ clan war）数据（wws me cw）。





        当用户问「公会战」「cw 打得怎么样」时调用。





        Args:


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 用户明确说是 QQ 号时填写，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"


            lang = tg.get("lang") or "cn"


            params = {"aid": tg["aid"], "server": tg["server"], "lang": lang}


            return await self._run_query_tool(


                event, script="wws_cw", path="/b/cw-data/", params=params,


                render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


                label=f"[{tg['target_desc']} 公会战数据]")





    @llm_tool(name="kokomi_rank")


    async def kokomi_rank(self, event: AstrMessageEvent, server: str = None, qq_id: str = None,


                          nickname: str = None) -> str:


        """查询账号的排位赛数据总览（wws me rank）。





        当用户问「排位数据」「排位赛总览」时调用；指定赛季用 kokomi_rank_season；


        近期排位战绩用 kokomi_recent_rank。





        Args:


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 用户明确说是 QQ 号时填写，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"


            lang = tg.get("lang") or "cn"


            params = {"aid": tg["aid"], "server": tg["server"], "lang": lang, "use_pr": True}


            return await self._run_query_tool(


                event, script="wws_rank", path="/b/rank-data/", params=params,


                render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


                label=f"[{tg['target_desc']} 排位赛数据]")





    @llm_tool(name="kokomi_rank_season")


    async def kokomi_rank_season(self, event: AstrMessageEvent, season: str,


                                 server: str = None, qq_id: str = None,


                                 nickname: str = None) -> str:


        """查询账号指定排位赛季的数据（wws me rank s14）。





        当用户问「s14 排位」「某个赛季的排位数据」时调用。





        Args:


            season(string): 赛季编号，如 s14、s24。


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


            qq_id(string): 用户明确说是 QQ 号时填写，直接查该 QQ 绑定的账号。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"


            lang = tg.get("lang") or "cn"


            try:


                sn = int(re.sub(r"[^0-9]", "", str(season)) or 0)


            except (TypeError, ValueError):


                sn = 0


            if sn <= 0:


                return "赛季格式应为 s14 / 14 这样的编号。"


            params = {"aid": tg["aid"], "server": tg["server"], "lang": lang,


                      "rank_season": sn, "use_pr": True}


            return await self._run_query_tool(


                event, script="wws_rank_season", path="/b/rank-season-data/", params=params,


                render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang, "pic_num": 1},


                label=f"[{tg['target_desc']} 排位赛季 s{sn}]")








    @llm_tool(name="kokomi_clan_info")


    async def kokomi_clan_info(self, event: AstrMessageEvent, server: str = None,


                               clan_tag: str = None, clan_id: str = None) -> str:


        """查询公会信息（wws me clan / wws 俄服 clan NEKOM）。





        不填公会标签和 ID 时查**自己所属公会**；


        给公会标签（如 NEKOM）时按服务器搜索。





        Args:


            server(string): 公会所在服务器，可选：亚服/国服/欧服/美服/俄服。查自己的公会可不填。


            clan_tag(string): 公会标签（如 NEKOM），按标签搜索时填写。


            clan_id(string): 直接给公会 ID 时填写。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            cid, srv, err = await self._resolve_clan_id(event, server, clan_tag, clan_id)


            if err:


                return err


            return await self._run_query_tool(


                event, script="wws_clan_info", path="/b/clan-basic-data/",


                params={"clan_id": cid, "server": srv, "lang": "cn"},


                render_args={"clan_id": cid, "server": srv, "lang": "cn", "pic_num": 1},


                label=f"[公会 {cid} 信息]")





    @llm_tool(name="kokomi_clan_season")


    async def kokomi_clan_season(self, event: AstrMessageEvent, season: str,


                                 server: str = None, clan_tag: str = None,


                                 clan_id: str = None) -> str:


        """查询公会的指定公会战赛季数据（wws me clan s24）。





        Args:


            season(string): 公会战赛季编号，如 s24、22。


            server(string): 公会所在服务器。查自己的公会可不填。


            clan_tag(string): 公会标签，按标签搜索时填写。


            clan_id(string): 直接给公会 ID 时填写。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            cid, srv, err = await self._resolve_clan_id(event, server, clan_tag, clan_id)


            if err:


                return err


            try:


                sn = int(re.sub(r"[^0-9]", "", str(season)) or 0)


            except (TypeError, ValueError):


                sn = 0


            if sn <= 0:


                return "赛季格式应为 s24 / 24 这样的编号。"


            return await self._run_query_tool(


                event, script="wws_clan_season", path="/b/clan-season-data/",


                params={"clan_id": cid, "server": srv, "lang": "cn", "cvc_season": sn},


                render_args={"clan_id": cid, "server": srv, "lang": "cn", "pic_num": 1},


                label=f"[公会 {cid} 赛季 s{sn}]")





    @llm_tool(name="kokomi_clan_history")


    async def kokomi_clan_history(self, event: AstrMessageEvent, server: str = None,


                                  clan_tag: str = None, clan_id: str = None) -> str:


        """查询公会参加过的所有公会战赛季历史（wws me clan history）。





        Args:


            server(string): 公会所在服务器。查自己的公会可不填。


            clan_tag(string): 公会标签，按标签搜索时填写。


            clan_id(string): 直接给公会 ID 时填写。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            cid, srv, err = await self._resolve_clan_id(event, server, clan_tag, clan_id)


            if err:


                return err


            return await self._run_query_tool(


                event, script="wws_clan_history", path="/b/clan-history-data/",


                params={"clan_id": cid, "server": srv, "lang": "cn"},


                render_args={"clan_id": cid, "server": srv, "lang": "cn", "pic_num": 1},


                label=f"[公会 {cid} 赛季历史]")





    @llm_tool(name="kokomi_online")


    async def kokomi_online(self, event: AstrMessageEvent) -> str:


        """查询当前各服务器在线人数（wws online）。





        当用户问「现在多少人在线」「服务器在线人数」时调用。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            return await self._run_query_tool(


                event, script="wws_online", path="/p/online-player/",


                params={"lang": "cn"},


                render_args={"lang": "cn", "pic_num": 1},


                label="[服务器在线人数]")





    @llm_tool(name="kokomi_search_ship")


    async def kokomi_search_ship(self, event: AstrMessageEvent, ship_type: str = None,


                                 ship_tier: int = None, ship_nation: str = None) -> str:


        """按舰种/等级/国家查询游戏内船只列表（wws search 10 bb）。





        当用户问「有哪些 10 级战列」「查一下苏联驱逐」时调用。





        Args:


            ship_type(string): 舰种，可选：航母/战列/巡洋/驱逐/潜艇。


            ship_tier(number): 等级 1-11。


            ship_nation(string): 国家，如 美国/日本/俄国/英国/意大利 等。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            params = {"lang": "cn",


                      "ship_type": normalize_ship_type(ship_type) or "",


                      "ship_tier": int(ship_tier) if ship_tier else "",


                      "ship_nation": str(ship_nation or "")}


            return await self._run_query_tool(


                event, script="wws_name", path="/p/ships-info/", params=params,


                render_args={"lang": "cn", "pic_num": 1},


                label="[船只列表]")





    @llm_tool(name="kokomi_server_ships")


    async def kokomi_server_ships(self, event: AstrMessageEvent, server: str,


                                  ship_type: str = None, ship_tier: int = None,


                                  ship_nation: str = None) -> str:


        """查询指定服务器指定范围内船只的服务器总体数据（wws 亚洲 stats x cv）。





        Args:


            server(string): 服务器：亚服/国服/欧服/美服/俄服。


            ship_type(string): 舰种，可选：航母/战列/巡洋/驱逐/潜艇。


            ship_tier(number): 等级 1-11。


            ship_nation(string): 国家，如 美国/日本/俄国/英国 等。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        srv = normalize_server(server, self._kp)


        if not srv:


            return "需要指定服务器（亚服/国服/欧服/美服/俄服）。"


        async with self._lock:


            params = {"server": srv, "lang": "cn",


                      "ship_type": normalize_ship_type(ship_type) or "",


                      "ship_tier": int(ship_tier) if ship_tier else "",


                      "ship_nation": str(ship_nation or "")}


            return await self._run_query_tool(


                event, script="wws_data", path="/p/ships-data/", params=params,


                render_args={"server": srv, "lang": "cn", "pic_num": 1},


                label=f"[{srv} 服船只数据]")





    @llm_tool(name="kokomi_ship_server_rank")


    async def kokomi_ship_server_rank(self, event: AstrMessageEvent, ship_name: str,


                                      server: str = None) -> str:


        """查询某艘船在 wows numbers 上的全服排行榜（前 50 名）（wws 亚洲 ship rank 大和）。





        当用户问「大和在全服排第几」「这船的服务器排行」时调用。


        查自己某艘船的排名用 kokomi_ship。





        Args:


            ship_name(string): 船只名称，支持中文或英文。


            server(string): 服务器：亚服/国服/欧服/美服/俄服。默认俄服。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            lang = "cn"


            sid, found = await self._resolve_ship_id(ship_name, lang, server=tg.get("server"))


            if not sid:


                return f"没有找到名为「{ship_name}」的船只，请确认名称。"


            srv = normalize_server(server, self._kp) or "ru"


            return await self._run_query_tool(


                event, script="wws_number_rank", path="/b/number-ship-rank/",


                params={"server": srv, "lang": lang, "ship_id": sid},


                render_args={"server": srv, "lang": lang, "pic_num": 1},


                label=f"[{srv} 服 {ship_name} 全服排行]")





    @llm_tool(name="kokomi_ship_server_stats")


    async def kokomi_ship_server_stats(self, event: AstrMessageEvent, ship_name: str) -> str:


        """查询某艘船的全服务器总体数据与近期数据（wws stats ship 大和）。





        当用户问「大和这船在服务器上表现怎么样」「这船服务器平均数据」时调用。





        Args:


            ship_name(string): 船只名称，支持中文或英文。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        async with self._lock:


            lang = "cn"


            sid, found = await self._resolve_ship_id(ship_name, lang, server=tg.get("server"))


            if not sid:


                return f"没有找到名为「{ship_name}」的船只，请确认名称。"


            return await self._run_query_tool(


                event, script="wws_stats", path="/p/ship-data/",


                params={"lang": lang, "ship_id": sid},


                render_args={"lang": lang, "pic_num": 1},


                label=f"[{ship_name} 服务器数据]")








    @llm_tool(name="kokomi_ship_batch")


    async def kokomi_ship_batch(self, event: AstrMessageEvent, ship_names: str,


                                server: str = None, qq_id: str = None,


                                nickname: str = None) -> str:


        """一次查询**多艘船**的个人战绩（用户在同一条消息里问了多艘船时用这个）。





        用户说「查一下图拉真和莫斯科的战绩」「塞德利茨、北安普顿怎么样」这类


        多船查询时必须用本工具（而不是逐个调用 kokomi_ship）。并发查询，全部完成后


        依次发图并汇总结果。





        Args:


            ship_names(string): 船名列表，用逗号/顿号/空格分隔，如「图拉真,莫斯科,塞德利茨」。最多 8 艘。


            server(string): 被查玩家所在服务器，可选：亚服/国服/欧服/美服/俄服。不填则查当前用户自己。


            qq_id(string): 用户明确说是 QQ 号时填写，直接查该 QQ 绑定的账号。


            nickname(string): 玩家游戏昵称。不填则查当前用户自己。


        """


        if not self._ensure_llm_ready():


            return "战绩查询插件未就绪，请稍后再试。"


        names = [n for n in re.split(r"[,，、/;；\s]+", str(ship_names or "").strip()) if n][:8]


        if not names:


            return "请给出要查询的船名列表，如：图拉真,莫斯科"


        async with self._lock:


            tg = await resolve_target(self._kp, event, server=server, nickname=nickname, qq_id=qq_id, prefix=self.command)


            if tg["status"] != "ok":


                return tg.get("detail") or "无法确定查询目标。"


            return await self._batch_ship_query(event, names, tg)





    # ---- 多命中候选交互（用户定案）----
    # 唯一命中 → 直接发图；多命中 → 列本服候选图（1/2/3），回序号查船，
    # 20 秒无响应自动超时取消（2026-10-16 参考外部样式由 15s 调整）。
    # 候选只从用户所在服的船表出，不跨表混。
    _SHIP_PICK_TIMEOUT = 20

    async def _list_ship_candidates(self, event, query: str, tg: dict) -> str | None:
        """列出候选（多命中）并登记待选状态；返回给用户的提示文本。

        返回 None 表示不是「多候选」情形（0 命中或 1 命中），交给原流程。
        """
        from .kokomi_llm.ships import find_ship_candidates, ship_display_name
        try:
            cands = find_ship_candidates(query, prefer_server=tg.get("server"))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[kokomi] 候选列举异常: {e}")
            return None
        if len(cands) < 2:
            return None

        sid = self._session_key(event)
        task = self._pick_tasks.pop(sid, None)
        if task and not task.done():
            task.cancel()

        lines = [f"存在多条名字相似的船（共 {len(cands)} 艘）",
                 f"请在{self._SHIP_PICK_TIMEOUT}秒内回复对应的序号："]
        for i, item in enumerate(cands, 1):
            lv = item.get("level")
            st = item.get("shipType")
            tag = " ".join(x for x in (f"{lv}级" if lv else "", str(st or "")) if x)
            lines.append(f"{i}. {ship_display_name(item)}" + (f" [{tag}]" if tag else ""))
        lines.append(f"（{self._SHIP_PICK_TIMEOUT} 秒内不回复则取消）")
        text = "\n".join(lines)

        pending = {
            "items": [
                {"name": (it.get("nameCn") or it.get("nameEnglish") or query),
                 "ship_id": it.get("shipId") or it.get("ship_id"),
                 "display": ship_display_name(it)}
                for it in cands
            ],
            "tg": tg,
            "expire": time.monotonic() + self._SHIP_PICK_TIMEOUT,
        }
        self._pick_pending[sid] = pending

        async def _expire():
            await asyncio.sleep(self._SHIP_PICK_TIMEOUT)
            cur = self._pick_pending.get(sid)
            if cur is pending:
                self._pick_pending.pop(sid, None)
                try:
                    await event.send(MessageChain().message("选择超时，已取消。"))
                except Exception:  # noqa: BLE001
                    pass

        self._pick_tasks[sid] = asyncio.ensure_future(_expire())

        return text

    async def _handle_ship_pick(self, event) -> bool:
        """处理「回复序号选船」。命中并处理返回 True。"""
        txt = (event.message_str or "").strip()
        print(f"[diag-pick] 入口 txt={txt!r}", flush=True)
        # ★ 序号支持 1-20（2026-10-16）：候选上限提至 20 后，两位数序号必须能选
        m = re.fullmatch(r"[#＃]?\s*(20|1[0-9]|[1-9])\s*[.、:：]?", txt)
        if not m:
            return False
        sid = self._session_key(event)
        pending = self._pick_pending.get(sid)
        if not pending:
            print(f"[diag-pick] 无待选 pending sid={sid!r} keys={list(self._pick_pending)[:5]}", flush=True)
            return False
        if time.monotonic() > pending.get("expire", 0):
            self._pick_pending.pop(sid, None)
            await event.send(MessageChain().message("候选已超时，请重新查询。"))
            event.stop_event()
            return True

        idx = int(m.group(1)) - 1
        items = pending["items"]
        if idx < 0 or idx >= len(items):
            await event.send(MessageChain().message(
                f"序号超出范围，请输入 1-{len(items)}。"))
            event.stop_event()
            return True

        # 消费掉待选状态 + 撤销超时任务
        self._pick_pending.pop(sid, None)
        task = self._pick_tasks.pop(sid, None)
        if task and not task.done():
            task.cancel()

        chosen = items[idx]
        tg = dict(pending.get("tg") or {})
        event.stop_event()
        await self._batch_ship_query(event, [chosen["name"]], tg, forced_ship_id=chosen.get("ship_id"))
        return True

    @staticmethod
    def _server_tag(it: dict, query_server: str | None) -> str:
        """候选条目的服务器标签。"""
        st = str(it.get("serverType") or "").upper()
        srv = str(it.get("server") or "").lower()
        _map = {"ru": "俄服", "asia": "亚服", "eu": "欧服", "na": "美服", "cn": "国服"}
        if st == "LESTA" or srv == "ru":
            return "俄服"
        if srv in _map:
            return _map[srv]
        qs = str(query_server or "").lower()
        return _map.get(qs, "外服")

    def _pick_text_from_candidates(self, result: dict) -> str:
        """候选的文字版（渲染失败时兜底）。"""
        ships = result.get("ships") or []
        lang = result.get("lang") or "cn"
        server = result.get("server")
        lines = [f"存在多条名字相似的船（共 {len(ships)} 艘）",
                 f"请在{self._SHIP_PICK_TIMEOUT}秒内回复对应的序号："]
        for i, it in enumerate(ships, 1):
            sd = it.get("ship_data") or {}
            nm = ((sd.get("cn") if lang == "cn" else None)
                  or it.get("name") or sd.get("en")
                  or it.get("nameCn") or "?")
            try:
                lv = int(sd.get("tier") or it.get("level") or 0)
            except Exception:  # noqa: BLE001
                lv = 0
            tag = self._server_tag(it, server)
            lines.append(f"{i}. [{tag}] {nm}（{lv}级）")
        lines.append(f"（{self._SHIP_PICK_TIMEOUT} 秒内不回复则取消）")
        return "\n".join(lines)

    async def _register_pick_from_candidates(self, event, result: dict):
        """注册选号交互并渲染候选图（name_list，图内自带序号）；返回图片路径或 None。"""
        ships = result.get("ships") or []
        lang = result.get("lang") or "cn"
        server = result.get("server")
        aid = result.get("aid")

        items = []
        for it in ships:
            sd = it.get("ship_data") or {}
            nm = ((sd.get("cn") if lang == "cn" else None)
                  or it.get("name") or sd.get("en")
                  or it.get("nameCn") or "?")
            sid_ = it.get("ship_id") or it.get("shipId")
            items.append({"name": nm, "ship_id": sid_, "display": nm})

        ssk = self._session_key(event)
        task = self._pick_tasks.pop(ssk, None)
        if task and not task.done():
            task.cancel()
        pending = {
            "items": items,
            "tg": {"aid": aid, "server": server, "lang": lang},
            "expire": time.monotonic() + self._SHIP_PICK_TIMEOUT,
        }
        self._pick_pending[ssk] = pending

        async def _expire():
            await asyncio.sleep(self._SHIP_PICK_TIMEOUT)
            cur = self._pick_pending.get(ssk)
            if cur is pending:
                self._pick_pending.pop(ssk, None)
                try:
                    await event.send(MessageChain().message("选择超时，已取消。"))
                except Exception:  # noqa: BLE001
                    pass

        self._pick_tasks[ssk] = asyncio.ensure_future(_expire())

        # 渲染候选图（复用 name_list 渲染器；失败返回 None 由调用方回退文字）
        try:
            pic = 99  # v3 卡片式新渲染（2026-10-16 用户定稿，走 name_list.get_png_v3）
            res = await self._kp.call("pick_list", parameter=[lang, ships, pic])
            if res.get("status") == "ok" and res.get("img"):
                return res["img"]
            logger.warning(f"[kokomi] 候选图渲染未成功: {res.get('message')!r}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"[kokomi] 候选图渲染异常: {e!r}", exc_info=True)
        return None

    @staticmethod
    def _session_key(event) -> str:
        try:
            sid = event.get_session_id()
        except Exception:  # noqa: BLE001
            sid = None
        return f"{sid or ''}:{event.get_sender_id() or ''}"

    async def _send_candidate_image(self, event, query: str, cands: list[dict]) -> None:
        """把候选渲染成一张图（本地 PIL，纯文本版式）。"""
        def _draw():
            from PIL import Image, ImageDraw, ImageFont
            lines = [f"「{query}」候选 {len(cands)} 艘："] + [
                f"{i}. {c.get('nameCn') or c.get('nameEnglish')}"
                + (f"（{c.get('nameRu')}）" if c.get("nameRu") else "")
                + (f"  {c.get('level')}级 {c.get('shipType') or ''}".rstrip())
                for i, c in enumerate(cands, 1)
            ]
            try:
                _fp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "kokomi", "fonts", "SHSCN.ttf")
                font = ImageFont.truetype(_fp, 20, encoding="utf-8")
            except Exception:  # noqa: BLE001
                font = ImageFont.load_default()
            w = 560
            h = 24 + 26 * len(lines)
            img = Image.new("RGB", (w, h), (32, 34, 40))
            d = ImageDraw.Draw(img)
            for i, ln in enumerate(lines):
                d.text((14, 12 + 26 * i), ln, fill=(235, 235, 235), font=font)
            out = os.path.join(self._tmp_dir(), f"ship_pick_{abs(hash(query)) % 10**8}.png")
            img.save(out)
            return out

        path = await asyncio.to_thread(_draw)
        if path and os.path.isfile(path):
            await self._send_image(event, path)

    def _tmp_dir(self) -> str:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(d, exist_ok=True)
        return d

    async def _batch_ship_query(self, event, names: list[str], tg: dict,
                                forced_ship_id=None) -> str:


        """多船并发查询核心：本地索引解析 -> gather 并发取数渲染 -> 逐个发图 -> 汇总。"""


        lang = tg.get("lang") or "cn"





        async def one(name):


            try:


                return await asyncio.wait_for(_one_impl(name), timeout=45)


            except asyncio.TimeoutError:


                return (name, None, None, "查询超时（上游无响应），请稍后重试这一艘")


            except Exception as e:  # noqa: BLE001


                return (name, None, None, f"{type(e).__name__}: {e}")





        async def _one_impl(name):


            try:


                if forced_ship_id and len(names) == 1:


                    sid, found = str(forced_ship_id), name


                else:


                    sid, found = await self._resolve_ship_id(


                        name, lang, server=tg.get("server"))


                if not sid:


                    return (name, None, None, f"没有找到名为「{name}」的船只")


                async with self._upstream_sem:


                    res = await fetch_and_render(


                        self._kp, script="wws_ship", path="/b/ship-data/",


                        params={"aid": tg["aid"], "server": tg["server"], "lang": lang,


                                "ship_id": sid, "use_pr": True},


                        render_args={"aid": tg["aid"], "server": tg["server"], "lang": lang,


                                     "pic_num": 1},


                        want_image=self._llm_auto_image)


                if res["status"] != "ok" or res["message"] != "SUCCESS":


                    return (name, found, None, humanize_api_error(res))


                return (name, found, res, None)


            except Exception as e:  # noqa: BLE001


                return (name, None, None, f"{type(e).__name__}: {e}")





        results = await asyncio.gather(*(one(n) for n in names))


        summary, any_img = [], False


        for name, found, res, err in results:


            if err:


                summary.append(f"{name}: {err}")


                continue


            if res["img"] and os.path.isfile(res["img"]):


                await self._send_image(event, res["img"])


                any_img = True


                summary.append(f"{found}: 已出图")


            else:


                summary.append(f"{name}: 查询成功但没有图")


        return await self._deliver_data_or_return(


            event, f"[批量查询 {len(names)} 艘]\n" + "\n".join(summary),


            img_sent=any_img)





    def _ensure_llm_ready(self) -> bool:


        """LLM 工具总开关 + 插件加载状态检查。"""


        if not self._llm_enabled:


            return False


        return self._kp is not None


