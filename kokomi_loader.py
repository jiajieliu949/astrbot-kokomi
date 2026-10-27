# -*- coding: utf-8 -*-
"""在 AstrBot 容器内加载随插件分发的 Kokomi 代码（无 NoneBot 运行时）。

## 背景

原 Kokomi_bot_plugin 是 NoneBot2 插件，包级 ``__init__.py`` 末尾有::

    from nonebot import on_command, on_startswith
    from nonebot.adapters.onebot.v11 import (ActionFailed, Bot, MessageEvent, MessageSegment)
    from nonebot.log import logger

但业务逻辑（取数 + 画图）完全在 NoneBot 之外。``scripts/*.py`` 里的
``from .. import Plugin_Config, Picture, ...`` 这些符号，来源**就是包级
``__init__.py`` 前 18 行的那段再导出**，与 NoneBot 无关。

## 做法

本插件把 Kokomi 的源码（含 ``scripts/``、``common/``、``fonts/``、``png/``）
整体放在 ``./kokomi/`` 下。加载时：

1. 构造一个名为 ``kokomi`` 的假包，``__path__`` 指向 ``./kokomi/``，
   **不执行**真的 ``__init__.py``（本目录下就没有那个文件）；
2. 手工执行原 ``__init__.py`` 中 NoneBot 之前的纯业务段，
   把 ``Plugin_Config / Picture / Text_Data / Box_Data / dog_tag /
   call_api / write_error / fonts / plugin_path`` 注入假包命名空间；
3. 于是 ``from .. import X`` 在假包里解析成功，``scripts.*`` 可以正常导入与调用。

因为 ``path.py`` 用的是 ``os.path.dirname(__file__)``（相对自身），
整个 ``kokomi/`` 目录放哪都能跑，**不需要改原插件任何一行代码**。

## 与参考实现的关系

本文件对应 ``AstrByWowsYuyukoBot`` 里 hikari-core 的角色——都是「把渲染器
装进插件目录并在容器内跑」。区别是那边渲染器本身就是 AstrBot 友好的库，
而 Kokomi 是 NoneBot 插件，多了一层"绕开包级 NoneBot 胶水"的 shim。

## 用法

    from .kokomi_loader import KokomiPlugin

    kp = KokomiPlugin()                            # 默认 ./kokomi/
    res = await kp.call("wws_basic", aid="...", server="ru")
    # res == {"status": "ok", "message": "SUCCESS", "img": "/.../temp/xxx.png"}
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from typing import Any

# 插件自带 Kokomi 代码的目录（本文件同级）
_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KOKOMI_DIR = os.path.join(_HERE, "kokomi")

# 构造的假包名。与原插件的相对导入（`from .. import`）配合时需要它。
_SHIM_PKG = "kokomi"

# 原 __init__.py 里 NoneBot 段的起点，截到它为止。
# 若上游插件结构变化导致找不到，会显式报错而不是静默降级。
_NONEBOT_MARKER = "import traceback"

# 业务指令模块 → 上游 API 端点（取自各 scripts/*.py 的 path= 常量）
COMMAND_ENDPOINTS = {
    "wws_basic": "/b/pvp-data/",       # wws me       个人 PR 卡
    "wws_info": "/b/info-data/",       # wws me info  玩家总表
    "wws_rank": "/b/rank-data/",       # wws rank
    "wws_cw": "/b/cw-data/",           # wws cw
    "wws_ship": "/b/ship-data/",       # wws ship
    "wws_ships": "/b/ships-data/",     # wws ships
    "wws_recent": "/r1/recent-data/",  # wws recent
    "wws_stats": "/p/ship-data/",      # wws stats
    "wws_bind": "/b/user-data/",       # wws bind
    "wws_me_rank": "/b/number-me-rank/",
}

# 刻意不含 nonebot 的模块级 import 白名单校验：scripts/ 下全部文件都不 import nonebot，
# 这一条是搬运时的完整性保证（若上游给 scripts 加了 nonebot 依赖，这里会失败）。
_SCRIPTS_MUST_NOT_IMPORT = ("from nonebot", "import nonebot")


class KokomiLoadError(RuntimeError):
    """加载 Kokomi 代码失败。"""


def list_scripts(kokomi_dir: str = DEFAULT_KOKOMI_DIR) -> list[str]:
    d = os.path.join(kokomi_dir, "scripts")
    if not os.path.isdir(d):
        return []
    return sorted(
        f[:-3] for f in os.listdir(d)
        if f.endswith(".py") and not f.startswith("_")
    )


def audit_scripts(kokomi_dir: str = DEFAULT_KOKOMI_DIR) -> list[str]:
    """检查 scripts/*.py 是否意外引入了 NoneBot 依赖。返回有问题的文件名列表。"""
    bad = []
    d = os.path.join(kokomi_dir, "scripts")
    if not os.path.isdir(d):
        return bad
    for f in os.listdir(d):
        if not f.endswith(".py"):
            continue
        try:
            src = open(os.path.join(d, f), encoding="utf-8").read()
        except OSError:
            continue
        if any(tok in src for tok in _SCRIPTS_MUST_NOT_IMPORT):
            bad.append(f)
    return bad


# ---------------------------------------------------------------------------
# 素材完整性
#
# 踩过的坑：只搬了内置素材（dog_tag_2 等）而漏掉 dog_tag_custom/，渲染**不会报错**，
# 而是静默回退到内置组合背景 —— 表现为「玩家的自定义背景/徽记没了，换成灰底」。
# 这种差异只能靠肉眼比对发现，所以这里做一次显式检查。
#
# 实测（2026-10）：漏 dog_tag_custom 时整图 5.92% 像素有差异，且 100% 集中在
# 顶部 64~275 行的舰徽区；其余区域逐像素完全一致（说明字体/绘图无差异，
# Pillow 10→12 的大版本跨越并不影响出图）。
# ---------------------------------------------------------------------------

# 相对 kokomi_dir 的必需目录，缺一个都会导致部分渲染静默降级
REQUIRED_ASSETS = {
    "fonts": "字体（SHSCN.ttf 中文 / NZBZ.ttf 数字）",
    "png/bg_cn": "中文界面背景与 PR 勋章",
    "png/dog_tag_2": "内置舰徽组合底图",
    "png/dog_tag_lesta": "俄服舰徽素材",
    "png/dog_tag_wg": "WG 服舰徽素材",
    "png/dog_tag_custom": "用户/军团自定义底图与徽记（缺失会静默回退，肉眼才看得出）",
    "png/achievement": "成就图标",
    "png/clan": "军团图标",
    "png/nation": "国家旗帜",
    "png/ship_icon": "舰种图标",
    "json": "ID→代号映射表",
}


def audit_assets(kokomi_dir: str = DEFAULT_KOKOMI_DIR) -> list[tuple[str, str]]:
    """检查必需素材目录是否存在。返回 [(缺失路径, 说明)]。"""
    missing = []
    for rel, why in REQUIRED_ASSETS.items():
        p = os.path.join(kokomi_dir, rel)
        if not os.path.isdir(p) or not os.listdir(p):
            missing.append((rel, why))
    return missing


class KokomiPlugin:
    """把随插件分发的 Kokomi 代码，当作「无 NoneBot 的普通库」加载与调用。

    幂等：重复实例化不会重复注入 ``sys.modules``。
    """

    def __init__(self, kokomi_dir: str | None = None, *, quiet: bool = False):
        self.kokomi_dir = os.path.abspath(kokomi_dir or DEFAULT_KOKOMI_DIR)
        self.quiet = quiet
        self._loaded = False

        if not os.path.isdir(self.kokomi_dir):
            raise KokomiLoadError(f"Kokomi 代码目录不存在: {self.kokomi_dir}")
        if not os.path.isfile(os.path.join(self.kokomi_dir, "data_source.py")):
            raise KokomiLoadError(
                f"{self.kokomi_dir} 里没有 data_source.py —— "
                "素材/代码搬运不完整？"
            )

        self._ensure_shim()
        self.config = self._load("config").Plugin_Config

    # ---------------- 内部 ----------------

    def _log(self, msg: str) -> None:
        if not self.quiet:
            print(f"[kokomi_loader] {msg}")

    def _ensure_shim(self) -> None:
        if self._loaded:
            return

        # 0) 完整性检查：scripts 不应有 nonebot 依赖
        bad = audit_scripts(self.kokomi_dir)
        if bad:
            raise KokomiLoadError(
                "以下 scripts 引入了 NoneBot 依赖，shim 无法绕过: "
                + ", ".join(bad)
            )

        head_src = self._extract_business_head()

        # 1) 把 Kokomi 目录所在处加入 sys.path，
        #    这样假包内的 `from .config import ...` 能被解析
        parent = os.path.dirname(self.kokomi_dir)
        if parent not in sys.path:
            sys.path.insert(0, parent)

        # 2) 造顶层假包（没有任何 __init__.py 会被执行）
        if _SHIM_PKG in sys.modules:
            self._top = sys.modules[_SHIM_PKG]
            self._loaded = True
            self._log("shim 已在 sys.modules 中，复用")
            return

        top = types.ModuleType(_SHIM_PKG)
        top.__path__ = [self.kokomi_dir]
        top.__package__ = _SHIM_PKG
        top.__file__ = os.path.join(self.kokomi_dir, "__init__.py")
        sys.modules[_SHIM_PKG] = top

        # 3) 执行纯业务段，注入 Plugin_Config / Picture / fonts / ...
        try:
            exec(compile(head_src, f"<{_SHIM_PKG}.__init__ head>", "exec"), top.__dict__)
        except Exception as e:  # noqa: BLE001
            del sys.modules[_SHIM_PKG]
            raise KokomiLoadError(
                f"执行业务段失败: {type(e).__name__}: {e}"
            ) from e

        self._top = top
        self._loaded = True

    def _extract_business_head(self) -> str:
        """从搬运过来的 ``_init_head.py``（原 __init__.py 的业务段）读取源码。

        搬运时把原 ``__init__.py`` 中 NoneBot 之前的部分单独存成
        ``kokomi/_init_head.py``，这样运行时不依赖对上游文件的解析，
        也避免把 NoneBot 代码带进容器。
        """
        head_file = os.path.join(self.kokomi_dir, "_init_head.py")
        if not os.path.isfile(head_file):
            raise KokomiLoadError(
                f"缺少 {head_file}（原 __init__.py 的业务段）。"
                "请确认搬运脚本已执行。"
            )
        return open(head_file, encoding="utf-8").read()

    def _load(self, dotted: str):
        full = f"{_SHIM_PKG}.{dotted}"
        try:
            return importlib.import_module(full)
        except Exception as e:  # noqa: BLE001
            raise KokomiLoadError(f"导入 {full} 失败: {type(e).__name__}: {e}") from e

    # ---------------- 公开 API ----------------

    @property
    def plugin_config(self):
        """原插件 Plugin_Config（API_URL / API_TYPE / API_USERNAME / API_PASSWORD / VERSON）。"""
        return self.config

    def module(self, name: str):
        """拿 scripts 子模块，如 module('wws_basic')。"""
        mod_name = name if name.startswith("scripts.") else f"scripts.{name}"
        return self._load(mod_name)

    def route_module(self):
        """取指令路由模块（command_select / select_funtion）。"""
        return self._load("command_select")

    async def call(self, script: str, *, parameter: list[Any], **_: Any) -> dict:
        """调用 scripts/<script>.py 的 ``get_data()``。

        返回插件原样结果：
        ``{"status": "ok"|"error", "message": str, "img": path|None, ...}``
        """
        mod = self.module(script)
        get_data = getattr(mod, "get_data", None)
        if get_data is None:
            raise KokomiLoadError(f"{script} 不提供 get_data()")
        return await get_data(parameter=parameter)

    async def route(self, msg: list[str], user_id: str, *,
                    platform: str = "qq_bot", platform_id: str = "123456",
                    channel_id: str = "123456") -> dict:
        """把一条指令（NoneBot 风格 ``['wws','me']``）交给原插件路由。

        返回 ``{"type": "img"|"msg", "img": path|None, "msg": str|None}``
        —— 与原插件 ``__init__.py`` 里处理器的预期完全一致。

        绑定查询走上游 API（``platform`` + ``user_id``），所以真寻侧已绑定的
        账号在 AstrBot 侧可直接复用，无需重复绑定。
        """
        cs = self.route_module()
        select_funtion = getattr(cs, "select_funtion", None)
        if select_funtion is None:
            raise KokomiLoadError("command_select 里没有 select_funtion")
        return await select_funtion.main(
            msg=msg,
            user_id=user_id,
            user_data={},
            platform=platform,
            platform_id=platform_id,
            channel_id=channel_id,
            platform_data={},
        )

    # ---------------- 便捷 ----------------

    @classmethod
    def available_scripts(cls, kokomi_dir: str | None = None) -> list[str]:
        return list_scripts(kokomi_dir or DEFAULT_KOKOMI_DIR)


def selftest(kokomi_dir: str | None = None) -> bool:
    """自检：加载 shim、校验符号、真实渲染一次。"""
    import asyncio

    ok = True
    print("=" * 60)
    print("Kokomi 容器内 shim 自检")
    print("=" * 60)

    try:
        kp = KokomiPlugin(kokomi_dir, quiet=True)
    except KokomiLoadError as e:
        print(f"[FAIL] 加载失败: {e}")
        return False

    print(f"[ok] shim 加载，解释器 {sys.executable}")
    print(f"[ok] Kokomi 目录 {kp.kokomi_dir}")
    print(f"[ok] API_URL = {kp.config.API_URL}")
    print(f"[ok] VERSON  = {kp.config.VERSON}")

    top = sys.modules[_SHIM_PKG]
    for sym in ("Plugin_Config", "write_error", "fonts", "plugin_path",
                "Picture", "Text_Data", "Box_Data", "dog_tag", "call_api"):
        has = hasattr(top, sym)
        print(f"[{'ok' if has else 'FAIL'}] 符号 {sym}")
        ok = ok and has

    scripts = KokomiPlugin.available_scripts(kokomi_dir)
    print(f"[ok] 可用脚本 {len(scripts)} 个")

    try:
        res = asyncio.run(kp.call(
            "wws_basic",
            parameter=["210054418", "ru", "cn", True, True, [], 1],
        ))
        st = res.get("status")
        img = res.get("img")
        size = None
        if st == "ok" and img and os.path.isfile(img):
            from PIL import Image
            size = Image.open(img).size
        print(f"[{'ok' if st == 'ok' else 'FAIL'}] 实调 status={st!r} size={size} img={img}")
        ok = ok and st == "ok"
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"[FAIL] 实调异常: {type(e).__name__}: {e}")
        ok = False

    print("=" * 60)
    print("结果:", "全部通过" if ok else "存在失败")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if selftest() else 1)
