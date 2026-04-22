"""
Grid Trading Strategy Calculator.

Pure-math calculations for grid trading strategies:
- Suitability scoring based on volatility and trend
- Grid interval sizing (price range + grid count)
- Position sizing (shares per grid)
- Profit per round-trip calculation with fees
- Multiple strategy variants: short / medium / long-term
"""

from dataclasses import dataclass, field, asdict


# A-share fee structure (approximate, 2026)
# Buy: commission 0.025% (min 5 yuan) + transfer fee 0.001% (Shanghai only)
# Sell: commission 0.025% (min 5 yuan) + transfer fee 0.001% + stamp tax 0.05%
DEFAULT_FEE_RATE_BUY = 0.00025 + 0.00001   # 0.026%
DEFAULT_FEE_RATE_SELL = 0.00025 + 0.00001 + 0.0005  # 0.076%
MIN_COMMISSION = 5.0  # yuan, minimum per trade


@dataclass
class GridStrategy:
    """One grid trading strategy proposal."""
    name: str  # e.g. "Short-term Tight Grid"
    horizon: str  # "short-term" | "medium-term" | "long-term"
    lower_price: float
    upper_price: float
    grid_count: int
    grid_step: float  # price gap between grids
    grid_step_pct: float  # grid step as % of current price
    shares_per_grid: int
    capital_required: float  # total yuan needed
    profit_per_cycle: float  # yuan earned per one buy+sell round-trip
    profit_per_cycle_pct: float  # profit % per cycle (of capital deployed per grid)
    fees_per_cycle: float  # total fees eaten per round-trip
    break_even_move_pct: float  # minimum price move needed to break even
    estimated_cycles_per_month: float  # rough estimate based on volatility
    estimated_monthly_return_pct: float
    description: str = ""
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def compute_volatility(closes: list[float]) -> float:
    """Compute annualized volatility from close prices (simple stdev)."""
    if len(closes) < 2:
        return 0.0
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    daily_vol = var ** 0.5
    # Annualize assuming 252 trading days
    return daily_vol * (252 ** 0.5)


def compute_daily_range_pct(closes: list[float], window: int = 20) -> float:
    """Average daily range percentage over the window."""
    if len(closes) < 2:
        return 0.0
    recent = closes[-window:] if len(closes) >= window else closes
    daily_changes = [abs(recent[i] / recent[i - 1] - 1) for i in range(1, len(recent))]
    if not daily_changes:
        return 0.0
    return sum(daily_changes) / len(daily_changes) * 100


def assess_suitability(
    current_price: float,
    closes: list[float],
    rsi: float | None,
    sma_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
) -> tuple[int, str, list[str]]:
    """
    Assess whether a stock is suitable for grid trading.

    Returns:
        (score 0-100, verdict string, list of reasons)
    """
    score = 50
    reasons = []

    # 1. Volatility (grid needs movement)
    annual_vol = compute_volatility(closes) * 100  # as percentage
    if annual_vol >= 40:
        score += 20
        reasons.append(f"High volatility {annual_vol:.1f}% annually — ideal for grid profit generation")
    elif annual_vol >= 25:
        score += 10
        reasons.append(f"Moderate volatility {annual_vol:.1f}% annually — acceptable for grid trading")
    elif annual_vol >= 15:
        reasons.append(f"Low volatility {annual_vol:.1f}% annually — grid cycles will be infrequent")
    else:
        score -= 20
        reasons.append(f"Very low volatility {annual_vol:.1f}% annually — NOT suitable for grid")

    # 2. Trend strength (grid prefers sideways)
    if sma_20 and sma_50 and sma_200:
        trend_spread = abs(sma_20 - sma_200) / sma_200 * 100
        if trend_spread < 5:
            score += 15
            reasons.append(f"Sideways trend (SMA20 within {trend_spread:.1f}% of SMA200) — ideal for range-bound grid")
        elif trend_spread < 10:
            score += 5
            reasons.append(f"Weak trend (spread {trend_spread:.1f}%) — grid workable")
        elif trend_spread < 20:
            score -= 5
            reasons.append(f"Moderate trend (spread {trend_spread:.1f}%) — grid may underperform trend following")
        else:
            score -= 15
            reasons.append(f"Strong trend (spread {trend_spread:.1f}%) — grid will likely lag, NOT recommended")

    # 3. RSI in neutral zone preferred
    if rsi is not None:
        if 40 <= rsi <= 60:
            score += 10
            reasons.append(f"RSI {rsi:.1f} in neutral zone — good grid entry")
        elif rsi > 75:
            score -= 10
            reasons.append(f"RSI {rsi:.1f} overbought — risk of grid being caught at top")
        elif rsi < 25:
            score += 5
            reasons.append(f"RSI {rsi:.1f} oversold — could be grid accumulation opportunity")

    score = max(0, min(100, score))

    if score >= 70:
        verdict = "HIGHLY SUITABLE"
    elif score >= 50:
        verdict = "MODERATELY SUITABLE"
    elif score >= 30:
        verdict = "MARGINAL"
    else:
        verdict = "NOT RECOMMENDED"

    return score, verdict, reasons


def _calculate_profit_per_cycle(
    buy_price: float,
    sell_price: float,
    shares: int,
    fee_buy: float,
    fee_sell: float,
) -> tuple[float, float]:
    """
    Calculate profit and total fees for one round-trip.
    Returns: (net_profit, total_fees)
    """
    buy_cost = buy_price * shares
    sell_revenue = sell_price * shares

    buy_fee = max(buy_cost * fee_buy, MIN_COMMISSION)
    sell_fee = max(sell_revenue * fee_sell, MIN_COMMISSION)

    total_fees = buy_fee + sell_fee
    gross_profit = sell_revenue - buy_cost
    net_profit = gross_profit - total_fees

    return net_profit, total_fees


def _shares_for_budget(price: float, budget: float) -> int:
    """Compute number of shares (A-share lot = 100) that fit in budget."""
    import math
    if not math.isfinite(price) or price <= 0:
        return 0
    raw = int(budget / price)
    # Round down to multiples of 100 (A-share lot size)
    return (raw // 100) * 100


def build_strategy(
    name: str,
    horizon: str,
    current_price: float,
    annual_vol: float,
    lower_pct: float,
    upper_pct: float,
    grid_count: int,
    capital_per_grid: float,
    description: str,
) -> GridStrategy:
    """Build one grid strategy given the parameters."""
    lower_price = current_price * (1 - lower_pct / 100)
    upper_price = current_price * (1 + upper_pct / 100)
    grid_step = (upper_price - lower_price) / grid_count
    grid_step_pct = grid_step / current_price * 100

    shares_per_grid = _shares_for_budget(current_price, capital_per_grid)
    if shares_per_grid < 100:
        shares_per_grid = 100  # Minimum A-share lot

    # Profit calculation: buy at one grid, sell at next higher grid
    buy_price = current_price
    sell_price = current_price + grid_step
    net_profit, fees = _calculate_profit_per_cycle(
        buy_price, sell_price, shares_per_grid,
        DEFAULT_FEE_RATE_BUY, DEFAULT_FEE_RATE_SELL,
    )

    capital_deployed = buy_price * shares_per_grid
    profit_pct = (net_profit / capital_deployed * 100) if capital_deployed > 0 else 0

    # Break-even: min price move to cover fees (as % of buy price)
    be_move_pct = (fees / (shares_per_grid * buy_price)) * 100 if shares_per_grid > 0 else 0

    # Estimate cycles per month based on volatility and grid step
    # If daily vol ≈ annual_vol/sqrt(252), and we need grid_step_pct move,
    # expect roughly (daily_range / grid_step) cycles per day
    daily_range_pct = annual_vol / (252 ** 0.5)
    if grid_step_pct > 0:
        cycles_per_day = daily_range_pct / grid_step_pct * 0.3  # 0.3 = conservative factor
        cycles_per_month = max(0.1, cycles_per_day * 20)  # 20 trading days
    else:
        cycles_per_month = 0.0

    monthly_return_pct = profit_pct * cycles_per_month

    caveats = []
    if net_profit < 0:
        caveats.append(f"Grid step {grid_step_pct:.2f}% too small — fees exceed profit. NOT profitable.")
    if be_move_pct >= grid_step_pct:
        caveats.append(f"Break-even move {be_move_pct:.2f}% >= grid step {grid_step_pct:.2f}% — margin too thin")
    if shares_per_grid == 100 and capital_per_grid > current_price * 100 * 1.5:
        caveats.append("Capital per grid allows only minimum 100 shares — consider larger position")

    total_capital = capital_per_grid * grid_count

    return GridStrategy(
        name=name,
        horizon=horizon,
        lower_price=round(lower_price, 2),
        upper_price=round(upper_price, 2),
        grid_count=grid_count,
        grid_step=round(grid_step, 2),
        grid_step_pct=round(grid_step_pct, 3),
        shares_per_grid=shares_per_grid,
        capital_required=round(total_capital, 2),
        profit_per_cycle=round(net_profit, 2),
        profit_per_cycle_pct=round(profit_pct, 3),
        fees_per_cycle=round(fees, 2),
        break_even_move_pct=round(be_move_pct, 3),
        estimated_cycles_per_month=round(cycles_per_month, 1),
        estimated_monthly_return_pct=round(monthly_return_pct, 2),
        description=description,
        caveats=caveats,
    )


def generate_strategies(
    current_price: float,
    closes: list[float],
    capital_budget: float = 100_000,
) -> list[GridStrategy]:
    """Generate multiple grid strategy variants (short/medium/long term)."""
    annual_vol = compute_volatility(closes) * 100

    strategies = []

    # Short-term aggressive: tight grid, many grids, fast cycles
    strategies.append(build_strategy(
        name="Short-term Tight Grid",
        horizon="short-term",
        current_price=current_price,
        annual_vol=annual_vol,
        lower_pct=8,    # +/- 8% range
        upper_pct=8,
        grid_count=16,  # 1% step
        capital_per_grid=capital_budget / 16,
        description="Dense grid for rapid cycling in short-term range. Best for volatile, sideways stocks.",
    ))

    # Medium-term balanced
    strategies.append(build_strategy(
        name="Medium-term Balanced Grid",
        horizon="medium-term",
        current_price=current_price,
        annual_vol=annual_vol,
        lower_pct=15,   # +/- 15% range
        upper_pct=15,
        grid_count=15,  # 2% step
        capital_per_grid=capital_budget / 15,
        description="Balanced grid for 1-3 month holding. Wider range tolerates moderate trends.",
    ))

    # Long-term wide grid: wider range, fewer grids
    strategies.append(build_strategy(
        name="Long-term Wide Grid",
        horizon="long-term",
        current_price=current_price,
        annual_vol=annual_vol,
        lower_pct=25,   # +/- 25% range
        upper_pct=25,
        grid_count=10,  # 5% step
        capital_per_grid=capital_budget / 10,
        description="Wide grid for 6-12 month holding. Captures larger swings, fewer transactions.",
    ))

    # Asymmetric accumulation: more grids below, fewer above
    strategies.append(build_strategy(
        name="Accumulation Grid (Buy the Dip)",
        horizon="medium-term",
        current_price=current_price,
        annual_vol=annual_vol,
        lower_pct=20,   # -20% range
        upper_pct=10,   # +10% only
        grid_count=12,
        capital_per_grid=capital_budget / 12,
        description="Asymmetric grid biased toward accumulation. Good when expecting downside before recovery.",
    ))

    return strategies
