# astrbot_plugin_kokomi

战舰世界（World of Warships）战绩查询插件 —— AstrBot 版。

渲染器移植自 NoneBot2 版 [Kokomi](https://github.com/) 插件（代码随包分发，无 NoneBot 运行时依赖），
支持 **wws 指令** 与 **LLM 自然语言工具** 两条查询通道，输出 Kokomi 风格战绩图。

- 版本：v0.2.0
- 作者：local（本项目适配）
- 上游数据：`http://43.155.60.190:8000`（Kokomi API）

---

## 功能特性

### 双通道查询
- **指令通道**：`wws ru <昵称> ship <船名>` 这类结构化指令，共 30+ 个子指令（见[指令列表](#指令列表)）；
- **LLM 通道**：注册 26 个 `kokomi_*` 工具，支持「查一下 xxx 的施里芬战绩」这类自然语言请求。

### 渲染图
- 所有查询结果渲染为 Kokomi 原版风格图片（水表 / 单船卡 / 近期 / 排位 / 公会 …）；
- **候选选船**：船名模糊命中多艘时，渲染**带序号**的候选列表图，用户回复序号即可直查；
- **精确名优先**：查询词与某船中文名完全一致时（如「施里芬」「神风」），跳过候选直接查该船；
- **长文本自适应**：候选图中英文列按文本长度自动缩字号，防溢出；
- **候选去重**：按 ship_id 归一化去重（接口/本地混型 id 也能正确合并）。

### 数据
- 本地船名索引：`kokomi_llm/data/ship_index_ru.json`（俄服，**955 艘**；中文名数据源为 Korabli_localization_chs，经 TomatoRadar 打包，见[数据来源](#数据来源)）
  与 `ship_index_wg.json`（外服）；
- 索引已过滤不可玩组（disabled / unavailable / demoWithoutStats / event 等测试船）；
- 索引与接口结果做**并集**：本地全名 + 接口模糊，兼顾命中率与准确性。

### 稳健性
- 上游接口超时/波动时自动降级（接口不可用 → 只用本地索引）；
- 「没玩过这艘船」等业务错误按上游 message 精确翻译（`NO STATISTICS IN THIS SHIP` → 无战绩提示），
  选号后也会把失败原因发给用户，不会静默；
- 工具调用纪律：以**本轮实际工具列表**判断可用性，禁止凭历史/猜测说「工具不可用」。

---

## 安装

### 1. 放置插件
将本目录放入 AstrBot 的 `data/plugins/astrbot_plugin_kokomi/`，在 WebUI 插件页重载。

### 2. 安装依赖
```bash
# 容器/宿主机通用（装进 AstrBot 运行环境）
pip install opencv-python-headless
```

> 渲染器自带在 `kokomi/` 目录（约 1.1G，含字体与素材），无需额外安装 Kokomi。

### 3. 配置
WebUI → 插件配置 → `astrbot_plugin_kokomi`，见[配置说明](#配置说明)。

---

## 配置说明

上游 API 凭据通过环境变量配置，不要写入源码：

```bash
KOKOMI_API_URL=http://43.155.60.190:8000
KOKOMI_API_TYPE=Bearer
KOKOMI_API_USERNAME=你的用户名
KOKOMI_API_PASSWORD=你的密码
```

其中 `KOKOMI_API_URL` 和 `KOKOMI_API_TYPE` 可省略，分别默认为上游地址和 `Bearer`。

| 配置项 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `command` | string | `wws` | 指令前缀 |
| `group_blacklist` | list | `[]` | 群聊黑名单，填写群号；列表中的群不触发查询或回复 |
| `llm_tool_enable` | bool | `true` | LLM 工具总开关（自然语言查询）|
| `llm_tool_evaluate` | bool | `true` | 查询结果是否让 AI 顺带点评 |
| `llm_tool_rate_limit` | int | `10` | 每会话每分钟查询上限（≤0 不限）|
| `llm_auto_image` | bool | `true` | 查询时同时渲染原图发给用户 |

**工具开关**（均为 bool，默认 `true`，可按需关闭单个能力）：

| 配置项 | 能力 |
|---|---|
| `llm_tool_enable_account` | 总体战绩（水表）|
| `llm_tool_enable_ship` | 单船战绩 |
| `llm_tool_enable_recent` | 近期战绩汇总（按天）|
| `llm_tool_enable_recent_random` | 近期随机战 |
| `llm_tool_enable_recent_rank` | 近期排位战 |
| `llm_tool_enable_ship_recent` | 单船近期战绩 |
| `llm_tool_enable_recent_battles` | 最近 24 小时逐场明细 |
| `llm_tool_enable_ships` | 按舰种/等级筛选 |
| `llm_tool_enable_bind` | 引导绑定游戏账号 |
| `llm_tool_enable_info` | 玩家总表（详细水表）|
| `llm_tool_enable_card` | 绑定及账户数据卡片 |
| `llm_tool_enable_oper` | 剧情数据 |
| `llm_tool_enable_cw` | 公会战数据 |
| `llm_tool_enable_rank` | 排位赛数据总览 |
| `llm_tool_enable_rank_season` | 指定排位赛季 |
| `llm_tool_enable_clan_info` | 公会信息 |
| `llm_tool_enable_clan_season` | 公会指定赛季 |
| `llm_tool_enable_clan_history` | 公会赛季历史 |
| `llm_tool_enable_me_ship_rank` | 自己单船全服排名 |
| `llm_tool_enable_ship_server_rank` | 单船全服排行前 50 |
| `llm_tool_enable_ship_server_stats` | 单船服务器总体数据 |
| `llm_tool_enable_online` | 服务器在线人数 |
| `llm_tool_enable_search_ship` | 船只列表查询 |
| `llm_tool_enable_server_ships` | 服务器船只数据 |
| `llm_tool_enable_ship_batch` | 多船批量查询 |

---

## 指令列表

前缀默认 `wws`（可在配置中修改）。服务器代号：`ru`（俄服）/ `asia` `/ eu` `/ na`（外服）。

### 基础查询
| 指令 | 说明 |
|---|---|
| `wws bind` | 绑定游戏账号 |
| `wws me` | 自己的总体战绩 |
| `wws me ship <船名>` | 自己单船战绩 |
| `wws <昵称> ship <船名>` | 指定玩家单船战绩 |
| `wws <昵称>` | 指定玩家总体战绩 |
| `wws ship <船名>` | 船只资料/属性 |

### 战绩明细
| 指令 | 说明 |
|---|---|
| `wws me recent` | 近期战绩（按天）|
| `wws me recent random` | 近期随机战 |
| `wws me recent rank` | 近期排位战 |
| `wws me recent battles` | 最近 24 小时逐场 |
| `wws me ships` | 按舰种/等级筛选 |
| `wws me info` | 详细水表 |
| `wws me card` | 账户数据卡片 |

### 排位 / 公会 / 剧情
| 指令 | 说明 |
|---|---|
| `wws me rank` / `wws me rank season <n>` | 排位总览 / 指定赛季 |
| `wws me clan` / `wws me clan season` / `wws me clan history` | 公会信息 / 赛季数据 / 历史 |
| `wws me cw` | 公会战数据 |
| `wws me oper` | 剧情数据 |

### 排行 / 服务器
| 指令 | 说明 |
|---|---|
| `wws me ship rank <船名>` | 自己单船全服排名 |
| `wws ship rank <船名>` | 单船全服排行前 50 |
| `wws ship stats <船名>` | 单船服务器总体数据 |
| `wws online` | 服务器在线人数 |
| `wws ships` | 船只列表查询 |

> 完整指令以插件实际注册为准（共 33 条）。

---

## LLM 自然语言查询

开启 `llm_tool_enable` 后，模型会获得以下工具（前缀 `kokomi_`）：

- `kokomi_account` / `kokomi_info` / `kokomi_card` —— 总体水表 / 详细水表 / 账户卡片
- `kokomi_ship` / `kokomi_ship_batch` / `kokomi_ships` —— 单船 / 多船批量 / 舰种筛选
- `kokomi_recent` / `kokomi_recent_random` / `kokomi_recent_rank` / `kokomi_ship_recent` / `kokomi_recent_battles`
- `kokomi_rank` / `kokomi_rank_season` / `kokomi_cw` / `kokomi_oper`
- `kokomi_clan_info` / `kokomi_clan_season` / `kokomi_clan_history`
- `kokomi_me_ship_rank` / `kokomi_ship_server_rank` / `kokomi_ship_server_stats`
- `kokomi_online` / `kokomi_search_ship` / `kokomi_server_ships`

**工具返回约定**：命中唯一或直查成功 → 直接发渲染图，返回「渲染图已直接发送给用户」；
多艘命中 → 发候选列表图，等待用户回复序号（15 秒内有效）。

---

## 候选选船机制

当船名查询命中多艘（如「上将」「彼得罗」），插件会：

1. 渲染**带序号的候选列表图**（等级 / 舰种 / 中文名 / 英文名 四列）；
2. 注册 15 秒内的序号回复；
3. 用户回复数字 → 用该候选的 **ship_id** 精确查询（`forced_ship_id`，不会再模糊）；
4. 超时 → 提示「选择超时，已取消」并清除状态。

**精确名优先**：查询词与某船中文名**完全一致**时跳过候选直接查询（如「施里芬」→ 直接查施里芬，
「施里芬CLR」→ 查 CLR 变体）。

**去重**：候选按 `ship_id`（字符串归一化）去重——接口与本地索引的 id 混型不会导致重复条目。
（注：游戏里真实存在的同名不同船——如旧版/新版「彼得罗·巴格拉季昂」——会保留两条，属正常现象。）

---

## 数据文件

| 文件 | 说明 |
|---|---|
| `kokomi_llm/data/ship_index_ru.json` | 俄服船名索引（955 艘，数据链：Korabli_localization_chs → TomatoRadar → 本索引；已过滤测试船）|
| `kokomi_llm/data/ship_index_wg.json` | 外服船名索引 |
| `kokomi_llm/data/ship_code_cn.json` | 船只内部代号 → 中文名映射 |
| `kokomi_llm/data/ship_blocklist.json` | 屏蔽名单 |

### 数据来源

俄服船名的**中文翻译源头**是 [DDFantasyV/Korabli_localization_chs](https://github.com/DDFantasyV/Korabli_localization_chs)
（战舰世界俄服 Korabli 的中文本地化项目）。数据链：

```
Korabli_localization_chs（船名中文/俄文/英文翻译）
        │
        ▼
TomatoRadar ships_lesta.json（打包为结构化数据：shipId + 各语言名 + tier/type/group）
        │
        ▼
dogtag-sync/gen_ru_index.py（字段映射 + 过滤测试船 + 生成索引）
        │
        ▼
kokomi_llm/data/ship_index_ru.json（本插件使用）
```

**索引更新**：版本更新时替换 TomatoRadar 的 `ships_lesta.json`，重跑 `gen_ru_index.py` 即可。
旧索引会被自动备份（`ship_index_ru.json.bak-*`）。

---

## 架构

```
astrbot_plugin_kokomi/
├── main.py               # AstrBot 插件主体：指令、LLM 工具、候选选船、发送
├── kokomi_loader.py      # Kokomi 代码加载器（无 NoneBot 运行时，独立渲染）
├── kokomi/               # 随包分发的 Kokomi 渲染器（约 1.1G：脚本/字体/素材）
│   ├── common/           #   公共模块：name_list / search_ship_name / call_api …
│   └── scripts/          #   渲染脚本：wws_me / wws_ship / wws_recent / pick_list …
├── kokomi_llm/           # LLM 桥接层
│   ├── tools.py          #   26 个 kokomi_* 工具定义
│   ├── query.py          #   fetch_and_render（取数 + 渲染）
│   ├── guide.py          #   业务文案映射（humanize_api_error）
│   └── data/             #   船名索引等数据
├── _conf_schema.json     # WebUI 配置定义
└── metadata.yaml
```

---

## 常见问题

**Q：查询为什么有 3-6 秒延迟？**
A：耗时主要来自三段：昵称→aid 解析（上游）、接口搜索/本地并集、图渲染（首次渲染会加载字体素材，
同进程内后续更快）。上游波动时插件会自动降级到本地索引。

**Q：提示「没有玩过这艘船」/「您在该船只上没有数据」？**
A：该玩家没有这艘船的战绩记录（上游返回 `NO STATISTICS IN THIS SHIP`），不是插件故障。

**Q：候选图里为什么有两艘同名船？**
A：游戏资源包里确实存在（如「彼得罗·巴格拉季昂」的旧版/新版两个 ship_id），按设计保留。

**Q：LLM 用不了工具 / 提示工具不可用？**
A：先确认 WebUI 配置里 `llm_tool_enable` 已开启；插件应按本轮实际工具列表判断可用性，
如出现「未调用就说不可用」的情况，把对话发出来排查。

---

## 致谢

- 渲染器与查询逻辑：[Kokomi](https://github.com/)（NoneBot2 版原作者）
- 俄服船名中文数据：[DDFantasyV/Korabli_localization_chs](https://github.com/DDFantasyV/Korabli_localization_chs)（中文本地化）
- 结构化数据打包：TomatoRadar（ships_lesta.json）
- 本项目适配：AstrBot 插件封装、LLM 工具层、候选选船、数据索引与去重逻辑
