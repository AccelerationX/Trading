# Assistant Pipeline

## 1. 目标

本文件描述交易助手的最小分析流水线。

当前已经可以生成的对象包括：

- `market_regime_snapshot`
- `event_card`
- `theme_card`
- `account_constraints`
- `technical_module_recommendation`

下一层的目标不是立刻给出最终买卖建议，而是先把这些对象装配成一个统一的分析上下文包，供后续：

- LLM 深度分析
- 候选股票生成
- 交易建议起草

## 2. 当前流水线

```text
daily intake
-> processed market/account/event/theme objects
-> technical module recommendation
-> assistant analysis bundle
-> later: candidate cards
-> later: trade plan cards
```

## 3. analysis bundle 的作用

`analysis_bundle` 解决的是“对象已经各自生成了，但还没有被整合”的问题。

它会把：

- 当前市场环境
- 当前适合启用的技术模块
- 当前正式事件草稿
- 当前政策/主题草稿
- 当前账户约束

放到一个统一 JSON/Markdown 输出里，供人工和后续 LLM 任务读取。

## 4. 当前仍未完成的层

这一层之后，才会继续做：

- `candidate_card` 生成
- `trade_plan_card` 起草
- 人工执行后回流复盘
