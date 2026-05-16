# Data Contracts

## 1. 目标

本文件定义第一版统一数据契约，确保：

- 不同来源进入系统时字段口径一致
- LLM 输入输出可以结构化
- 决策层不直接处理杂乱原始文本

## 2. 原始记录通用元数据

所有原始记录都应尽量带有以下公共字段：

| 字段 | 说明 |
|---|---|
| `source_record_id` | 原始记录唯一标识 |
| `source_family` | 来源家族 |
| `source_name` | 来源名称 |
| `source_url` | 来源链接或定位信息 |
| `publish_time` | 对外发布时间 |
| `known_time` | 系统获取时间 |
| `market_phase` | `pre_open` / `in_session` / `post_close` / `weekend` |
| `trade_date_scope` | 适用交易日 |
| `trust_level` | `S` / `A` / `B` / `C` |
| `raw_payload_path` | 原始文件存放位置 |

## 3. 原始记录类型

### 3.1 市场行情记录 `market_bar_record`

建议字段：

- `stock_code`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `prev_close`
- `volume`
- `amount`
- `turnover_pct`
- `volume_ratio`
- `limit_up_price`
- `limit_down_price`

### 3.2 指数记录 `index_bar_record`

建议字段：

- `index_code`
- `index_name`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `amount`

### 3.3 市场结构记录 `market_breadth_record`

建议字段：

- `trade_date`
- `up_count`
- `down_count`
- `flat_count`
- `limit_up_count`
- `limit_down_count`
- `broken_limit_up_count`
- `max_board_height`
- `total_turnover`
- `small_cap_turnover`
- `large_cap_turnover`

### 3.4 公告原始记录 `filing_record`

建议字段：

- `stock_code`
- `stock_name`
- `filing_type`
- `title`
- `publish_time`
- `source_url`
- `full_text_path`
- `summary_text`

### 3.5 政策原始记录 `policy_record`

建议字段：

- `policy_id`
- `title`
- `policy_level`
- `issuing_body`
- `publish_time`
- `source_url`
- `full_text_path`
- `summary_text`

### 3.6 资金行为原始记录 `capital_flow_record`

建议字段：

- `stock_code`
- `trade_date`
- `capital_signal_type`
- `net_amount`
- `buy_amount`
- `sell_amount`
- `seat_or_channel`
- `reason`

### 3.7 新闻原始记录 `news_record`

建议字段：

- `news_id`
- `title`
- `publish_time`
- `source_url`
- `source_name`
- `content_text`
- `related_stocks`
- `related_industries`

### 3.8 手工输入记录 `manual_note_record`

建议字段：

- `note_id`
- `note_type`
- `author`
- `created_time`
- `trade_date_scope`
- `content_text`
- `related_stocks`
- `related_themes`

## 4. 结构化中间对象

### 4.1 市场环境快照 `market_regime_snapshot`

目标：

- 提供“今天适不适合交易、适合什么打法”的统一判断对象

建议字段：

- `snapshot_id`
- `trade_date`
- `market_bias`
- `risk_mode`
- `breadth_strength`
- `limit_up_temperature`
- `turnover_regime`
- `style_lead`
- `theme_concentration`
- `opening_risk_note`
- `confidence`
- `supporting_evidence`

### 4.2 事件卡片 `event_card`

目标：

- 把公告、新闻、事件文本转成可供决策层消费的标准对象

建议字段：

- `event_id`
- `event_type`
- `event_title`
- `stock_codes`
- `industry_tags`
- `publish_time`
- `bullish_bearish`
- `impact_horizon`
- `event_strength`
- `novelty_score`
- `is_official`
- `core_claim`
- `risk_flags`
- `source_refs`
- `llm_summary`

### 4.3 主题卡片 `theme_card`

目标：

- 表示某个政策/行业/题材催化对市场的潜在影响

建议字段：

- `theme_id`
- `theme_name`
- `trigger_type`
- `trigger_time`
- `beneficiary_chain`
- `priority_industries`
- `priority_stocks`
- `continuation_guess`
- `market_confirmation_needed`
- `contra_risks`
- `source_refs`
- `llm_summary`

### 4.4 资金行为卡片 `capital_behavior_card`

目标：

- 把龙虎榜、大宗交易、北向和融资行为转成统一的资金信号对象

建议字段：

- `card_id`
- `stock_code`
- `trade_date`
- `capital_signal_type`
- `participation_strength`
- `consistency_score`
- `suspected_style`
- `support_or_distribution`
- `warning_flags`
- `source_refs`
- `llm_summary`

### 4.5 候选股票卡片 `candidate_card`

目标：

- 给决策层提供统一候选对象

建议字段：

- `candidate_id`
- `stock_code`
- `trade_date`
- `candidate_source`
- `technical_state`
- `event_support_score`
- `theme_alignment_score`
- `capital_confirmation_score`
- `market_fit_score`
- `account_fit_score`
- `disqualify_flags`
- `candidate_rationale`

### 4.6 交易计划卡片 `trade_plan_card`

目标：

- 最终给交易者看的建议对象

建议字段：

- `plan_id`
- `trade_date`
- `stock_code`
- `action`
- `priority_rank`
- `rationale`
- `entry_condition`
- `entry_zone`
- `position_size_rule`
- `max_position_pct`
- `add_reduce_rule`
- `invalidation_rule`
- `exit_rule_hint`
- `holding_horizon`
- `risk_notes`
- `supporting_cards`

## 5. 卡片之间的关系

建议的依赖链：

```text
raw source records
-> event_card / theme_card / capital_behavior_card / market_regime_snapshot
-> candidate_card
-> trade_plan_card
```

决策层原则：

- `trade_plan_card` 不应直接引用未结构化原文
- 必须优先依赖上游卡片对象

## 6. 时间污染防护规则

以下字段后续必须重点校验：

- `publish_time`
- `known_time`
- `trade_date`
- `decision_scope`

原则：

- 盘后发布的信息不能直接参与当天盘前建议
- 周末政策可参与下一个交易日判断，但必须保留时点
- 历史复盘时不能使用当时尚未发布的后验摘要

## 7. 第一阶段最低要求

在功能落地前，至少先保证：

- 所有结构化对象都有 `source_refs`
- 所有事件类对象都有 `publish_time`
- 所有建议类对象都有 `invalidation_rule`
- 所有建议类对象都有 `position_size_rule`
