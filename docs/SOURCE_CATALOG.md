# Source Catalog

## 1. 说明

本文件是在 `INFORMATION_SOURCE_DESIGN.md` 基础上的进一步细化。

这里不直接绑定某一个外部供应商，而是先定义“来源家族”。  
后续无论接交易所原文、数据接口、爬虫还是人工输入，都必须先落到这里的某个来源家族中。

## 2. 来源家族总览

### 2.1 A 类：核心来源家族

#### `market_equity_daily`

- 类别：A
- 作用：个股基础行情、技术状态、候选生成底座
- 典型内容：
  - 开高低收
  - 成交量
  - 成交额
  - 换手率
  - 涨跌幅
  - 量比
- 主要服务：
  - 候选池生成
  - 市场结构判断
  - 个股状态摘要

#### `market_index_daily`

- 类别：A
- 作用：指数环境、风格判断、市场风险偏好
- 典型内容：
  - 大盘指数
  - 中小盘风格指数
  - 行业指数
  - 主题指数
- 主要服务：
  - 市场环境判断
  - 主风格切换识别

#### `market_breadth_and_limit_structure`

- 类别：A
- 作用：识别情绪强弱、题材温度、可交易性
- 典型内容：
  - 涨跌家数
  - 涨停数、跌停数
  - 炸板率
  - 连板高度
  - 市场总成交额
  - 分风格成交热度
- 主要服务：
  - `market_regime_snapshot`
  - 是否适合开仓
  - 是否适合追强或防守

#### `exchange_filings`

- 类别：A
- 作用：正式公司事件主入口
- 典型内容：
  - 业绩预告
  - 增减持
  - 回购
  - 解禁
  - 重组并购
  - 停复牌
  - 处罚/立案/监管函
- 主要服务：
  - `event_cards`
  - 风险排雷
  - 催化识别

#### `company_announcements_structured`

- 类别：A
- 作用：对正式公告做结构化抽取
- 典型内容：
  - 公告标题
  - 公告类型
  - 发布时间
  - 关联股票
  - 核心数值
- 主要服务：
  - 事件归类
  - 事件强度提取
  - LLM 摘要输入

#### `policy_primary_documents`

- 类别：A
- 作用：政策原文和正式政策信号
- 典型内容：
  - 部委政策
  - 地方扶持政策
  - 监管规则变动
  - 行业专项通知
- 主要服务：
  - `theme_cards`
  - 中期主线识别
  - 受益链条映射

#### `industry_catalyst_calendar`

- 类别：A
- 作用：产业事件和行业催化日历
- 典型内容：
  - 行业会议
  - 展会
  - 新品发布
  - 技术节点
  - 产业里程碑
- 主要服务：
  - 主线确认
  - 题材持续性判断

#### `dragon_tiger_board`

- 类别：A
- 作用：资金行为和游资/机构痕迹
- 典型内容：
  - 龙虎榜上榜原因
  - 买卖席位
  - 净买入/净卖出
  - 重复活跃席位
- 主要服务：
  - `capital_behavior_cards`
  - 强势股承接判断
  - 题材真伪判断

#### `northbound_and_margin_flow`

- 类别：A
- 作用：中短线资金风险偏好参考
- 典型内容：
  - 北向净流入流出
  - 两融余额变化
  - 两融个股变化
- 主要服务：
  - 市场环境
  - 个股承接辅助判断

#### `block_trade_and_abnormal_volume`

- 类别：A
- 作用：辅助识别大资金行为与异常交易
- 典型内容：
  - 大宗交易
  - 异常放量
  - 异常换手
- 主要服务：
  - 资金行为判断
  - 风险提示

#### `equity_reference_master`

- 类别：A
- 作用：股票、行业、概念、指数成分映射底表
- 典型内容：
  - 股票基础资料
  - 行业归属
  - 概念归属
  - 上市日期
  - 市值分类
- 主要服务：
  - 主题映射
  - 候选池扩散
  - 行业聚类

#### `account_constraints`

- 类别：A
- 作用：把建议绑定到你的真实账户
- 典型内容：
  - 总资金
  - 单票上限
  - 持仓数上限
  - 最大回撤容忍
  - 风格偏好
  - 可盯盘时间
- 主要服务：
  - `trade_plan_cards`
  - 仓位与退出建议

### 2.2 B 类：扩展来源家族

#### `financial_news_wire`

- 类别：B
- 作用：更快发现热点与扩散
- 风险：
  - 重复转载
  - 噪音高
  - 标题误导
- 主要服务：
  - 事件补充
  - 主线早期感知

#### `mainstream_finance_media_analysis`

- 类别：B
- 作用：辅助理解市场解释框架
- 风险：
  - 观点不一
  - 有时滞
- 主要服务：
  - LLM 解释输入
  - 主题背景补全

#### `sell_side_research_reports`

- 类别：B
- 作用：理解产业逻辑、盈利预期、机构偏好
- 风险：
  - 不易完整回放
  - 时效性差异大
- 主要服务：
  - 中期逻辑补强
  - 非日频交易辅助

#### `fundamental_deep_tables`

- 类别：B
- 作用：更细的估值、盈利和财务质量判断
- 风险：
  - 对短线交易帮助未必直接
- 主要服务：
  - 中期择股
  - 风险筛除

#### `intraday_microstructure`

- 类别：B
- 作用：辅助更精细的进场时机
- 风险：
  - 容易过度复杂化
  - 对人工执行要求高
- 主要服务：
  - 盘中确认
  - 择时微调

#### `manual_market_notes`

- 类别：B
- 作用：记录交易者主观观察
- 内容包括：
  - 今日主线感受
  - 不适合系统自动抓取的细节
  - 临场观察
- 主要服务：
  - 经验记忆层
  - 决策复盘

## 3. 来源家族与输出对象映射

| 来源家族 | 输出对象 |
|---|---|
| `market_equity_daily` | `candidate_pool`, `market_regime_snapshot` |
| `market_index_daily` | `market_regime_snapshot` |
| `market_breadth_and_limit_structure` | `market_regime_snapshot` |
| `exchange_filings` | `event_cards` |
| `company_announcements_structured` | `event_cards` |
| `policy_primary_documents` | `theme_cards` |
| `industry_catalyst_calendar` | `theme_cards` |
| `dragon_tiger_board` | `capital_behavior_cards` |
| `northbound_and_margin_flow` | `capital_behavior_cards`, `market_regime_snapshot` |
| `block_trade_and_abnormal_volume` | `capital_behavior_cards` |
| `equity_reference_master` | `candidate_pool`, `theme_cards` |
| `account_constraints` | `trade_plan_cards` |
| `financial_news_wire` | `event_cards`, `theme_cards` |
| `mainstream_finance_media_analysis` | `theme_cards` |
| `sell_side_research_reports` | `theme_cards`, `candidate_pool` |
| `fundamental_deep_tables` | `candidate_pool` |
| `intraday_microstructure` | `trade_plan_cards` |
| `manual_market_notes` | `trade_plan_cards`, `memory` |

## 4. 第一版接入顺序

建议的具体接入顺序：

1. `market_equity_daily`
2. `market_index_daily`
3. `market_breadth_and_limit_structure`
4. `equity_reference_master`
5. `exchange_filings`
6. `company_announcements_structured`
7. `policy_primary_documents`
8. `industry_catalyst_calendar`
9. `dragon_tiger_board`
10. `northbound_and_margin_flow`
11. `block_trade_and_abnormal_volume`
12. `account_constraints`
13. `financial_news_wire`
14. `mainstream_finance_media_analysis`
15. `manual_market_notes`
16. `sell_side_research_reports`
17. `fundamental_deep_tables`
18. `intraday_microstructure`

## 5. 当前结论

如果只从交易实用性出发，最核心的闭环是：

- 市场结构
- 正式公告事件
- 政策催化
- 资金行为
- 基础映射
- 账户约束

如果这六块没建好，堆更多新闻和研究报告不会真正提升系统质量。
