# REQ-002 Grid Trading Excel Calculator

> Status: Requirement Finalized
> Created: 2026-04-12
> Updated: 2026-04-12

## 1. Background

Grid trading is a quantitative strategy where a trader places buy orders at regular price intervals below the current market price and sell orders above it. Managing multiple grid levels manually is error-prone and time-consuming. Users need a pre-trade validation tool that, given a set of parameters, immediately shows every grid level's trade action, position change, cost basis, and cumulative P&L — so they can judge whether the strategy parameters are viable before placing any orders.

The tool is implemented as a Python script that generates a formatted `.xlsx` file. All parameters are adjustable via a configuration section at the top of the generated sheet.

## 2. Target Users & Scenarios

**Primary user**: Individual retail investor trading A-shares on a domestic broker platform.

**Core scenario**: Before setting up a grid strategy on a stock, the user fills in 9 parameters and runs the script to get a full grid table — checking whether each grid's net profit is positive, whether total capital is sufficient, and where the current price sits relative to the grid.

**Secondary scenario**: Adjusting parameters (e.g., narrowing the interval or increasing shares per grid) and re-running to compare outcomes.

## 3. Functional Requirements

### F-01 Parameter Configuration

The script accepts the following 9 parameters (all adjustable, with defaults matching the worked example):

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `stock_name` | str | "泰达股份" | Display name of the stock |
| `current_price` | float | 4.10 | Current market price (CNY) |
| `grid_interval` | float | 0.20 | Price interval between grid levels (CNY) |
| `shares_per_grid` | int | 1000 | Shares to trade at each grid level (must be multiple of 100) |
| `fixed_fee` | float | 10.0 | Fixed commission per trade (CNY) |
| `fee_rate` | float | 0.0001 | Proportional commission rate (e.g. 0.0001 = 0.01%) |
| `initial_shares` | int | 5000 | Initial holdings in shares (directly input, not reverse-calculated) |
| `upper_limit` | float | 5.00 | Grid upper boundary (CNY) |
| `lower_limit` | float | 3.50 | Grid lower boundary (CNY) |
| `initial_capital` | float | 50000 | Total available capital for reference (CNY) |

- Main flow: Parameters defined as variables at the top of the script; user edits and re-runs to regenerate the Excel.
- Error handling: Validate that `upper_limit > current_price > lower_limit`, `shares_per_grid` is a positive multiple of 100, `grid_interval > 0`, all fees ≥ 0.
- Edge cases: If `grid_interval` is so small that net profit per grid is negative, emit a warning row in the summary.

### F-02 Grid Level Auto-Generation

Generate one row per grid level from `lower_limit` to `upper_limit` in steps of `grid_interval`.

Each row contains:

| Column | Description |
|:---|:---|
| Grid No. | Sequential index (1 = lowest price) |
| Grid Price | Calculated price for this level (CNY) |
| Action | BUY (price < current), SELL (price > current), CURRENT (nearest to current price, highlighted) |
| Shares Traded | Fixed `shares_per_grid` for every grid |
| Trade Amount | Grid Price × Shares Traded (CNY) |
| Commission | `max(fixed_fee, Trade Amount × fee_rate)` (CNY) |

- Main flow: Prices generated bottom-up; direction determined by comparing grid price to `current_price`.
- Edge cases: If a grid price lands exactly on `current_price`, mark as CURRENT. If rounding causes the last grid to exceed `upper_limit`, cap and note it.

### F-03 Position & Cost Tracking

Cumulative position state after each grid triggers (simulating sequential execution from the initial position downward for BUY grids and upward for SELL grids).

| Column | Description |
|:---|:---|
| Shares Change | +`shares_per_grid` for BUY, −`shares_per_grid` for SELL |
| Cumulative Shares | Running total of shares held |
| Avg Cost Price | Weighted average cost of current holdings (CNY), updated on each BUY |
| Market Value | Cumulative Shares × Grid Price (CNY) |

- Main flow: Start from `initial_shares` at the CURRENT row; BUY grids below accumulate shares and update weighted avg cost; SELL grids above reduce shares (avg cost unchanged on sell).
- Error handling: If cumulative shares would go negative (over-sell), flag the cell in red and stop the sell chain.
- Edge cases: 100-share round-lot — `shares_per_grid` is validated at input; no partial lots generated.

### F-04 P&L Calculation

For each grid level, calculate profit assuming that grid executes as a round-trip (one buy + one sell one interval apart).

| Column | Description |
|:---|:---|
| Gross Profit | `grid_interval × shares_per_grid` (CNY) — fixed per grid |
| Total Commission | Commission for buy leg + Commission for sell leg |
| Net Profit | Gross Profit − Total Commission |
| Cumulative P&L | Running sum of Net Profit from the bottom grid upward |

- Main flow: Gross profit is the same for every grid (fixed interval × fixed shares). Net profit shows whether the commission eats into the gain.
- Error handling: If Net Profit ≤ 0, highlight that row in orange with a warning note "Fee exceeds gain".
- Edge cases: The CURRENT row has no completed round-trip; mark its P&L columns as N/A.

### F-05 Summary Statistics

A separate summary block (above or below the grid table) showing:

| Statistic | Formula |
|:---|:---|
| Total Grid Levels | Count of all generated rows |
| Net Profit per Grid | `grid_interval × shares_per_grid − 2 × max(fixed_fee, mid_amount × fee_rate)` |
| Total Commission (one full cycle) | Sum of all commissions for one complete up-down sweep |
| Min Oscillations to Break Even | `ceil(total_commission_one_cycle / net_profit_per_grid)` |
| Minimum Required Capital | `lower_limit × shares_per_grid × total_buy_grids` |
| Capital Sufficiency | Flag: OK if `initial_capital ≥ Minimum Required Capital`, else INSUFFICIENT |

- Main flow: Computed via formulas, displayed in a styled header block.
- Edge cases: If net profit per grid is negative, show "WARNING: grid interval too narrow" instead of break-even count.

## 4. Non-functional Requirements

- **Output format**: Single `.xlsx` file, one sheet. Parameters block at top (rows 1–12), summary block follows, then the grid table.
- **Styling**: Header row bold + light blue fill; CURRENT row yellow highlight; negative net-profit rows orange; over-sell error rows red.
- **Column widths**: Auto-fit to content.
- **Dependency**: Python 3.8+, `openpyxl` library only (no pandas required).
- **Execution**: Single script `tools/grid_trading_excel.py`; run with `python tools/grid_trading_excel.py`; output file written to `output/grid_trading_<stock_name>_<date>.xlsx`.
- **Reproducibility**: Same parameters always produce identical output.
- **T+1 note**: A comment cell in the summary block notes "A-share T+1 rule: shares bought today cannot be sold on the same day." No logic enforcement — user awareness only.

## 5. Out of Scope

- Historical backtesting against real price data
- Automated trade execution or broker API integration
- Multi-stock comparison
- Dynamic rebalancing suggestions
- Unequal grid intervals (all grids use the same fixed interval)
- Partial fill handling
- VBA macros or Excel add-ins
- Annual return estimation

## 6. Acceptance Criteria

| ID | Feature | Condition | Expected Result |
|:---|:---|:---|:---|
| AC-01 | F-01 | Run with default parameters | Script completes without error; .xlsx file created in output/ |
| AC-02 | F-02 | Default params (3.5–5.0, interval 0.2) | 8 grid rows generated: prices 3.5, 3.7, 3.9, 4.1, 4.3, 4.5, 4.7, 4.9 (±rounding) |
| AC-03 | F-02 | Commission formula | At price 4.1, amount=4100; fee=max(10, 4100×0.0001)=max(10,0.41)=10.0 CNY |
| AC-04 | F-03 | CURRENT row | Row for price 4.1 marked CURRENT, initial_shares=5000, avg cost=4.10 |
| AC-05 | F-03 | BUY grid at 3.9 | Cumulative shares = 5000+1000=6000; avg cost = (5000×4.10+1000×3.90)/6000 ≈ 4.067 |
| AC-06 | F-04 | Net profit per grid | Gross=0.2×1000=200; commission buy+sell=10+10=20; net=180 CNY |
| AC-07 | F-04 | Fee-exceeds-gain warning | Set interval=0.01, fee=10 → net<0 → row highlighted orange |
| AC-08 | F-05 | Capital sufficiency | initial_capital=50000, min_required=3.5×1000×4=14000 → shows OK |
| AC-09 | F-01 | Validation | shares_per_grid=150 → ValueError "shares_per_grid must be a multiple of 100" |
| AC-10 | F-01 | Validation | upper_limit=3.0, lower_limit=5.0 → ValueError "upper_limit must be greater than lower_limit" |

## 7. Change Log

| Version | Date | Changes | Affected Scope | Reason |
|:---|:---|:---|:---|:---|
| v1 | 2026-04-12 | Initial version | ALL | - |
