# REQ-002 Grid Trading Excel Calculator

> Status: Requirement Finalized
> Created: 2026-04-12
> Updated: 2026-04-12

## 1. Background

Grid trading is a quantitative strategy where a trader places buy/sell orders at regular price intervals. Managing multiple grid levels manually is error-prone. Users need a ready-to-use `.xlsx` file where they fill in a few parameters and the entire grid table — price levels, actions, P&L, position, cost — recalculates automatically via Excel formulas.

No Python, no scripts. Open the file, edit the parameter cells, done.

## 2. Target Users & Scenarios

**Primary user**: Individual retail investor trading A-shares.

**Core scenario**: User opens the Excel file, changes 9 yellow-highlighted parameter cells (e.g. current price, interval, shares per grid), and immediately sees the full grid table update with each level's action, commission, P&L, position, and avg cost.

**Secondary scenario**: User tweaks parameters (e.g. narrower interval, larger position) and observes how net profit and capital requirements change in real time.

## 3. Functional Requirements

### F-01 Parameter Input Area

A dedicated block at the top of the sheet (rows 1–11) with labeled parameter cells. All parameter cells are **yellow-highlighted** and unlocked; all formula cells are locked (sheet protection optional).

| Parameter | Cell | Default | Description |
|:---|:---|:---|:---|
| Stock Name | B2 | 泰达股份 | Display label only |
| Current Price | B3 | 4.10 | Current market price (CNY) |
| Grid Interval | B4 | 0.20 | Price step between grid levels (CNY) |
| Shares per Grid | B5 | 1000 | Shares traded at each level (multiple of 100) |
| Fixed Fee | B6 | 10.00 | Minimum commission per trade (CNY) |
| Fee Rate | B7 | 0.0001 | Proportional commission (e.g. 0.0001 = 0.01%) |
| Initial Shares Held | B8 | 5000 | Current holdings in shares |
| Upper Limit | B9 | 5.00 | Highest grid price (CNY) |
| Lower Limit | B10 | 3.50 | Lowest grid price (CNY) |
| Initial Capital | B11 | 50000 | Total capital available (CNY) |

- All 10 parameters feed into the grid table and summary via cell references — no hardcoded values anywhere in the formulas.

### F-02 Grid Table (Auto-Generated via Formulas)

Starting from a fixed row (e.g. row 15), each row represents one grid level. The table expands automatically based on Upper/Lower Limit and Grid Interval. Rows beyond the valid range are hidden or left blank via `IF` formulas.

**Columns:**

| Col | Header | Formula Logic |
|:---|:---|:---|
| A | Grid No. | `=IF(grid_price="","", ROW()-offset)` — sequential, blank when out of range |
| B | Grid Price | `=Lower_Limit + (ROW()-offset) * Grid_Interval`, capped at Upper_Limit |
| C | Action | `=IF(price<current,"BUY", IF(price>current,"SELL","CURRENT"))` |
| D | Shares Traded | `=$B$5` (fixed reference to parameter) |
| E | Trade Amount | `=B_price * D_shares` |
| F | Commission | `=MAX($B$6, E_amount * $B$7)` |
| G | Shares Change | `=IF(action="BUY", $B$5, IF(action="SELL", -$B$5, 0))` |
| H | Cumulative Shares | Running sum from initial shares at CURRENT row outward |
| I | Avg Cost Price | Weighted average, updated on BUY; unchanged on SELL |
| J | Market Value | `=H_shares * B_price` |
| K | Gross Profit | `=$B$4 * $B$5` (same for every row) |
| L | Total Commission | `=F_buy_commission + F_sell_commission` (both legs) |
| M | Net Profit | `=K - L` |
| N | Cumulative P&L | Running sum of Net Profit |

- The CURRENT row (where Action = "CURRENT") is highlighted **yellow**.
- Rows where Net Profit ≤ 0 are highlighted **orange** via Conditional Formatting.
- If Cumulative Shares would go negative on a SELL row, that cell shows "ERROR" in red via Conditional Formatting.

### F-03 Summary Statistics Block

A block between the parameter area and the grid table (rows 13–14 area), all formula-driven:

| Label | Formula |
|:---|:---|
| Total Grid Levels | `=COUNTIF(Action_col, "<>")` |
| Net Profit per Grid | `=$B$4*$B$5 - 2*MAX($B$6, mid_price*$B$7)` |
| Total Commission (one cycle) | `=SUMIF(...)` across all commission cells |
| Min Oscillations to Break Even | `=CEILING(total_commission / net_per_grid, 1)` |
| Minimum Required Capital | `=$B$10 * $B$5 * COUNTIF(Action_col,"BUY")` |
| Capital Sufficiency | `=IF($B$11 >= min_capital, "OK ✓", "INSUFFICIENT ✗")` |
| T+1 Note | Static text: "A股T+1: 当日买入不可当日卖出" |

### F-04 Conditional Formatting Rules

| Condition | Range | Style |
|:---|:---|:---|
| Action = "CURRENT" | Entire row | Yellow fill |
| Net Profit ≤ 0 | Entire row | Orange fill |
| Cumulative Shares < 0 | Column H cell | Red fill, bold |
| Action = "BUY" | Column C cell | Light green fill |
| Action = "SELL" | Column C cell | Light red fill |

## 4. Non-functional Requirements

- **File format**: `.xlsx` (Excel 2007+), single sheet named "网格计算".
- **No macros / VBA**: Pure formulas and conditional formatting only.
- **Max grid rows pre-built**: 100 rows (enough for any realistic range/interval combination). Rows outside the active range show blank via `IF` formulas.
- **Column widths**: Pre-set to readable widths; headers bold.
- **Deliverable**: A single file `tools/grid_trading_calculator.xlsx` committed to the repository.

## 5. Out of Scope

- Python scripts or code generation
- Historical backtesting
- Multi-stock comparison sheets
- Unequal grid intervals
- Partial fill simulation
- VBA / macros
- Annual return estimation

## 6. Acceptance Criteria

| ID | Feature | Condition | Expected Result |
|:---|:---|:---|:---|
| AC-01 | F-01 | Open file with defaults | Grid table shows 8 rows (3.5 to 4.9, step 0.2) |
| AC-02 | F-02 | Default params | Row at 4.1 shows CURRENT, yellow highlight |
| AC-03 | F-02 | Commission at 4.1 | max(10, 4100×0.0001) = 10.00 CNY |
| AC-04 | F-02 | BUY row at 3.9 | Shares change = +1000, cumulative = 6000 |
| AC-05 | F-02 | Avg cost at 3.9 | (5000×4.10 + 1000×3.90)/6000 ≈ 4.067 |
| AC-06 | F-02 | Net profit per grid | 0.2×1000 − 2×10 = 180 CNY |
| AC-07 | F-04 | Change interval to 0.01 | Net profit < 0 → row turns orange |
| AC-08 | F-03 | Capital sufficiency default | 50000 ≥ 3.5×1000×4 = 14000 → shows "OK ✓" |
| AC-09 | F-01 | Change Upper Limit to 6.0 | Grid table automatically extends to include 5.2, 5.4… 5.8 |
| AC-10 | F-01 | Change Grid Interval to 0.10 | Grid table shows 16 rows instead of 8 |

## 7. Change Log

| Version | Date | Changes | Affected Scope | Reason |
|:---|:---|:---|:---|:---|
| v1 | 2026-04-12 | Initial version | ALL | - |
| v2 | 2026-04-12 | Change deliverable from Python script to pure Excel file with formulas | ALL | User clarification: no Python needed |
