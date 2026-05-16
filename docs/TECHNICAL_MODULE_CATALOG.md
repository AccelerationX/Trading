# Technical Module Catalog

## 1. 目标

本文件用于把 `Trading` 和 `TradingMain` 里值得保留的技术分析资产，拆成新系统可复用的技术模块。

这里继承的是：

- 形态研究经验
- 市场环境适用条件
- 执行与风控约束

这里不继承的是：

- 旧策略线的最终收益结论
- 受未来函数污染的最终打分
- 难以解释的复杂组合结果

## 2. 迁移原则

### 2.1 继承技术经验，不继承旧结论

旧项目里的高收益策略线不能直接迁入新系统作为买卖依据。  
但它们拆开后的“技术动作和适用环境”很有价值。

### 2.2 技术模块只负责一部分职责

技术模块在新系统里主要负责：

- 候选生成
- 技术状态描述
- 入场时机提示
- 环境适配提醒

它不单独负责最终交易结论。

### 2.3 每个模块必须回答 4 个问题

1. 它在抓什么市场行为。
2. 它适合什么市场环境。
3. 它最怕什么失效方式。
4. 它在新系统里属于候选、确认，还是过滤层。

## 3. 技术模块分组

## 3.1 趋势延续组

### `TM001_line_a_trend_continuation`

- 来源参考：
  - `Trading/run_line_a_simulation_pack.py`
  - `Trading/run_line_a_variant_research.py`
  - `TradingMain/research/tools/strategy_line_a_family.py`
- 核心行为：
  - 主板趋势延续
  - 相对强势
  - 排名持有
- 在新系统中的角色：
  - 核心候选生成器
- 更适合：
  - `risk_on`
  - 中高成交额
  - 主板或大中票活跃阶段
- 主要失效：
  - 追高后分歧
  - 风格急切换
  - 指数弱而个股假强

### `TM002_breakout_and_relative_strength`

- 来源参考：
  - `Trading/run_buy_timing_04_rel_strength.py`
  - `Trading/run_buy_timing_03_opening_pattern.py`
  - `Trading/run_main_board_entry_rank_survival.py`
- 核心行为：
  - 突破后延续
  - 量价同步增强
  - 强势股筛选
- 在新系统中的角色：
  - 技术确认器
- 更适合：
  - 热主线
  - 板块有领涨股
- 主要失效：
  - 炸板回落
  - 主线退潮

## 3.2 修复反弹组

### `TM101_behavior_repair_rebound`

- 来源参考：
  - `Trading/run_behavior_path_repair_live_pack.py`
  - `Trading/run_behavior_path_repair_simulation_pack.py`
  - `Trading/run_recent_behavior_simulation_pack.py`
  - `TradingMain/research/tools/strategy_behavior_state_family.py`
- 核心行为：
  - 行为修复
  - 超跌后的反弹延续
  - 下影线/修复率/反弹状态
- 在新系统中的角色：
  - 修复型候选生成器
- 更适合：
  - 分化市
  - 局部题材修复
  - 并非极强的普涨市
- 主要失效：
  - 抄到底部继续下跌
  - 无主线承接

### `TM102_trend_repair_low_vol`

- 来源参考：
  - `Trading/run_trend_repair_switch_simulation_pack.py`
  - `Trading/strategy_line_guide.md`
- 核心行为：
  - 修复 + 低波过滤
  - 突破率和修复率结合
- 在新系统中的角色：
  - 修复型过滤器
- 更适合：
  - `selective`
  - 中性偏强市场
- 主要失效：
  - 极端情绪主升浪里跑输纯进攻线
  - 低波股缺少爆发力

## 3.3 群组轮动组

### `TM201_group_rotation_repair`

- 来源参考：
  - `Trading/run_sector_rotation_simulation_pack.py`
  - `Trading/run_latent_group_behavior_bridge_simulation_pack.py`
  - `TradingMain/research/tools/strategy_group_rotation_family.py`
- 核心行为：
  - 群组/板块/风格轮动
  - 先选强组，再在组内排序
- 在新系统中的角色：
  - 板块层候选压缩器
- 更适合：
  - 有明显板块轮动
  - 主线不是单一龙头而是群体推进
- 主要失效：
  - 极端单点龙头行情
  - 板块快速切换过快

### `TM202_sector_rotation_and_industry_strength`

- 来源参考：
  - `Trading/projects/sector_rotation`
  - `TradingMain/research/tools/strategy_industry_first_rotation.py`
- 核心行为：
  - 行业强弱识别
  - 行业内优中选优
- 在新系统中的角色：
  - 主线映射辅助器
- 更适合：
  - 政策驱动行业行情
  - 宽度足够的轮动市场
- 主要失效：
  - 纯消息脉冲但缺乏持续板块强度

## 3.4 波动与压缩组

### `TM301_volatility_compression_breakout`

- 来源参考：
  - `Trading/projects/volatility_compression_release`
  - `TradingMain/docs/STRATEGY_LINE_DESIGN.md`
- 核心行为：
  - 波动收敛后方向选择
  - 放量突破确认
- 在新系统中的角色：
  - 启动前观察器
- 更适合：
  - 低位或平台整理后的新题材
- 主要失效：
  - 假突破
  - 缩量无跟随

### `TM302_low_vol_quality_filter`

- 来源参考：
  - `Trading/strategy_line_guide.md` 中的低波修复逻辑
  - `TradingMain/docs/STRATEGY_LINE_DESIGN.md` 中低波/质量方向
- 核心行为：
  - 用低波与流动性过滤极端噪音
- 在新系统中的角色：
  - 风险过滤器
- 更适合：
  - 震荡环境
  - 追求更稳的候选池
- 主要失效：
  - 纯投机爆发行情里滞后

## 3.5 盘中时机组

### `TM401_gap_open_anchor`

- 来源参考：
  - `Trading/run_buy_timing_01_gap_filter.py`
  - `Trading/run_buy_timing_02_open_anchor.py`
- 核心行为：
  - 跳空后的可做性判断
  - 开盘锚点过滤
- 在新系统中的角色：
  - 入场时机模块
- 更适合：
  - 有明确消息催化的次日
- 主要失效：
  - 高开低走
  - 消息兑现即见顶

### `TM402_vwap_range_intraday_confirmation`

- 来源参考：
  - `Trading/run_buy_timing_05_vwap_anchor.py`
  - `Trading/run_buy_timing_06_range_position.py`
  - `TradingMain/research/tools/strategy_intraday_minute.py`
- 核心行为：
  - VWAP 锚定
  - 日内区间位置判断
- 在新系统中的角色：
  - 盘中确认器
- 更适合：
  - 你有盯盘时间
  - 当天要做更精细入场
- 主要失效：
  - 过度精细化
  - 对执行要求高

## 3.6 市场状态组

### `TM501_market_state_dynamic`

- 来源参考：
  - `Trading/projects/style_timing`
  - `Trading/run_environment_policy_search_first_pass.py`
  - `TradingMain/research/tools/strategy_market_state_dynamic.py`
- 核心行为：
  - 根据市场宽度、风格和成交环境切换打法
- 在新系统中的角色：
  - 环境过滤核心模块
- 更适合：
  - 所有技术模块上层
- 主要失效：
  - 状态滞后
  - 切换过于频繁

## 3.7 资金拥挤与资本结构组

### `TM601_capital_flow_overlay`

- 来源参考：
  - `Trading/run_top_n_comparison_analysis.py`
  - `TradingMain/research/tools/strategy_capital_flow_family.py`
  - `TradingMain/research/CURRENT_INDEX.md` 中的 `ov302_line_a_anti_margin_crowding_h20_top6`
- 核心行为：
  - 资金拥挤识别
  - 量价与交易热度叠加过滤
- 在新系统中的角色：
  - 候选排序修正器
- 更适合：
  - 强趋势但需要防止过热追高
- 主要失效：
  - 错杀真正主升龙头

## 4. 旧项目到新系统的映射方法

新系统不迁移“旧策略名”，而迁移为三层资产：

### 4.1 候选生成器

- `TM001`
- `TM101`
- `TM201`
- `TM301`

### 4.2 技术确认器

- `TM002`
- `TM401`
- `TM402`

### 4.3 风险与环境过滤器

- `TM102`
- `TM202`
- `TM302`
- `TM501`
- `TM601`

## 5. 在交易助手中的位置

这些技术模块不会直接给最终买卖指令，而会进入 `candidate_card` 的技术字段：

- `technical_state`
- `candidate_source`
- `market_fit_score`
- `disqualify_flags`
- `candidate_rationale`

然后再与：

- `event_card`
- `theme_card`
- `capital_behavior_card`
- `account_constraints`

一起融合成 `trade_plan_card`。

## 6. 当前结论

旧项目里最值得保留的是：

- 趋势延续
- 修复反弹
- 群组轮动
- 波动压缩
- 盘中时机
- 市场状态
- 资金拥挤过滤

这些已经足够构成新系统的技术分析底座。
