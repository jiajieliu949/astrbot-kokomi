---
name: kokomi-query
description: 战舰世界战绩查询工具调度规则。用户询问战绩、水表、船只、公会、服务器数据时，按本技能的映射调用 kokomi_* 工具；多船用批量工具；命中静默；未命中解释。
---

# Kokomi 战绩查询

你已接入战舰世界战绩查询插件（工具名前缀 `kokomi_`，共 24 个工具）。收到战绩相关请求时，**严格按以下映射调用工具**：

## 触发词 → 工具映射

| 用户请求 | 工具 |
|---|---|
| 单船总战绩（「查我的大和」） | `kokomi_ship` |
| **一条消息问多艘船**（「查A、B、C的战绩」） | `kokomi_ship_batch`（船名列表逗号分隔一次传入，**禁止逐个调用 kokomi_ship**） |
| 总水表（简略，「我的水表」） | `kokomi_account` |
| 详细总表（「wws me info」） | `kokomi_info` |
| 绑定及账户数据 | `kokomi_card` |
| 近期按天（「最近7天」） | `kokomi_recent` |
| 近期随机战 / 排位 | `kokomi_recent_random` / `kokomi_recent_rank` |
| 最近24小时逐场 | `kokomi_recent_battles` |
| 单船近期 | `kokomi_ship_recent` |
| 排位赛数据 / 指定赛季 | `kokomi_rank` / `kokomi_rank_season` |
| 公会信息 / 赛季 / 历史 | `kokomi_clan_info` / `kokomi_clan_season` / `kokomi_clan_history` |
| 按舰种筛选（「我的10级战列」） | `kokomi_ships` |
| 船只列表 | `kokomi_search_ship` |
| 服务器船只数据 / 单船服务器数据 | `kokomi_server_ships` / `kokomi_ship_server_stats` |
| 全服排行前50 | `kokomi_ship_server_rank` |
| 在线人数 | `kokomi_online` |
| 绑定引导 | `kokomi_bind` |

## 行为准则

1. **命中静默**：工具返回「渲染图已直接发送给用户」= 图已发出 → 你只回一句简短确认（如「已查收 📊」），**禁止复述数据、禁止编造数据**。
2. **未命中**：工具返回错误或未命中 → 用一句话向用户解释原因（没玩过 / 没绑定 / 船名不对），并给建议。
3. **船名兜底**：船名搜不到 → 先调 `kokomi_search_ship` 查正确写法再重试一次；仍失败如实告知。
4. **多船必批量**：用户一次问多艘船 → 必须调 `kokomi_ship_batch`，不要逐个调 `kokomi_ship`。
5. **前缀**：指令示例一律用 `wws`（如 `wws me info`）—— 这是当前面板配置的前缀。
6. **服务器分区**：工具自动按玩家绑定的服务器选择船表（ru→LESTA，直营服→WG），无需用户关心。

## 指令体系

插件同时支持指令式调用：`wws me` / `wws me info` / `wws rank` / `wws bind 服务器 昵称` 等 32 个子指令（用户直接发以 wws 开头的消息时不经 LLM，插件直接处理）。
