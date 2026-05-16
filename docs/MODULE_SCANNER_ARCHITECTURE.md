# Module Scanner Architecture

## 1. 设计目标

将技术模块从"被动标签"升级为"主动候选源"。每个被 `recommend_modules_for_regime` 推荐的模块，必须能独立扫描当日市场，产出标准化的信号列表。最终候选池由 **事件源 + 主题源 + 技术模块源** 三方合并生成。

## 2. 核心原则

1. **接口统一，实现解耦**：所有模块对外暴露同一个 `ModuleScanner` 接口，内部实现可以千差万别
2. **旧代码核心算法复用**：直接复制旧项目（`Trading` / `TradingMain`）的核心扫描逻辑到本项目中，去掉回测、交易模板、加权计划等与"候选生成"无关的逻辑
3. **数据层适配**：旧代码的数据读取层（`quant_research.pipeline`）不直接复制，而是提取核心算法为"纯函数"（输入 DataFrame，输出信号列表），数据准备由 scanner 使用 TradingSystem 现有数据源组装
4. **独立可测试**：每个 scanner 可以单独运行、单独验证
5. **向后兼容**：现有 `event_cards` 和 `theme_cards` 的候选生成逻辑保留，模块信号作为增量来源叠加
6. **主板优先**：所有 scanner 默认只扫描主板股票（符合账户约束）

## 3. 新增数据契约

### 3.1 ModuleSignal

```python
@dataclass(frozen=True)
class ModuleSignal:
    module_id: str              # 产生信号的模块ID
    stock_code: str             # 股票代码
    trade_date: str
    signal_type: str            # "strong", "moderate", "watch", "avoid"
    strength: float             # 0.0 ~ 1.0，模块内部原始分数归一化
    technical_state: str        # 模块视角下的技术状态描述
    confidence: float           # 0.0 ~ 1.0，数据完整度
    metadata: dict              # 模块特有数据（如 trend_slope, repair_score）
    invalidation_hint: str      # 什么条件下这个信号失效
    source_refs: list[str]      # 数据来源引用
```

与 `CandidateCard` 的关系：
- `ModuleSignal` 是**单一模块视角**的原始信号
- `CandidateCard` 是**系统融合后**的决策对象
- 一个 `CandidateCard` 可以被多个 `ModuleSignal` 支撑

### 3.2 主板股票定义

```python
MAIN_BOARD_PATTERNS = [
    re.compile(r'^(600|601|603|605)\d{3}\.SH$'),
    re.compile(r'^(000|001|002|003)\d{3}\.SZ$'),
]
```

## 4. 模块扫描器接口

```python
# src/trading_system/signal/scanners/base.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class ModuleScanner(Protocol):
    @property
    def module_id(self) -> str: ...
    
    def is_available(self, trade_date: str) -> bool:
        """检查该模块今天能否运行（所需数据是否到位）"""
        ...
    
    def scan(self, trade_date: str, 
             market_regime: MarketRegimeSnapshot,
             account: AccountConstraints | None = None,
             universe: list[str] | None = None) -> list[ModuleSignal]:
        """扫描当日市场，返回信号列表"""
        ...
```

## 5. 三类实现策略

### A类：内部实现（逻辑简单、数据已在本系统）

| 模块 | 实现思路 |
|------|----------|
| **TM501** market_state_dynamic | 不是选股，而是环境过滤。scanner 返回"全市场通过/不通过"信号，或根据 regime 动态调整其他 scanner 的参数 |
| **TM302** low_vol_quality_filter | 计算近20日波动率、换手率、流动性，过滤低质量票 |

### B类：旧代码核心算法复用（重点）

旧项目有大量可运行的研究脚本。我们不搬移整个回测框架，而是：

1. **复制核心算法文件**到 `src/trading_system/signal/legacy/`
2. **剥离数据层**：把原来自己读 `StockHistory/*.csv` 的逻辑，改为接受传入的 `pd.DataFrame`
3. **剥离回测层**：只保留"当日扫描、排序、筛选"逻辑
4. **包装为 scanner**：在 `src/trading_system/signal/scanners/` 下写 adapter

**旧代码复制清单（以 TM001 试点为例）**：

```
src/trading_system/signal/legacy/
├── __init__.py
├── line_a_core.py          # 从 run_line_a_simulation_pack.py 提取
├── line_a_factors.py       # 从 quant_research.pipeline + run_tech_factor_round2 提取
└── main_board_filter.py    # 从 run_main_board_strategy_validation.py 提取
```

**数据适配策略**：

旧代码依赖的字段 vs TradingSystem 现有数据：

| 旧字段 | 来源 | 本系统状态 | 适配方案 |
|--------|------|-----------|----------|
| stock_code, trade_date, open, high, low, close, prev_close, volume, amount, turnover_pct | `market_equity_daily` | ✅ 已有 | 直接映射 |
| total_mkt_cap_10k, float_mkt_cap_10k | `market_equity_daily` total_mv/circ_mv | ✅ 近似 | 字段映射 |
| limit_up, limit_down | `market_equity_daily` limit_up_price/limit_down_price | ✅ 已有 | 字段映射 |
| stock_name | 无 | ❌ 缺失 | 从 `equity_reference_master` 补充 |
| pe_ttm, pb | 无 | ❌ 缺失 | **Phase 1 简化版暂不使用**；Phase 2 从 Tushare `daily_basic` 补充 |
| bp (1/pb), ep_ttm (1/pe_ttm) | 依赖 pe_ttm, pb | ❌ 缺失 | Phase 1 用 proxy（如用 circ_mv 近似 size，用 turnover_pct 近似 liquidity） |

**Phase 1 简化版 TM001 算法**：

旧版 `core_combo_alpha` = `bp + short_reversal_5 + size + liquidity`（等权组合）

Phase 1 简化版：
- 用 `short_reversal_5`（5日反转，可直接从 close 计算）
- 用 `size_proxy` = `log(circ_mv)` 替代 size
- 用 `liquidity_proxy` = `log(amount)` 替代 liquidity
- `bp` 暂时用 `1.0` 作为中性占位（等 Tushare 补充 pb 后再启用）
- 组合方式保持等权

这个简化版不是最终目标，但能让 scanner 立即跑起来，验证接口和数据流是否正确。

### C类：外部数据依赖型（需要额外数据源）

| 模块 | 额外数据需求 |
|------|-------------|
| **TM601** capital_flow_overlay | 龙虎榜、资金流向数据（本系统已有 `northbound_and_margin_flow`, `dragon_tiger_board`） |
| **TM401/TM402** 日内时机 | 需要 intraday 1分钟数据 |

## 6. 候选合并架构

### 6.1 新流程

```text
┌─────────────────┐
│  event_cards    │──┐
│  theme_cards    │──┼──→ 事件/主题候选生成（保留现有逻辑）
└─────────────────┘  │
                     │
┌─────────────────┐  │     ┌─────────────────────┐
│ recommend_modules│──┘     │                     │
│ _for_regime()   │────────→│  对每个推荐模块      │
└─────────────────┘         │  调用 scanner.scan() │
                            │                     │
                            └──────────┬──────────┘
                                       │
                            ┌──────────▼──────────┐
                            │   ModuleSignal[]    │
                            │   按 stock_code 聚合 │
                            └──────────┬──────────┘
                                       │
                            ┌──────────▼──────────────┐
                            │  三方候选合并            │
                            │  1. 去重（stock_code）   │
                            │  2. 信号聚合             │
                            │  3. 统一评分             │
                            └──────────┬──────────────┘
                                       │
                            ┌──────────▼──────────┐
                            │   CandidateCard[]   │
                            └─────────────────────┘
```

### 6.2 合并规则

**去重与信号聚合**：

```python
def aggregate_module_signals(signals: list[ModuleSignal]) -> dict[str, list[ModuleSignal]]:
    """按 stock_code 分组"""
    ...

def merge_signals_for_stock(signals: list[ModuleSignal]) -> dict:
    """
    合并同一支票的多个模块信号：
    - active_module_ids: 所有支持的模块
    - best_strength: 最高 strength
    - avg_strength: 加权平均（按 confidence 加权）
    - has_avoid: 是否有 avoid 信号
    - technical_state: 组合描述（如 "line_a_trend_intact + breakout_watch"）
    """
    ...
```

**候选来源标注扩展**：

`CandidateCard.candidate_source` 扩展为：
- `module_direct` — 纯模块选出，无事件/主题支撑
- `module_event_resonance` — 模块 + 事件双重支撑
- `module_theme_resonance` — 模块 + 主题双重支撑
- `full_resonance` — 模块 + 事件 + 主题三重支撑
- 保留原有的 `event_direct`, `event_theme_resonance`, `theme_priority`

### 6.3 评分权重调整

现有权重：
- event: 0.35, theme: 0.2, market: 0.2, account: 0.15, capital: 0.1, text: 0.08

新权重（模块作为独立维度）：

```python
weights = {
    "event": 0.22,        # 下调，因为模块信号将分担选股职责
    "theme": 0.13,        # 下调
    "module": 0.25,       # 新增核心维度
    "market": 0.15,       # 下调
    "account": 0.10,      # 下调
}
# capital 和 text 保持 0.1 和 0.08，作为 bonus 不占总权重分母
```

模块分数计算：

```python
def _module_score(signals: list[ModuleSignal]) -> float:
    if not signals:
        return 0.25  # 无模块支持，基础分偏低
    
    best = max(s.strength for s in signals)
    avg = sum(s.strength * s.confidence for s in signals) / sum(s.confidence for s in signals)
    has_avoid = any(s.signal_type == "avoid" for s in signals)
    has_strong = any(s.signal_type == "strong" for s in signals)
    
    score = 0.35 + best * 0.30 + avg * 0.20
    if has_strong:
        score += 0.08
    if has_avoid:
        score -= 0.25
    return clamp(score)
```

**设计理由**：
- 用户核心诉求是"高收益率推荐"
- 量化模块是直接产生候选的引擎，应给予较高权重（0.25）
- 事件/主题权重下调，但保留重要地位，因为政策/公告类 alpha 在 A 股不可忽视
- 市场环境和账户约束权重下调，因为它们更多是"过滤"而非"生成"

## 7. 主板过滤整合

### 7.1 账户约束层

```python
# AccountConstraints 新增字段
main_board_only: bool = True
```

### 7.2 候选生成层

在 `build_candidate_cards` 中，对 `candidate_universe` 做主板过滤：

```python
def _is_main_board(code: str) -> bool:
    return any(pattern.match(code) for pattern in MAIN_BOARD_PATTERNS)

# 在 build_candidate_cards 中
candidate_universe = sorted(set(event_map) | set(theme_map))
if account.main_board_only:
    candidate_universe = [code for code in candidate_universe if _is_main_board(code)]
```

### 7.3 模块扫描层

每个 scanner 的 `scan()` 方法内部，默认只扫描主板：

```python
def scan(self, trade_date, market_regime, account=None, universe=None):
    if universe is None:
        universe = self._load_universe(trade_date)
    if account and account.main_board_only:
        universe = [code for code in universe if _is_main_board(code)]
    # ... 继续扫描
```

### 7.4 交易计划层

在 `build_trade_plan_cards` 中，最后再做一次主板过滤（防御性编程）：

```python
if account.main_board_only:
    plans = [p for p in plans if _is_main_board(p.stock_code)]
```

## 8. 配置扩展

`technical_module_registry.json` 增加 `scanner` 配置段：

```json
{
  "module_id": "TM001_line_a_trend_continuation",
  "family": "trend_continuation",
  "role": "candidate_generator",
  "priority": "core",
  "market_regimes": ["risk_on", "selective"],
  "style_bias": ["main_board", "large_mid_cap"],
  "needs_intraday": false,
  "scanner": {
    "enabled": true,
    "backend": "legacy_adapted",
    "legacy_module": "line_a_core",
    "config": {
      "strategy": "double_q60_top10",
      "top_n": 6,
      "keep_rank": 8,
      "rebalance_step": 10
    }
  }
}
```

`backend` 可选值：
- `"disabled"` — 不启用（默认，向后兼容）
- `"internal"` — 本项目内部实现
- `"legacy_adapted"` — 复用旧代码核心算法

## 9. 目录结构

```
src/trading_system/signal/
├── __init__.py
├── technical_modules.py              # 现有：模块定义与推荐逻辑
├── scanners/
│   ├── __init__.py
│   ├── base.py                        # ModuleSignal + ModuleScanner 协议
│   ├── registry.py                    # scanner 注册与发现
│   ├── merging.py                     # 信号聚合与候选合并
│   ├── internal/
│   │   ├── __init__.py
│   │   ├── tm501_market_state.py      # TM501 内部实现
│   │   └── tm302_low_vol_filter.py    # TM302 内部实现
│   └── legacy_adapted/
│       ├── __init__.py
│       ├── tm001_line_a.py            # TM001 adapter
│       ├── tm002_breakout.py          # TM002 adapter
│       └── ...
└── legacy/                            # 旧代码核心算法（纯函数，无IO）
    ├── __init__.py
    ├── main_board_filter.py
    ├── line_a_core.py
    └── line_a_factors.py
```

## 10. 分阶段实施计划

### Phase 1：基础设施 + 账户约束修正（2-3 天）

1. 修正 `AccountConstraints`：资金 4.3 万，增加 `main_board_only`
2. 修正候选/交易计划生成：增加主板过滤
3. 定义 `ModuleSignal`、`ModuleScanner` 协议
4. 实现 scanner 注册表
5. 实现 `FileBackedScanner` 基类（为后续扩展预留）
6. 写测试：协议契约、注册表、主板过滤

### Phase 2：TM001 试点（3-5 天）

1. 复制旧代码核心算法到 `signal/legacy/`
2. 剥离数据层：改为接受 DataFrame 输入
3. 实现简化版因子（Phase 1 不用 pe/pb）
4. 写 `TM001Scanner`，包装 legacy 算法
5. 修改 `build_candidate_cards`，接入 module 信号
6. 调整评分权重
7. 跑完整流水线，观察候选池变化
8. 写测试：TM001 scanner 独立测试、合并逻辑测试

### Phase 3：逐个模块接入（1-2 周，逐个来）

每接入一个模块：
1. 复制/改造旧代码核心算法
2. 写 adapter scanner
3. 跑一次完整流水线
4. 观察候选池变化和质量
5. 调整参数

接入顺序建议：
1. TM001（趋势延续）— 最成熟
2. TM002（突破确认）— 与 TM001 互补
3. TM101（修复反弹）— selective 市场有价值
4. TM201（板块轮动）— 需要行业数据
5. TM601（资金流 overlay）— 本系统已有资金流数据

### Phase 4：评分调优与迭代（持续）

1. 收集 1-2 周运行数据
2. 分析各模块信号的命中率
3. 调整 `module` 权重和各模块内部参数
4. 目标：`full_resonance`（模块+事件+主题）候选排在最前面

## 11. 预期收益

| 维度 | 现在 | 改进后 |
|------|------|--------|
| 候选来源 | 仅事件/主题（回购、增持） | 事件 + 主题 + 12 条量化策略线 |
| 技术模块 | 纯标签，不选股 | 真正扫描市场产出信号 |
| candidate_score | event 主导（35%） | 模块+event+theme 三足鼎立 |
| 交易计划同质化 | 高度雷同 | 不同模块有不同 technical_state 和 invalidation_hint |
| 账户适配 | 通用模板 | 仅主板、4.3万资金真实映射 |
| 可解释性 | "因为有关联事件" | "TM001 趋势完好 + TM002 突破确认" |
