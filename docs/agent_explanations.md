# Multi-Agent Investment Research System — 各 Agent 详细解释

---

## 1. Orchestrator Agent（编排器）

**对应需求：** F-01（意图识别）、F-03（DAG 路由）、F-14（注入防御）

**定位与作用：** Orchestrator 是整个系统的"门卫"和"调度中心"。它接收用户的自然语言查询，在进入任何分析流程之前完成三项关键任务：意图分类、ticker 提取和安全过滤。

**工作流程：** 第一步，系统通过 `detect_language()` 自动检测用户输入的语言（中英文判断逻辑：检测是否包含 ≥2 个 CJK 字符），这个语言标签会被写入 state 并在后续所有 Agent 间传递，确保所有 LLM 输出的语言与用户一致。第二步，`sanitize_user_input()` 执行完整安全管道——包括提示词注入模式检测（匹配 `injection_patterns.py` 中定义的正则规则，如 "Ignore previous instructions"、"You are now a..." 等）、PII 信息检测、长度限制、控制字符剥离。如果检测被拦截，直接返回 `intent: "rejected"` 并记录审计日志，整个流水线终止。第三步，通过 `call_llm_structured()` 调用 DeepSeek LLM 对已清洗的查询进行意图分类，支持的意图包括 `stock_query`（分析个股）、`stock_comparison`（个股比较）、`chitchat`（闲聊）、`out_of_scope`（超出范围，如执行交易操作）。LLM 同时提取 ticker 符号（如 "AAPL"）和公司名称，并说明分类理由。**第四步（新增）**，通过 `classify_exchange()` 自动判断交易所类型（SH/SZ/BJ/HK/US/UNKNOWN），写入 `state["exchange"]`。这个交易所标签会被下游 4 个中国专属 Agent（macro_env/sector/announcement/social_sentiment）读取，用于决定是否跳过 akshare 调用。

**路由决策：** 在 `graph.py` 中，`_route_after_orchestrator` 函数根据 intent 决定走向——`chitchat`、`out_of_scope`、`rejected` 直接跳到 END 节点，`stock_query` 则进入 `dispatch` 节点，触发后续 6 个数据采集节点的并行扇出。

**设计亮点：** 安全过滤放在 LLM 调用之前，是"防御纵深"的第一层。即使输入过滤器漏过了注入攻击，后续每个 Agent 的 system prompt 也做了加固（defense-in-depth）。被拦截的输入会被记录到审计日志（`audit_trail`），供 MLSecOps 审查。

---

## 2. Market Data Agent（市场数据）

**对应需求：** F-04（实时行情）、F-05（技术指标）、F-06（Mock 降级）

**定位与作用：** 这是整个流水线的数据底座，负责通过 yfinance 获取股票的实时价格、历史 OHLCV 数据，并计算经典技术指标。所有下游 Agent（Fundamental、Quant、Momentum、Grid Strategy）都依赖它的输出。

**数据获取流程：** `market_data_node` 是一个极简的薄封装层——它验证 ticker 非空后，委托 `fetch_market_data(ticker)` 从 `providers.py` 获取数据。`providers.py` 使用 yfinance 的 `Ticker.history(period="1y")` 获取一年日线数据，从中提取：当前价格、涨跌幅、成交量、市值、P/E 比率、52 周高低、当日高低。技术指标计算包括：SMA(20/50/200) 简单移动平均线、RSI(14) 相对强弱指标、MACD(12,26,9) 指数平滑异同移动平均线。所有计算使用 pandas 完成，向量化操作效率高。

**Mock 降级机制：** 如果 yfinance API 不可用（网络中断、速率限制、ticker 无效），`providers.py` 会在 3 秒超时内切换到 `mock.py` 中的硬编码模拟数据。Mock 数据标记 `is_mock=True` 和 `data_source="mock"`，下游 Agent 可以据此判断数据质量。这种设计确保即使所有外部数据源都失败，系统也不会崩溃——Advisory Agent 会降低置信度并添加显著警告。

**关键设计：** ticker 通过 `backend/utils/ticker.py` 的 `normalize_for_yfinance()` 进行归一化处理，自动补全交易所后缀（如 600519 → 600519.SS，000858 → 000858.SZ）。返回数据通过 `MarketDataResult` Pydantic 模型验证，确保类型安全。

---

## 3. Macro Environment Agent（宏观环境）

**对应需求：** 扩展的宏观分析需求（v2 新增）

**定位与作用：** 一只股票的技术面看起来超买，但如果整个市场处于强势牛市，SELL 可能是不恰当的。这个 Agent 提供宏观市场背景，让下游 Agent 能够将个股分析放在更大的市场环境中理解。

**交易所路由：** Orchestrator 在 `state["exchange"]` 中标记了交易所类型（SH/SZ/BJ/HK/US）。本 Agent 入口检查：`exchange not in ("SH", "SZ", "BJ")` 时直接跳过 akshare 调用，返回包含 `"overall_regime": "N/A (overseas stock)"` 的空结构。这意味着分析美股 AAPL 时，不会拉取沪深 300 等无关的中国指数数据，下游的 Debate 和 Advisory Agent 会看到空宏观并继续运行，不会将中国市场的判断应用到美股上。

**数据获取：** 通过 akshare 获取中国主要指数的快照数据，包括沪深 300（CSI 300）、上证指数（SSE）、深证成指、创业板指等。对每个指数，获取当前价格、当日涨跌幅、5 日和 20 日收益率。

**市场状态检测（Regime Detection）：** 这是本 Agent 的核心创新。它不使用 LLM 判断市场状态，而是用纯算法逻辑：根据指数的多周期收益率和价格位置，将每个指数的状态归类为 BULL（牛市）、BEAR（熊市）或 SIDEWAYS（震荡）。然后汇总所有指数的状态——如果 BULL 状态指数 ≥ 2 且超过 BEAR 数量，整体判定为 "BULL MARKET"；反之则为 "BEAR MARKET"；否则为 "SIDEWAYS / MIXED"。同时统计多头和空头指数的具体数量，为下游提供量化参考。

**下游影响：** 宏观环境数据被注入到 Debate Agent 的辩论上下文中。Bull 和 Bear 双方在论证时必须考虑当前市场大势——在熊市中推荐 BUY 需要更强的理由，在牛市中 SELL 的判断也需要额外谨慎。这避免了"只见树木不见森林"的个股分析偏差。

---

## 4. Sector Agent（行业板块）

**对应需求：** 行业分析需求（v2 新增）

**定位与作用：** 确定个股所属的行业板块，该板块当日的涨跌情况，以及全市场的热门/冷门板块和概念板块排名。下游 Agent 通过此信息判断这只股票是"乘风而起"还是"逆势下跌"。

**交易所路由：** 与 Macro Environment 相同，检查 `exchange not in ("SH", "SZ", "BJ")` 时跳过所有 akshare 调用。对于美股 AAPL 或港股 0700.HK，返回空板块数据（`summary: "Sector context (A-share industry boards) not applicable for overseas stocks."`），下游不会将 A 股申万行业信息错误地注入到美股分析中。

**数据来源：** 全部通过 akshare 免费获取，无需 API Key。

**三个核心数据流：** 第一，`fetch_sector_ranking()` 获取 A 股行业板块当日涨跌排名，返回每个板块的名称、涨跌幅、上涨/下跌家数。第二，`fetch_concept_ranking()` 获取概念板块排名（如"新能源"、"AI 芯片"等主题概念），反映市场热点资金流向。第三，`fetch_stock_industry()` 根据个股 ticker 查询其所属行业信息。

**匹配逻辑：** 由于 akshare 返回的行业名称可能与个股的行业标签存在命名差异，代码使用模糊匹配——遍历板块排名列表，检查行业名称是否互为子串。匹配成功后记录该板块的排名位置。

**输出结构：** 包含 `stock_industry`（个股行业信息）、`stock_sector_row`（该股所属板块的排名行数据）、`top_sectors`（热门板块 Top5）、`bottom_sectors`（冷门板块）、`top_concepts`（热门概念 Top5），以及一段摘要文本。下游的 Debate Agent 和 Advisory Agent 都会引用这些信息。

---

## 5. News Agent（新闻采集）

**对应需求：** F-07（多源新闻）、F-08（去重与相关性评分）

**定位与作用：** 从多个新闻源采集与目标股票相关的新闻文章，进行去重和相关性排序，为下游的 Sentiment Agent 提供结构化新闻输入。**这是 6 个并行数据采集节点中唯一一个全球通用的 Agent（与 market_data 一起），A 股和海外股票都会执行。**

**多源采集：** `fetch_news(ticker)` 在 `sources.py` 中实现了三源采集：第一数据源是 akshare 东方财富个股新闻（仅 A 股，`symbol.isdigit()` 校验，非 A 股自动返回空）。第二数据源是 yfinance 的 `ticker.news` 接口（全球通用）。第三数据源是 DuckDuckGo Search API（全球通用）。三个数据源的异常各自独立捕获，互不影响。

**去重机制：** 新闻去重基于标题哈希（title-hash dedup）。对每篇文章标题计算哈希值，相同哈希视为重复文章。这比简单的字符串精确匹配更鲁棒，能处理同一新闻在不同来源的标题微小差异。

**相关性排序：** 每篇文章附带 `relevance_score` 字段，按"相关性 × 时效性"综合排序返回。与 ticker 精确匹配的文章获得高相关性，仅提及行业或板块的文章获得低相关性。最终返回 Top 10 最相关文章，每篇包含标题、来源、发布日期、摘要和 URL。

**设计考量：** 这个 Agent 不调用 LLM——它只做数据收集和清洗。真正的语义分析和情感评分由下游的 Sentiment Agent 完成，确保关注点分离。

---

## 6. Announcement Agent（公司公告）

**对应需求：** F-22（公司公告与财报）

**定位与作用：** 获取目标公司的官方公告和财务摘要数据，提供来自中国证监会指定信息披露平台的结构化公司披露信息。

**交易所路由：** 检查 `exchange not in ("SH", "SZ", "BJ")` 时跳过 akshare 调用，返回空公告列表和空财务摘要。美股和港股的公告不在此 Agent 的职责范围内（akshare 的东方财富/同花顺接口仅覆盖 A 股）。下游的 Fundamental Agent 和 Debate Agent 会看到空数据并继续运行。

**数据来源：** 通过 akshare 的多个接口获取。第一，`fetch_announcements()` 从东方财富（Eastmoney）获取公司公告列表，包括公告标题、发布日期、公告类型等。第二，`fetch_financial_summary()` 从同花顺（THS）接口获取财务摘要，包括营业收入（revenue）、净利润（net profit）、ROE、毛利率（gross margin）和资产负债率（debt ratio）等关键财务比率。

**数据处理：** 对于 A 股 ticker（如 600519.SS），需要去除 `.SS` / `.SZ` 后缀转换为 akshare 所需格式。对于港股（.HK），由于 akshare 不支持港股数据接口，函数会优雅返回空列表和空字典，不引发异常。新上市股票可能财务历史有限，函数返回现有数据，不做额外处理。

**下游价值：** 公告和财务数据为 Fundamental Agent 提供 LLM 无法从 yfinance 获取的中国 A 股特有财务信息（akshare 的数据源是东财/同花顺/财新），同时为 Debate Agent 提供公司级别的官方信息支撑。

---

## 7. Social Sentiment Agent（社交情绪）

**对应需求：** F-23（散户社交情绪）

**定位与作用：** 采集中国股市散户投资者的社交情绪数据，主要来自东方财富"股吧"平台。这部分数据反映了"散户情绪"，与基于新闻的 AI 情绪分析（Sentiment Agent）形成互补——一个是机构/媒体视角，一个是散户视角。

**交易所路由：** 检查 `exchange not in ("SH", "SZ", "BJ")` 时跳过 akshare 调用，返回空社交数据（`summary: "Social sentiment (Eastmoney Guba) not available for overseas stocks."`）。美股和港股不在中国社交平台的覆盖范围内，提前跳过避免了无意义的 akshare API 调用和潜在的异常。

**三维度数据采集：** 第一，`fetch_stock_comments()` 获取该股票在东方财富股吧的评论情绪评分，包括正面/负面评论比例、整体情绪得分。第二，`fetch_hot_stocks()` 获取当前市场热门股票排行榜，检查目标股票是否在热门榜单中（`is_trending`），以及排名位置（`trending_rank`）。第三，`fetch_individual_stock_hotrank()` 获取该股票的个体热度数据。

**数据结构：** 返回 `comment_sentiment`（评论情绪字典）、`hot_rank`（个体热度数据）、`is_trending`（是否热门，布尔值）、`trending_rank`（热门排名）、`hot_stocks_sample`（热门榜单 Top5 样本）。同时生成一段摘要文本。

**数据限制：** 港股和美股不在中国社交平台的覆盖范围内，对于这些市场的股票，本 Agent 返回空的社交数据。akshare 接口可能随时变更 schema 或遭遇速率限制，所有异常被捕获后返回空字典，不中断流水线。

---

## 8. Sentiment Agent（情绪分析）

**对应需求：** F-09（新闻情绪评分）、F-10（可解释的推理链）

**定位与作用：** 对 News Agent 采集的新闻文章进行逐篇情绪分析，计算相关性加权后的综合情绪得分，并生成可解释的推理链。这是系统中第一个使用 LLM 进行分析的 Agent（前面的 Market Data、News、Announcement 等都不涉及 LLM）。

**LLM 分析流程：** 将 Top 10 新闻文章的标题、来源、日期和摘要拼接为结构化文本，通过 `call_llm_structured()` 发送给 DeepSeek。System Prompt 要求 LLM 扮演"金融情绪分析专家"角色，对每篇文章进行情绪评分（-1.0 极度看空到 +1.0 极度看多），同时提供相关性评分（0-1）和情绪影响等级（high/medium/low）。Prompt 中特别包含讽刺/反讽提醒，因为金融新闻中常有"太好了，特斯拉又召回了"这类反向表达。

**相关性加权平均：** LLM 返回每篇文章的评分和相关性后，系统在代码层重新计算加权平均情绪得分（`weighted_sum / total_weight`）。如果 LLM 自行计算的 overall_score 与重新计算结果偏差超过 0.05，系统会覆盖为重新计算值。这确保了最终得分是可追溯、可辩护的——每个分数都能追溯到具体文章的评分和相关性。

**可解释性设计：** 输出中包含 `key_factors`（3-5 个具体驱动因素，如"Q3 盈利超预期"、"新产品发布"、"监管调查"），而不是泛泛的"利好消息"。每篇文章的 `rationale` 字段说明了评分依据。这些推理链会出现在最终的推荐理由中，满足 NF-02（可解释性）需求。

---

## 9. Fundamental Agent（基本面分析）

**对应需求：** F-11（财务比率分析）、F-12（同业比较与红旗检测）

**定位与作用：** 对目标股票进行基本面分析，生成财务健康评分（1-10 分制），识别财务红旗，并通过算法估值模型（DCF/PEG）为 LLM 提供数值锚点，防止 LLM 凭空臆测估值水平。

**算法估值锚点：** 在调用 LLM 之前，先通过 `compute_valuation_summary()` 计算算法估值指标。这包括 PEG 比率（市盈率相对盈利增长比率）、DCF 内在价值（基于自由现金流的折现模型）、安全边际（当前价格 vs DCF 估值的偏差百分比）和盈利收益率。这些数值通过 `valuation_calc.py` 中的公式计算，为 LLM 提供客观的数学基准。

**LLM 综合分析：** 将市场数据（价格、P/E、市值、52 周高低、SMA、RSI）和算法估值锚点一起发送给 DeepSeek，要求 LLM 从财务健康、估值合理性、同业比较和红旗检测四个维度进行分析。输出是 `FundamentalOutput` Pydantic 模型，包含：`health_score`（1-10）、各比率评估（P/E、P/B、ROE、负债）、同业比较说明、红旗列表和总结。

**降级处理：** 如果没有市场数据（Market Data Agent 失败），直接返回默认的空分析结果。LLM 结构化输出失败时（JSON 解析错误），`call_llm_structured` 会重试最多 2 次，仍失败则返回默认实例。估值锚点的引入解决了纯 LLM 分析的一个关键问题——LLM 不知道当前 P/E 到底是贵还是便宜，有了 PEG 和 DCF 的数值对比，它的判断就有了数学支撑。

---

## 10. Momentum Agent（动量分析）

**对应需求：** F-19 的补充需求（解决"上涨股被推荐 SELL"的问题）

**定位与作用：** 这是一个纯算法 Agent（无 LLM），专门解决系统中一个关键设计缺陷：Quant Agent 的 SMA/MACD 等技术指标具有滞后性，当股票刚刚开始强势上涨时，传统技术指标可能尚未发出买入信号，导致系统错误推荐 SELL。Momentum Agent 通过捕捉短期价格动能来弥补这一盲区。

**多周期收益计算：** 计算 3 日、5 日、10 日、20 日和 60 日的累计收益率，通过 `_fetch_recent_series()` 直接从 yfinance 获取最近 3 个月的收盘价序列。5 日收益被赋予了最高权重——这是核心设计选择，因为 5 日动能对短期价格变化最敏感。

**突破检测：** 判断当前价格是否处于 20 日新高附近（`breakout_20`）。突破新高是强烈的看涨信号，在后续 Advisory Agent 的决策覆盖中会触发特殊规则。

**量能激增检测：** 比较当日成交量与 20 日平均成交量的比值。`volume_surge_ratio ≥ 2.0` 表示成交量翻倍，结合价格方向判断是"买入放量"还是"恐慌性抛售"。

**趋势一致性：** 统计最近 20 个交易日中上涨天数的百分比。`trend_consistency ≥ 70%` 表明持续上涨趋势，≤30% 表明持续下跌。

**相对强度：** 将个股 20 日收益率与沪深 300 指数 20 日收益率做差，得到超额收益（relative strength）。跑赢大盘 +5% 以上加分，跑输 -5% 以下减分。

**评分合成：** 各子信号加权求和，clamped 到 [-100, +100]，分为五个等级（STRONG BULLISH / BULLISH / NEUTRAL / BEARISH / STRONG BEARISH MOMENTUM）。

---

## 11. Quant Agent（量化分析）

**对应需求：** F-20（算法量化评分）

**定位与作用：** 这是系统中的"数据裁判"——一个完全基于算法的量化分析 Agent，不依赖任何 LLM，通过经典技术指标系统计算综合评分，为多空辩论提供客观、无 AI 偏见的证据支撑。

**五大信号子系统：** 第一，移动平均系统（`compute_ma_signals`）——判断价格与 MA20/MA50/MA200 的关系，检测金叉/死叉。第二，RSI 动量（`compute_rsi_signals`）——将 RSI(14) 分为极度超买、超买、中性、超卖、极度超卖五个等级。第三，MACD 信号（`compute_macd_signals`）——判断强弱多头/空头及交叉状态。第四，52 周区间位置（`compute_range_signals`）——价格在 52 周高低之间的位置，判断回撤严重程度。第五，P/E 估值层级（`compute_pe_signals`）——负值/极端/偏高/适中/偏低五个档位。此外，`compute_advanced_signals` 还计算布林带（Bollinger Bands）、ATR（平均真实波幅）、随机指标（Stochastic）和 OBV（能量潮）等进阶指标。

**加权合成：** 每个信号附带 `weight` 字段（正数=看多，负数=看空），求和后 clamp 到 [-100, +100]。≥30 为 STRONG BUY，≥10 为 MODERATE BUY，-10 到 10 为 NEUTRAL，-10 到 -30 为 MODERATE SELL，≤-30 为 STRONG SELL。

**辩论价值：** 在 Debate Agent 中，Quant 的评分和信号被双方辩手同时引用。Bull 会强调"量化评分 +35，5 个看多信号"，Bear 会反驳"RSI 已进入超买区，MACD 即将死叉"。由于 Quant 是纯算法输出，双方无法质疑数据的客观性，辩论焦点转移到数据解读上。

---

## 12. Grid Strategy Agent（网格交易策略）

**对应需求：** F-21（网格交易策略提案）

**定位与作用：** 纯算法 Agent，分析目标股票是否适合网格交易策略，并生成四种策略变体（短期紧密网格、中期平衡网格、长期宽网格、累积型非对称网格），每种策略包含完整的交易参数和收益预测。

**适应性评估：** 第一步通过 `assess_suitability()` 评估网格交易适用性。评估因子包括：波动率（太低则交易机会少，太高则单边趋势风险大）、趋势强度（强趋势股不适合网格）、RSI 位置等。评分 0-100，≥50 认为适合。

**四种策略变体：** `generate_strategies()` 生成四种方案：
- **短期紧密网格（Short-term Tight Grid）：** ±8% 价格区间，16 格，1% 步长，适合日内交易者
- **中期平衡网格（Medium-term Balanced Grid）：** ±15% 区间，15 格，2% 步长，平衡收益和风险
- **长期宽网格（Long-term Wide Grid）：** ±25% 区间，10 格，5% 步长，适合长线投资者
- **累积型网格（Accumulation Grid）：** -20%/+10% 非对称区间，12 格，侧重低位建仓

**A 股交易规则：** 每网格股数向下取整到 100 的整数倍（A 股最小交易单位"一手"）。手续费模型包含佣金、过户费和印花税，每轮网格买入和卖出的费用都被精确计算。如果单笔网格利润扣除费用后为负，会标注 caveats 警告。

**月度收益估算：** 基于年化波动率估算每月网格触发次数，乘以每轮净利润，得到月度收益率预估。选择月度收益率最高的盈利策略作为"最佳策略"推荐。

**价格序列合成：** 由于 state 中只存储了 SMA 等摘要数据而非完整历史价格序列，`_synthesize_closes()` 函数利用 52 周高低和 SMA 数据合成一个合理的 60 点价格序列（基于正弦振荡），用于波动率计算。这是一种在有限信息下的近似方法。

---

## 13. Debate Agent（多空辩论）

**对应需求：** F-16（多空辩论轮次）

**定位与作用：** 这是整个系统最具创新性的组件。传统的 AI 投资分析是线性流水线，容易产生单向偏见。Debate Agent 让 Bull（看多方）和 Bear（看空方）两个角色基于同一份真实数据进行 2-5 轮结构化辩论，每轮必须引用具体的量化信号、财务指标和情绪分数。

**辩论流程：** 每轮辩论中，Bull 先发言，提出 3 个看多论点并附带证据；Bear 随后看到 Bull 的论点，针对其具体观点进行反驳，同时提出 3 个看空论点。两个角色使用不同的 system prompt——Bull 被告知"要为买入这只股票构建最强论证"，Bear 被告知"要为不买入或卖出这只股票构建最强论证"。

**上下文注入：** `_build_analysis_context()` 将所有上游分析结果（宏观环境、行业板块、市场数据、动量分析、情绪评分、基本面、量化信号、网格策略、公司公告、社交情绪）扁平化为结构化的文本。这确保双方辩手必须引用真实数据点，而不是凭空编造。Judge 的反馈也会注入到上下文中（"上一轮未解决的问题：XXX"），要求双方在后续轮次中回应。

**自环机制：** 在 LangGraph 中，Debate Agent 不是子图，而是通过条件边（conditional edge）形成自环。每轮辩论后，流程走向 Debate Judge，Judge 决定继续还是结束。这比子图实现更简单、调试更直观。

**语言支持：** 通过 `language_directive()` 在 system prompt 末尾追加语言指令（如"用中文回答"），确保辩论语言与用户一致。

---

## 14. Debate Judge Agent（辩论裁判）

**对应需求：** F-16 的动态深度控制（v2 新增）

**定位与作用：** Debate Judge 是一个独立的 LLM Agent，在每轮辩论结束后评估辩论质量和深度，决定是否需要更多轮次。它解决了固定轮次辩论的两个问题：一是辩论太浅就结束，二是辩论进入重复循环浪费时间。

**评估标准：** Judge 检查以下维度——实质性参与（双方是否在引用真实数据而非重复空话）、关键点覆盖（双方是否回应了对方最强论点）、收敛程度（双方是否在趋向综合理解还是各说各话）、饱和度（辩论是否开始重复已有观点）。

**安全边界：** 设置了最小轮次（MIN_DEBATE_ROUNDS = 2）和最大轮次（MAX_DEBATE_ROUNDS = 5）的硬性边界。低于 2 轮自动继续，达到 5 轮强制结束。即使 Judge 的 LLM 调用失败，也会自动结束辩论，不会导致无限循环。

**输出结构：** `JudgeDecision` Pydantic 模型包含：`verdict`（continue 或 concluded）、`quality_score`（0-100 的辩论质量评分）、`reason`（判决理由）、`unresolved_points`（如果继续，列出仍需回应的具体问题）、`bull_strength` 和 `bear_strength`（双方论点强度评分，0-100）。

**下游路由：** `should_continue_debate_with_judge()` 条件边函数读取 Judge 的 verdict——如果继续且未达最大轮次，路由回 Debate Agent 开始新一轮；否则路由到 Risk Agent。Judge 的 `unresolved_points` 会注入到下一轮辩论的上下文中，要求双方必须回应。

**辩论强度在 Advisory 中的应用：** Judge 评估的 `bull_strength` 和 `bear_strength` 差值会被 Advisory Agent 的 `_compute_decision_override()` 函数使用——如果一方压倒性胜出（差值 ≥ 25）且算法复合评分支持，会触发 LLM 建议覆盖。

---

## 15. Risk Agent（风险评估）

**对应需求：** F-13（风险评估与评分）、F-15（合规免责声明）

**定位与作用：** 从多个风险维度对目标股票进行综合风险评估，生成 1-10 的风险评分和枚举化的风险因素列表。它是投资推荐前的最后一道"刹车"——即使所有分析维度都看好，极高的风险评分也会影响最终建议的置信度。

**多维度评估：** 通过 system prompt 引导 LLM 考虑四个风险维度——市场风险（波动率、beta 系数）、行业风险（行业逆风/顺风，基于新闻和板块数据）、公司特有风险（诉讼、监管、关键人物依赖）、流动性风险（日均成交量评估）。风险评估的输入包括宏观市场状态、行业板块信息、市场数据（价格、P/E、RSI、技术信号）、动量评分和收益率、情绪评分和关键因素、基本面健康评分和红旗列表。

**评分体系：** 1-3 分为低风险（low），4-6 分为中等风险（medium），7-8 分为高风险（high），9-10 分为极高风险（critical）。风险评分直接影响 Advisory Agent 的复合评分公式中的 `risk_score` 分量（`risk_score = (5 - risk_raw) * 20`，即风险越高此项越负）。

**合规设计：** 虽然免责声明主要由 Advisory Agent 在最终输出中注入，Risk Agent 通过列举具体风险因素为免责声明提供实质内容。`RiskOutput` Pydantic 模型包含 `risk_factors`（枚举化风险因素列表）和 `mitigation_notes`（缓解措施建议）。

---

## 16. Advisory Agent（综合建议）

**对应需求：** F-17（投资建议综合）、F-18（推理链组装）

**定位与作用：** 这是流水线的最后一个 Agent，负责综合所有上游分析结果、辩论记录和 Judge 裁决，生成最终的 buy/hold/sell 投资建议。它同时承担一个关键功能——当 LLM 的判断与算法复合评分严重冲突时，用算法覆盖 LLM 的建议。

**加权综合：** System Prompt 明确指定了各维度的权重——动量（短期价格行为）20%、基本面分析 20%、量化信号（长期趋势）15%、宏观/行业背景 15%、情绪分析 10%、风险评估 10%、技术指标 10%。LLM 需要同时考虑辩论结果：哪些观点被对方承认、哪些仍存在争议。

**算法决策覆盖（核心创新）：** `_compute_decision_override()` 函数从动量、量化、基本面、情绪和风险五个维度计算加权复合评分（-100 到 +100）。如果 LLM 建议与算法评分严重冲突，系统会强制执行以下规则（按优先级排序）：
1. **强短期上涨 + 动量 ≥ 30 + 复合评分 ≥ 0** → 强制 BUY（置信度 ≥ 0.65）
2. **复合评分 ≥ 35** → 强制 BUY
3. **复合评分 ≤ -35** → 强制 SELL
4. **20 日突破 + 5 日收益 > 0 + 复合评分 ≥ 10** → 强制 BUY
5. **5 日收益 ≥ 5 + 复合评分 ≥ 0** → 禁止 SELL（rising_stock_no_sell_guard）
6. **Bull 辩论强势胜出 ≥ 25 + 复合评分 ≥ 10** → 强制 BUY
7. **Bear 辩论强势胜出 ≥ 25 + 复合评分 ≤ -10** → 强制 SELL

这些规则解决了 LLM 的一个已知问题——面对混合信号时 LLM 有强烈的 HOLD 倾向，即使数值证据明确指向 BUY 或 SELL。

**输出结构：** `RecommendationOutput` 包含 `recommendation`（buy/hold/sell）、`confidence`（0-1）、`investment_horizon`（short/medium/long-term）、`supporting_factors`（支持因素列表）、`dissenting_factors`（反对因素列表）、`debate_summary`（辩论总结）、`reasoning`（完整推理链）。

---

## 17. Follow-up Agent（后续问答）

**对应需求：** F-24（带完整上下文的后续对话）

**定位与作用：** 这是一个独立于 LangGraph 流水线的 Agent，不在主图中注册。当用户在一次完整分析后提出后续问题（如"Why did the Bear say it's risky?"），Follow-up Agent 利用之前所有 Agent 的完整输出结果进行回答。

**触发检测：** 在 `frontend/app.py` 中，系统通过启发式规则判断用户输入是新分析请求还是后续问题——包含 "why"、"explain"、"what about" 等关键词且不包含新的 ticker 模式时，判定为后续问题。如果用户提到了新的股票代码，则重新触发完整流水线。

**上下文构建：** `_build_full_context()` 将先前分析的完整 state 字典转换为结构化的长文本，涵盖市场数据、新闻、公告、财务摘要、社交情绪、AI 情绪分析、基本面、量化分析、网格策略、多空辩论、风险评估和最终推荐。每个 Agent 的输出都以格式化章节呈现。

**LLM 问答：** 使用 `call_llm()`（原始 LLM 调用，非结构化输出），因为答案是自然语言而非结构化 JSON。System Prompt 要求 LLM 基于提供的数据回答，引用具体数字和 Agent 的发现，对于分析中未涵盖的问题要如实告知。回答末尾自动添加免责声明。

**设计选择：** 不纳入 LangGraph 图的原因是后续问答不需要重新执行所有分析节点，而是直接复用已有结果。这避免了不必要的 LLM 调用和 API 请求，节省了时间和成本。
