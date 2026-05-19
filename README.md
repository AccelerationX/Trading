# TradingSystem

面向 A 股个人交易者的人机协同盘前分析与交易决策系统。

这个项目的目标不是做“全自动下单黑盒”，而是把市场环境、技术信号、事件驱动、政策信息、国内财经快讯、账户约束、LLM 深化分析、持仓管理和交易复盘串成一条可日常运行的实盘辅助链路。

当前版本已经支持：

- 一键更新数据、抓取信息并完成整条盘前分析流水线
- 输出可直接执行的交易指令单
- 按真实账户约束生成买卖建议
- 自动生成系统交易记录与默认执行持仓
- 根据真实成交回填结果，对 setup 胜率、执行质量和后续阈值做反馈修正

## 项目定位

这不是：

- 自动下单交易程序
- 高频量化系统
- 只会打分的选股脚本

这是：

- 面向小资金、高收益目标的盘前交易辅助系统
- 以“少做、做强、可解释”为核心的决策系统
- 可以持续记录、复盘、修正自己建议质量的实用型项目

## 当前能力

系统当前已经具备以下主能力：

- 市场状态判断
  - 指数趋势
  - 风格强弱
  - 情绪压力
  - 投机热度
  - 突破失败率
- 候选股生成
  - 技术模块扫描
  - 事件/题材驱动
  - 国内公开快讯与政策文本
  - 资金行为辅助解释
- 决策融合
  - `市场许可 -> setup 分类 -> 个股驱动 -> 技术确认 -> 账户适配 -> 动作生成`
- 交易计划
  - 买什么
  - 买多少股
  - 参考买入区间
  - 止损/止盈
  - 建议持有天数
  - 卖出建议
- 小资金账户适配
  - 主板过滤
  - 一手成本约束
  - 仓位集中度控制
  - setup 曝露控制
- LLM 增强
  - 核心决策任务优先云端
  - 批量辅助任务优先本地
  - 重试、fallback、模式化限流
- 真实执行反馈
  - 自动写入系统交易日志
  - 自动同步默认执行持仓
  - 回填真实成交后反向修正 setup 阈值和仓位上限

## 系统主链

当前日常主链大致如下：

1. 刷新账户与持仓状态
2. 抓取最新可得行情和文本信息
3. 生成市场环境、事件卡、题材卡、候选卡
4. 做 setup 分类与市场硬门控
5. 生成交易计划
6. 生成最终交易指令单
7. 将建议自动写入：
   - `workspace/portfolio/current_holdings.json`
   - `workspace/portfolio/system_trade_log.json`
8. 交易后回填真实成交
9. 根据真实执行结果生成学习反馈并影响后续建议

## 目录结构

```text
TradingSystem/
├─ configs/                        配置与注册表
├─ docs/                           设计文档与使用文档
├─ data/                           输入数据、缓存与处理层
├─ outputs/                        运行输出（已忽略，不进 Git）
├─ prompts/                        LLM 提示词
├─ research/                       研究脚本与实验材料
├─ scripts/                        可直接运行的脚本入口
├─ src/trading_system/             核心源代码
├─ tests/                          测试
├─ workspace/                      工作区、模板与本地运行态
├─ run_preopen_oneclick.bat        一键盘前运行入口
└─ README.md
```

## 关键入口

日常最重要的入口：

- `run_preopen_oneclick.bat`

主要脚本入口：

- `scripts/run_assistant_pipeline.py`
- `scripts/run_refresh_live_state.py`
- `scripts/run_system_selfcheck.py`
- `scripts/run_build_execution_feedback.py`
- `scripts/run_build_execution_behavior.py`

重要产物：

- `outputs/trade_execution/trade_execution_<trade_date>.md`
- `outputs/preopen/preopen_summary_<trade_date>.md`
- `workspace/portfolio/system_trade_log.json`
- `workspace/portfolio/current_holdings.json`

## 一键运行方式

双击：

```bat
run_preopen_oneclick.bat
```

默认行为：

1. 读取 `.env`
2. 刷新 live account / holdings 状态
3. 拉取最新可得行情与文本信息
4. 运行完整 assistant pipeline
5. 生成最终交易指令单
6. 自动写入默认执行的持仓与系统交易日志
7. 生成执行反馈与执行行为反馈

也可以手动指定：

```bat
run_preopen_oneclick.bat 2026-05-19 stable
run_preopen_oneclick.bat 2026-05-19 full
```

参数含义：

- 第一个参数：可选交易日期
- 第二个参数：`llm-mode`，默认 `stable`
- 第三个参数：可选 `llm-limit`

## 日常使用流程

现在推荐的实盘试运行流程非常简单：

1. 双击 `run_preopen_oneclick.bat`
2. 打开最新的 `outputs/trade_execution/trade_execution_<trade_date>.md`
3. 按建议手工交易
4. 交易后回填 `workspace/portfolio/system_trade_log.json`

正常情况下，你只需要回填 `system_trade_log.json` 里每条记录的：

- `fill_form.execution_status`
- `fill_form.actual_shares`
- `fill_form.actual_price`
- `fill_form.fill_note`

如果遇到未成交、部分成交、取消等特例，再修正：

- `workspace/portfolio/current_holdings.json`

详细说明见：

- [docs/ONE_CLICK_DAILY_RUN.md](docs/ONE_CLICK_DAILY_RUN.md)
- [docs/LIVE_ACCOUNT_WORKFLOW.md](docs/LIVE_ACCOUNT_WORKFLOW.md)

## 账户与持仓

当前系统已经按“小资金、高收益、主板-only”思路接入账户约束。

账户约束文件位于：

- `data/inbox/account_constraints/live_personal_account.json`

运行态持仓文件位于：

- `workspace/portfolio/current_holdings.json`

系统交易日志位于：

- `workspace/portfolio/system_trade_log.json`

当前默认工作方式是：

- 系统生成建议后，默认视为将执行
- 自动把建议写入持仓和交易日志
- 你在交易后回填真实成交结果
- 后续学习反馈以此为基础修正 setup policy

## LLM 使用策略

日常默认模式是 `stable`。

当前采用“核心云端 + 批量本地”的混合路由：

- 云端优先：
  - `candidate_diagnosis_agent`
  - `trade_plan_refine_agent`
- 本地优先：
  - `event_deepening_agent`
  - `theme_deepening_agent`
  - `capital_interpret_agent`
  - `review_memory_agent`

这样做的目的：

- 保住最终交易建议质量
- 控制云端成本
- 保持日常稳定可跑

如果云端失败，系统会按 provider 注册表进行重试和回退。

相关文档：

- [docs/LLM_PROVIDER_RUNTIME.md](docs/LLM_PROVIDER_RUNTIME.md)
- [docs/LLM_EXECUTION_PLAN.md](docs/LLM_EXECUTION_PLAN.md)

## 学习反馈机制

系统当前已经不是静态分析器，而是具备基础学习闭环：

- `setup_performance`
  - 看理论 forward return
- `execution_feedback`
  - 看真实成交后的实际盈亏表现
- `execution_behavior`
  - 看真实可执行性，例如成交率、跳过率、部分成交率、滑点

这些结果会共同影响后续：

- setup 状态：`favored / neutral / cautious / disabled`
- 候选分数倍率
- 动作阈值
- 仓位上限

也就是说，系统会逐步根据你的真实执行结果，而不是只根据理论行情表现修正自己。

## 数据源说明

当前版本主要依赖：

- Tushare 行情与结构化市场数据
- 国内公开政策与官方文本源
- 国内公开财经快讯抓取
  - 财联社
  - 东方财富
  - 其他已接入公开源

系统已支持严格市场日期校验：

- 当请求日期为非交易日时，会自动映射到最近开市日
- 如果核心市场数据没有刷新到最近开市日，严格模式下会直接失败，而不是静默吃旧数据

## 环境准备

建议使用：

- Python 3.10+
- Windows PowerShell / CMD
- 本地可用的 Ollama 或其他本地模型服务
- 可选的云端 LLM API Key

`.env` 中通常会包含：

- `TUSHARE_TOKEN`
- `MOONSHOT_API_KEY`
- 其他云端 provider 所需字段

注意：

- `.env`
- `outputs/`
- `data/processed/`
- 绝大部分本地缓存和运行态文件

都不会提交到 GitHub。

## 测试

运行全量测试：

```powershell
python -m pytest
```

当前仓库已包含较完整的测试覆盖，覆盖：

- pipeline 主链
- 市场状态与候选生成
- 交易计划
- LLM runtime
- 持仓同步
- 执行反馈与 setup policy

## 当前边界

当前版本已经适合进入实盘试运行，但仍有边界：

- 不是自动下单系统
- 不保证单次交易高胜率
- 国际付费新闻源目前未作为核心依赖
- 真实学习反馈刚建立，效果依赖持续使用和样本积累

最适合的使用方式是：

- 每天稳定运行
- 只做系统给出的少数高质量建议
- 认真回填真实成交
- 让系统在真实交易中逐步修正自己

## 推荐阅读顺序

如果你第一次进入项目，建议按这个顺序看：

1. [docs/ONE_CLICK_DAILY_RUN.md](docs/ONE_CLICK_DAILY_RUN.md)
2. [docs/LIVE_ACCOUNT_WORKFLOW.md](docs/LIVE_ACCOUNT_WORKFLOW.md)
3. [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md)
4. [docs/SYSTEM_OPTIMIZATION_BLUEPRINT.md](docs/SYSTEM_OPTIMIZATION_BLUEPRINT.md)
5. [docs/ASSISTANT_PIPELINE.md](docs/ASSISTANT_PIPELINE.md)

## 免责声明

本项目用于研究、盘前分析和人工辅助决策，不构成任何投资承诺。所有交易行为仍需由使用者自行判断并承担风险。
