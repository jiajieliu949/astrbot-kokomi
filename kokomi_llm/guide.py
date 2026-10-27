# -*- coding: utf-8 -*-
"""LLM 工具层的限流与话术。

LLM 可能被用户引导着连续调用工具（刷屏 / 打爆上游接口），
所以按会话限频；错误信息区分「业务态」与「程序态」，
给模型的是行动指引而不是原始报错。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from astrbot.api import logger

# 业务态：上游正常返回、但没有数据。不是故障，模型应如实转述。
BUSINESS_MESSAGES = {
    # 可能是这段期间真没打，也可能超出服务器数据留存范围 —— 一并如实说明
    "DATE NOT FOUND": "该日期范围内没有任何战斗记录（可能这段期间没打，也可能超出了服务器可查的数据范围）",
    "NO STATISTICS IN THIS SHIP": "没有玩过这艘船",
    "NO BIND DATA": "__NOT_BOUND__",   # 特殊标记：调用方需要区分「没绑定」话术
    "PLEASE CONNECT AUTHOR": "该功能需要联系插件作者开启",
}

# 程序态关键词 -> 给模型的指引
_ERROR_GUIDE = {
    "PROGRAM ERROR": "上游接口程序异常，请建议用户稍后再试",
    "TIMEOUT": "上游接口超时，请建议用户稍后重试",
}


class RateLimiter:
    """按会话限频：滑动窗口内最多 max_calls 次。max_calls<=0 表示不限流。"""

    def __init__(self, max_calls: int = 10, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, session_id: str) -> tuple[bool, int]:
        """返回 (是否放行, 需要等待的秒数)。放行时记录一次调用。"""
        if self.max_calls <= 0:
            return True, 0
        now = time.monotonic()
        q = self._hits[session_id]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max_calls:
            wait = int(self.window - (now - q[0])) + 1
            return False, wait
        q.append(now)
        return True, 0


def humanize_api_error(result: dict) -> str:
    """把 Kokomi API 的返回（status/message）翻译成给模型看的一句话。"""
    msg = str(result.get("message") or "")
    status = str(result.get("status") or "")

    if msg in BUSINESS_MESSAGES:
        mapped = BUSINESS_MESSAGES[msg]
        if mapped == "__NOT_BOUND__":
            # 正常情况下 resolve_target 已在更早环节拦下未绑定，
            # 走到这里说明是取数环节才发现的，给同样的行动指引。
            return "该用户尚未绑定游戏账号。请提示 TA 先发送绑定指令（绑定指令见插件帮助）"
        return mapped

    if status == "error" or msg == "PROGRAM ERROR":
        err = str(result.get("error") or "")
        logger.warning(f"[kokomi-llm] 上游程序错误: {err} track={result.get('track_id')}")
        return _ERROR_GUIDE.get("PROGRAM ERROR") + f"（内部标记 {result.get('track_id', '?')}）"

    return f"查询未成功（{status or '未知状态'}: {msg or '无信息'}），请如实告知用户"
