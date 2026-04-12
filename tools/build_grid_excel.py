"""
build_grid_excel.py — Grid Trading Excel Calculator builder

Generates tools/grid_trading_calculator.xlsx:
  - Pure Excel formulas + conditional formatting, no macros, no VBA.
  - Open the file, edit yellow parameter cells, all columns auto-recalculate.

Usage:
  pip install openpyxl
  python tools/build_grid_excel.py

Deliverable: tools/grid_trading_calculator.xlsx
"""

import os
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.formatting.rule import FormulaRule

# ─── Layout constants ─────────────────────────────────────────────────────────
PARAM_START   = 4    # first parameter row (rows 4–13)
SUMMARY_START = 16   # first summary data row  (section header at row 15)
GRID_HDR_ROW  = 24   # grid table column-header row
DATA_START    = 25   # first grid data row
DATA_END      = 124  # last grid data row  (100 pre-built levels)

# Column indices (1-based)
C_NO    = 1   # A  Grid No.
C_PRC   = 2   # B  Grid Price
C_ACT   = 3   # C  Action
C_SHR   = 4   # D  Shares Traded
C_AMT   = 5   # E  Trade Amount
C_COM   = 6   # F  Commission per leg
C_DSHP  = 7   # G  Shares Change
C_CSHP  = 8   # H  Cumulative Shares
C_AVG   = 9   # I  Avg Cost
C_MKT   = 10  # J  Market Value
C_GRS   = 11  # K  Gross Profit
C_TCOM  = 12  # L  Total Commission (round-trip)
C_NET   = 13  # M  Net Profit
C_CPNL  = 14  # N  Cumulative P&L

# Parameter cell addresses (all in column B)
P_NAME  = "$B$4"   # stock name
P_CUR   = "$B$5"   # current price
P_INT   = "$B$6"   # grid interval
P_SHR   = "$B$7"   # shares per grid
P_FEE   = "$B$8"   # fixed fee per leg
P_RATE  = "$B$9"   # proportional fee rate
P_ISHP  = "$B$10"  # initial shares held
P_UP    = "$B$11"  # upper limit
P_DN    = "$B$12"  # lower limit
P_CAP   = "$B$13"  # initial capital

# ─── Style helpers ────────────────────────────────────────────────────────────

def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)

def _font(bold=False, size=10, color="000000", italic=False, white=False) -> Font:
    return Font(bold=bold, size=size, color=("FFFFFF" if white else color), italic=italic)

def _border() -> Border:
    s = Side(style="thin")
    return Border(left=s, right=s, top=s, bottom=s)

BORDER   = _border()
ALIGN_C  = Alignment(horizontal="center", vertical="center")
ALIGN_L  = Alignment(horizontal="left",   vertical="center")
ALIGN_R  = Alignment(horizontal="right",  vertical="center")
ALIGN_W  = Alignment(horizontal="center", vertical="center", wrap_text=True)

# Fill palette
F_TITLE  = _fill("1F4E79")   # dark blue — title row
F_PLAB   = _fill("D6E4F0")   # light blue — param label
F_PVAL   = _fill("FFFACD")   # light yellow — editable input
F_SHDR   = _fill("D6E4F0")   # light blue — summary label
F_GHDR   = _fill("2E75B6")   # blue — grid column header
F_YELLOW = _fill("FFFF00")   # yellow — CURRENT row
F_ORANGE = _fill("FFA500")   # orange — net profit ≤ 0
F_RED    = _fill("FF6B6B")   # red — over-sell error
F_LGRN   = _fill("C6EFCE")   # light green — BUY
F_LRED   = _fill("FFC7CE")   # light red — SELL

# ─── Main entry point ─────────────────────────────────────────────────────────

def build(output_path: str) -> None:
    """Build the grid trading Excel workbook and save to output_path."""
    wb = Workbook()
    ws = wb.active
    ws.title = "网格计算"

    _set_col_widths(ws)
    _write_title(ws)
    _write_params(ws)
    _write_summary(ws)
    _write_grid_header(ws)
    _write_grid_data(ws)
    _apply_cond_fmt(ws)

    # Freeze rows 1–24 so the grid header stays visible when scrolling
    ws.freeze_panes = f"A{DATA_START}"

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    print(f"[OK] Created: {output_path}")


# ─── Section writers ──────────────────────────────────────────────────────────

def _set_col_widths(ws) -> None:
    """Set column widths for all 14 columns."""
    for col, width in zip(
        "ABCDEFGHIJKLMN",
        [9, 16, 9, 14, 15, 16, 13, 16, 14, 16, 14, 18, 14, 16],
    ):
        ws.column_dimensions[col].width = width


def _write_title(ws) -> None:
    """Write the title row and instruction subtitle."""
    ws.row_dimensions[1].height = 38
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 18

    _merged_row(ws, 1, "A1:N1",
                "网格交易计算器  ·  Grid Trading Calculator",
                _font(bold=True, size=16, white=True), F_TITLE, ALIGN_C)

    _merged_row(ws, 2, "A2:N2",
                "▶  修改下方黄色单元格，所有列自动重算   "
                "|   Edit yellow cells — the entire table auto-recalculates",
                _font(italic=True, size=9, color="595959"), None, ALIGN_C)

    _merged_row(ws, 3, "A3:N3",
                "━━  参数设置  Parameters  ━━",
                _font(bold=True, color="1F4E79"), None, ALIGN_L)


def _write_params(ws) -> None:
    """Write the 10 editable parameter rows (yellow value cells)."""
    rows = [
        # (label,                                    default value,  number format)
        ("标的名称  Stock Name",                     "泰达股份",     None),
        ("当前价格  Current Price  (元)",             4.10,           "#,##0.000"),
        ("网格间距  Grid Interval  (元)",             0.20,           "#,##0.000"),
        ("每格交易股数  Shares per Grid  (股)",       1000,           "#,##0"),
        ("固定手续费  Fixed Fee  (元/笔)",            10.0,           "#,##0.00"),
        ("比例费率  Fee Rate  (万分之一=0.0001)",     0.0001,         "0.0000%"),
        ("初始持仓  Initial Shares  (股)",            5000,           "#,##0"),
        ("网格上限  Upper Limit  (元)",               5.00,           "#,##0.000"),
        ("网格下限  Lower Limit  (元)",               3.50,           "#,##0.000"),
        ("初始资金  Initial Capital  (元)",           50000,          "#,##0"),
    ]

    for i, (label, default, fmt) in enumerate(rows):
        r = PARAM_START + i
        ws.row_dimensions[r].height = 20

        # Label cell (column A, blue background)
        c_label = ws.cell(r, 1, label)
        c_label.fill      = F_PLAB
        c_label.font      = _font(bold=True)
        c_label.alignment = ALIGN_L
        c_label.border    = BORDER

        # Value cell (column B, yellow — editable)
        c_val = ws.cell(r, 2, default)
        c_val.fill      = F_PVAL
        c_val.font      = _font()
        c_val.alignment = ALIGN_R
        c_val.border    = BORDER
        if fmt:
            c_val.number_format = fmt

    # Tip row below parameters
    tip_row = PARAM_START + len(rows)  # row 14
    _merged_row(ws, tip_row, f"A{tip_row}:N{tip_row}",
                "  ↑  黄色单元格为可修改的输入参数   "
                "|   Yellow cells are editable — formulas update automatically",
                _font(italic=True, size=8, color="888888"), None, ALIGN_L)
    ws.row_dimensions[tip_row].height = 14


def _write_summary(ws) -> None:
    """Write the summary statistics block (rows 15–21)."""
    # Section header (row 15)
    hdr = SUMMARY_START - 1
    ws.row_dimensions[hdr].height = 18
    _merged_row(ws, hdr, f"A{hdr}:N{hdr}",
                "━━  汇总统计  Summary  ━━",
                _font(bold=True, color="1F4E79"), None, ALIGN_L)

    # Row indices for formula cross-references
    r_total_grids   = SUMMARY_START      # 16
    r_net_per_grid  = SUMMARY_START + 1  # 17
    r_min_capital   = SUMMARY_START + 2  # 18
    r_cap_suffix    = SUMMARY_START + 3  # 19
    r_breakeven     = SUMMARY_START + 4  # 20
    r_t1_note       = SUMMARY_START + 5  # 21

    DS, DE = DATA_START, DATA_END

    summary_rows = [
        # (label, formula_or_text, number_format)
        ("总网格层数  Total Grid Levels",
         f'=SUMPRODUCT((B{DS}:B{DE}<>"")*1)',
         "#,##0"),

        ("单格净利润  Net Profit per Grid  (元)",
         f'={P_INT}*{P_SHR}-2*MAX({P_FEE},{P_CUR}*{P_SHR}*{P_RATE})',
         "#,##0.00"),

        ("最低所需资金  Min Required Capital  (元)",
         f'={P_DN}*{P_SHR}*COUNTIF(C{DS}:C{DE},"BUY")',
         "#,##0"),

        ("资金充裕度  Capital Sufficiency",
         f'=IF({P_CAP}>=B{r_min_capital},'
         f'"✓ 充裕  余额 "&TEXT({P_CAP}-B{r_min_capital},"#,##0")&" 元",'
         f'"✗ 不足  缺口 "&TEXT(B{r_min_capital}-{P_CAP},"#,##0")&" 元")',
         None),

        ("盈亏平衡振荡次数  Break-even Oscillations",
         f'=IF(B{r_net_per_grid}<=0,"⚠ 单格净利为负，无法计算",'
         f'TEXT(CEILING(SUMIF(B{DS}:B{DE},"<>",F{DS}:F{DE})*2'
         f'/B{r_net_per_grid},1),"0")&" 次完整振荡")',
         None),

        ("A股T+1提示  T+1 Rule",
         "当日买入的股票不可当日卖出   /   "
         "Shares bought today cannot be sold on the same day",
         None),
    ]

    for i, (label, formula, fmt) in enumerate(summary_rows):
        r = SUMMARY_START + i
        ws.row_dimensions[r].height = 20

        c_label = ws.cell(r, 1, label)
        c_label.fill      = F_SHDR
        c_label.font      = _font(bold=True)
        c_label.alignment = ALIGN_L
        c_label.border    = BORDER

        c_val = ws.cell(r, 2, formula)
        c_val.font      = _font()
        c_val.alignment = ALIGN_L
        c_val.border    = BORDER
        ws.merge_cells(f"B{r}:N{r}")
        if fmt:
            c_val.number_format = fmt

    # Spacing + grid section header
    ws.row_dimensions[SUMMARY_START + len(summary_rows)].height = 8
    grid_sect_row = GRID_HDR_ROW - 1  # row 23
    ws.row_dimensions[grid_sect_row].height = 18
    _merged_row(ws, grid_sect_row, f"A{grid_sect_row}:N{grid_sect_row}",
                "━━  网格明细  Grid Detail  ━━",
                _font(bold=True, color="1F4E79"), None, ALIGN_L)


def _write_grid_header(ws) -> None:
    """Write the grid table column headers (row 24)."""
    headers = [
        "序号\nNo.",
        "网格价格\nPrice (元)",
        "操作\nAction",
        "交易股数\nShares",
        "成交金额\nAmount (元)",
        "单腿手续费\nComm. (元)",
        "持仓变化\nΔShares",
        "累计持仓\nCum.Shares",
        "持仓均价\nAvg Cost (元)",
        "持仓市值\nMkt Val (元)",
        "单格毛利\nGross (元)",
        "双边手续费\nTotal Comm.",
        "单格净利\nNet (元)",
        "累计盈亏\nCum.P&L (元)",
    ]
    ws.row_dimensions[GRID_HDR_ROW].height = 44
    for col, hdr in enumerate(headers, 1):
        c = ws.cell(GRID_HDR_ROW, col, hdr)
        c.fill      = F_GHDR
        c.font      = _font(bold=True, white=True)
        c.alignment = ALIGN_W
        c.border    = BORDER


def _write_grid_data(ws) -> None:
    """Write formula strings for all 100 pre-built grid data rows."""
    DS = DATA_START  # 25

    # k_expr: number of grid levels between the CURRENT level and this row.
    #   k > 0  → below current price (BUY region, shares are added)
    #   k = 0  → CURRENT level
    #   k < 0  → above current price (SELL region, shares are removed)
    k_expr = f"(ROUND(({P_CUR}-{P_DN})/{P_INT},0)-(ROW()-{DS}))"

    for r in range(DS, DATA_END + 1):
        # Shorthand references for this row's cells
        b  = f"B{r}"   # grid price
        e  = f"E{r}"   # trade amount
        f_ = f"F{r}"   # commission per leg
        h  = f"H{r}"   # cumulative shares
        k_ = f"K{r}"   # gross profit cell
        l_ = f"L{r}"   # total commission cell
        m  = f"M{r}"   # net profit cell
        n  = f"N{r}"   # cumulative P&L cell (this row)
        np = f"N{r-1}" # cumulative P&L cell (previous row)

        # Helper prefix: emit "" for rows where grid price exceeds upper limit
        if_ = f'=IF({b}="","",'

        # ── A: Grid sequence number ─────────────────────────────────────
        ws.cell(r, C_NO).value = f'=IF({b}="","",ROW()-{DS - 1})'

        # ── B: Grid Price ───────────────────────────────────────────────
        # Price = lower_limit + (row_index) * interval, capped at upper_limit
        ws.cell(r, C_PRC).value = (
            f'=IF(ROUND({P_DN}+(ROW()-{DS})*{P_INT},4)<={P_UP},'
            f'ROUND({P_DN}+(ROW()-{DS})*{P_INT},4),"")'
        )
        ws.cell(r, C_PRC).number_format = "#,##0.000"

        # ── C: Action ───────────────────────────────────────────────────
        ws.cell(r, C_ACT).value = (
            f'=IF({b}="","",IF(ROUND({b},4)<ROUND({P_CUR},4),"BUY",'
            f'IF(ROUND({b},4)>ROUND({P_CUR},4),"SELL","CURRENT")))'
        )

        # ── D: Shares Traded ────────────────────────────────────────────
        ws.cell(r, C_SHR).value = f'{if_}{P_SHR})'
        ws.cell(r, C_SHR).number_format = "#,##0"

        # ── E: Trade Amount = grid_price × shares_per_grid ──────────────
        ws.cell(r, C_AMT).value = f'{if_}{b}*{P_SHR})'
        ws.cell(r, C_AMT).number_format = "#,##0.00"

        # ── F: Commission per leg = max(fixed_fee, amount × fee_rate) ───
        ws.cell(r, C_COM).value = f'{if_}MAX({P_FEE},{e}*{P_RATE}))'
        ws.cell(r, C_COM).number_format = "#,##0.00"

        # ── G: Shares Change (+shares for BUY, −shares for SELL, 0 for CURRENT)
        ws.cell(r, C_DSHP).value = (
            f'{if_}IF(C{r}="BUY",{P_SHR},IF(C{r}="SELL",-{P_SHR},0)))'
        )
        ws.cell(r, C_DSHP).number_format = '+#,##0;-#,##0;0'

        # ── H: Cumulative Shares = initial_shares + shares_per_grid × k ──
        # k > 0: added shares from BUY grids below; k < 0: removed by SELL grids above
        ws.cell(r, C_CSHP).value = f'{if_}{P_ISHP}+{P_SHR}*{k_expr})'
        ws.cell(r, C_CSHP).number_format = "#,##0"

        # ── I: Avg Cost Price ────────────────────────────────────────────
        # BUY / CURRENT rows (k >= 0):
        #   Weighted average = (initial_shares × current_price
        #                       + shares × k × (current_price − interval × (k+1)/2))
        #                     ÷ (initial_shares + shares × k)
        #   Derivation: each BUY adds shares at price (current − j×interval) for j=1..k
        #   Sum of BUY cost = shares × (k×current − interval × k(k+1)/2)
        #
        # SELL rows (k < 0): avg cost of remaining position is unchanged → return current_price
        ws.cell(r, C_AVG).value = (
            f'{if_}IF({k_expr}>=0,'
            f'({P_ISHP}*{P_CUR}+{P_SHR}*{k_expr}*({P_CUR}-{P_INT}*({k_expr}+1)/2))'
            f'/({P_ISHP}+{P_SHR}*{k_expr}),'
            f'{P_CUR}))'
        )
        ws.cell(r, C_AVG).number_format = "#,##0.000"

        # ── J: Market Value = cumulative_shares × grid_price ────────────
        ws.cell(r, C_MKT).value = f'{if_}{h}*{b})'
        ws.cell(r, C_MKT).number_format = "#,##0.00"

        # ── K: Gross Profit per round-trip = interval × shares ──────────
        # CURRENT row has no completed round-trip → N/A
        ws.cell(r, C_GRS).value = (
            f'{if_}IF(C{r}="CURRENT","N/A",{P_INT}*{P_SHR}))'
        )
        ws.cell(r, C_GRS).number_format = "#,##0.00"

        # ── L: Total Commission for round-trip = 2 × per-leg commission ─
        ws.cell(r, C_TCOM).value = (
            f'{if_}IF(C{r}="CURRENT","N/A",2*MAX({P_FEE},{e}*{P_RATE})))'
        )
        ws.cell(r, C_TCOM).number_format = "#,##0.00"

        # ── M: Net Profit = gross − total_commission ────────────────────
        ws.cell(r, C_NET).value = (
            f'{if_}IF(C{r}="CURRENT","N/A",{k_}-{l_}))'
        )
        ws.cell(r, C_NET).number_format = "#,##0.00"

        # ── N: Cumulative P&L (running sum; CURRENT row contributes 0) ──
        if r == DS:
            # First data row: seed the running sum
            ws.cell(r, C_CPNL).value = (
                f'{if_}IF(ISNUMBER({m}),{m},0))'
            )
        else:
            # Subsequent rows: add this row's net profit (or 0 if N/A)
            ws.cell(r, C_CPNL).value = (
                f'{if_}{np}+IF(ISNUMBER({m}),{m},0))'
            )
        ws.cell(r, C_CPNL).number_format = "#,##0.00"

        # ── Row styling ──────────────────────────────────────────────────
        for col in range(1, 15):
            c = ws.cell(r, col)
            c.border    = BORDER
            c.font      = _font(size=9)
            c.alignment = ALIGN_C if col in (C_NO, C_ACT, C_DSHP) else ALIGN_R
        ws.row_dimensions[r].height = 17


def _apply_cond_fmt(ws) -> None:
    """Apply conditional formatting rules to the grid data range."""
    DS = DATA_START
    all_cols  = f"A{DS}:N{DATA_END}"
    col_c     = f"C{DS}:C{DATA_END}"
    col_h     = f"H{DS}:H{DATA_END}"

    # Rule 1: CURRENT row → yellow fill  (applied first = highest priority in Excel)
    ws.conditional_formatting.add(all_cols, FormulaRule(
        formula=[f'$C{DS}="CURRENT"'], fill=F_YELLOW))

    # Rule 2: Net profit ≤ 0 → orange  (does not trigger on CURRENT since M = "N/A")
    ws.conditional_formatting.add(all_cols, FormulaRule(
        formula=[f'AND(ISNUMBER($M{DS}),$M{DS}<=0)'], fill=F_ORANGE))

    # Rule 3: Cumulative shares < 0 → red on column H  (over-sell error)
    ws.conditional_formatting.add(col_h, FormulaRule(
        formula=[f'AND(ISNUMBER(H{DS}),H{DS}<0)'], fill=F_RED))

    # Rule 4: BUY → light green on column C
    ws.conditional_formatting.add(col_c, FormulaRule(
        formula=[f'$C{DS}="BUY"'], fill=F_LGRN))

    # Rule 5: SELL → light red on column C
    ws.conditional_formatting.add(col_c, FormulaRule(
        formula=[f'$C{DS}="SELL"'], fill=F_LRED))


# ─── Utility ──────────────────────────────────────────────────────────────────

def _merged_row(ws, row: int, merge_range: str, value,
                fnt, fll, align) -> None:
    """Write a value into a merged row with optional font, fill, and alignment."""
    ws.merge_cells(merge_range)
    first_cell_addr = merge_range.split(":")[0]
    c = ws[first_cell_addr]
    c.value = value
    if fnt:   c.font      = fnt
    if fll:   c.fill      = fll
    if align: c.alignment = align


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "grid_trading_calculator.xlsx")
    build(output_path)
