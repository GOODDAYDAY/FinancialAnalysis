"""HTML email templates for stock analysis reports."""

import html
from datetime import datetime


def _esc(value) -> str:
    """Escape HTML."""
    return html.escape(str(value)) if value is not None else "N/A"


def _color_for_recommendation(rec: str) -> str:
    return {
        "buy": "#16a34a",
        "sell": "#dc2626",
        "hold": "#ea580c",
    }.get(rec.lower(), "#6b7280")


def _color_for_score(score: float, max_val: float = 100, reverse: bool = False) -> str:
    """Green for good, red for bad. reverse=True for risk scores."""
    if score is None:
        return "#6b7280"
    pct = score / max_val
    if reverse:
        pct = 1 - pct
    if pct >= 0.7:
        return "#16a34a"
    elif pct >= 0.4:
        return "#ea580c"
    else:
        return "#dc2626"


def render_analysis_email(result: dict) -> tuple[str, str, str]:
    """
    Render a single stock analysis result into HTML email content.

    Returns:
        (subject, html_body, text_body)
    """
    ticker = result.get("ticker", "?")
    rec_obj = result.get("recommendation", {})
    rec = rec_obj.get("recommendation", "N/A")
    confidence = rec_obj.get("confidence", 0)
    horizon = rec_obj.get("investment_horizon", "N/A")

    md = result.get("market_data", {})
    sentiment = result.get("sentiment", {})
    fundamental = result.get("fundamental", {})
    quant = result.get("quant", {})
    grid = result.get("grid_strategy", {})
    risk = result.get("risk", {})
    debate_history = result.get("debate_history", [])

    subject = f"[Stock Analysis] {ticker} - {rec.upper()} ({confidence:.0%} confidence)"

    rec_color = _color_for_recommendation(rec)

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{_esc(subject)}</title></head>
<body style="font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #1f2937; background: #f9fafb;">

<div style="background: white; padding: 30px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">

<h1 style="margin: 0 0 5px 0; color: #111827;">Stock Analysis Report</h1>
<p style="color: #6b7280; margin: 0 0 25px 0;">Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

<!-- Header card -->
<div style="background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); padding: 25px; border-radius: 8px; margin-bottom: 25px;">
  <h2 style="margin: 0 0 10px 0; color: #111827; font-size: 32px;">{_esc(ticker)}</h2>
  <div style="font-size: 28px; font-weight: bold; color: {rec_color};">{_esc(rec.upper())}</div>
  <div style="color: #4b5563; margin-top: 5px;">Confidence: {confidence:.0%} | Horizon: {_esc(horizon)}</div>
</div>

<!-- Key metrics -->
<h3 style="color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Key Metrics</h3>
<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
  <tr>
    <td style="padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb;"><strong>Price</strong></td>
    <td style="padding: 10px; border: 1px solid #e5e7eb;">${_esc(md.get('current_price'))} ({_esc(md.get('price_change_pct'))}%)</td>
  </tr>
  <tr>
    <td style="padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb;"><strong>P/E Ratio</strong></td>
    <td style="padding: 10px; border: 1px solid #e5e7eb;">{_esc(md.get('pe_ratio'))}</td>
  </tr>
  <tr>
    <td style="padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb;"><strong>RSI(14)</strong></td>
    <td style="padding: 10px; border: 1px solid #e5e7eb;">{_esc(md.get('rsi_14'))}</td>
  </tr>
  <tr>
    <td style="padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb;"><strong>52W Range</strong></td>
    <td style="padding: 10px; border: 1px solid #e5e7eb;">{_esc(md.get('fifty_two_week_low'))} - {_esc(md.get('fifty_two_week_high'))}</td>
  </tr>
  <tr>
    <td style="padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb;"><strong>Sentiment</strong></td>
    <td style="padding: 10px; border: 1px solid #e5e7eb;">{_esc(sentiment.get('overall_label'))} ({_esc(sentiment.get('overall_score'))})</td>
  </tr>
  <tr>
    <td style="padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb;"><strong>Fundamental Health</strong></td>
    <td style="padding: 10px; border: 1px solid #e5e7eb;"><span style="color: {_color_for_score(fundamental.get('health_score'), 10)};">{_esc(fundamental.get('health_score'))}/10</span></td>
  </tr>
  <tr>
    <td style="padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb;"><strong>Quant Score</strong></td>
    <td style="padding: 10px; border: 1px solid #e5e7eb;">{_esc(quant.get('score'))}/100 ({_esc(quant.get('verdict'))})</td>
  </tr>
  <tr>
    <td style="padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb;"><strong>Risk</strong></td>
    <td style="padding: 10px; border: 1px solid #e5e7eb;"><span style="color: {_color_for_score(risk.get('risk_score'), 10, reverse=True)};">{_esc(risk.get('risk_score'))}/10 ({_esc(risk.get('risk_level'))})</span></td>
  </tr>
</table>

<!-- Recommendation reasoning -->
<h3 style="color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Reasoning</h3>
<p style="line-height: 1.6;">{_esc(rec_obj.get('reasoning'))}</p>

<!-- Supporting / dissenting -->
<table style="width: 100%; margin-bottom: 20px;">
  <tr>
    <td style="vertical-align: top; padding-right: 10px; width: 50%;">
      <h4 style="color: #16a34a;">Supporting Factors</h4>
      <ul>{"".join(f"<li>{_esc(f)}</li>" for f in rec_obj.get('supporting_factors', []))}</ul>
    </td>
    <td style="vertical-align: top; padding-left: 10px; width: 50%;">
      <h4 style="color: #dc2626;">Dissenting Factors</h4>
      <ul>{"".join(f"<li>{_esc(f)}</li>" for f in rec_obj.get('dissenting_factors', []))}</ul>
    </td>
  </tr>
</table>

<!-- Bull vs Bear debate -->
<h3 style="color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Bull vs Bear Debate</h3>
{_render_debate(debate_history)}

<!-- Grid Strategy -->
{_render_grid(grid)}

<!-- Risk factors -->
<h3 style="color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Risk Factors</h3>
<ul>{"".join(f"<li>{_esc(f)}</li>" for f in risk.get('risk_factors', []))}</ul>

<!-- Disclaimer -->
<div style="margin-top: 30px; padding: 15px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px; font-size: 13px; color: #78350f;">
  <strong>Disclaimer:</strong> {_esc(rec_obj.get('disclaimer', 'For educational purposes only. Not financial advice.'))}
</div>

</div>

<p style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 20px;">
  Generated by Multi-Agent Investment Research System (LangGraph + DeepSeek)
</p>

</body>
</html>"""

    text_body = (
        f"Stock Analysis: {ticker}\n"
        f"{'=' * 50}\n"
        f"Recommendation: {rec.upper()} (Confidence: {confidence:.0%}, Horizon: {horizon})\n\n"
        f"Price: ${md.get('current_price')} ({md.get('price_change_pct')}%)\n"
        f"P/E: {md.get('pe_ratio')} | RSI: {md.get('rsi_14')}\n"
        f"Sentiment: {sentiment.get('overall_label')} ({sentiment.get('overall_score')})\n"
        f"Fundamental Health: {fundamental.get('health_score')}/10\n"
        f"Quant Score: {quant.get('score')}/100 ({quant.get('verdict')})\n"
        f"Risk: {risk.get('risk_score')}/10 ({risk.get('risk_level')})\n\n"
        f"Reasoning: {rec_obj.get('reasoning', 'N/A')}\n\n"
        f"Disclaimer: {rec_obj.get('disclaimer', 'For educational purposes only.')}\n"
    )

    return subject, html_body, text_body


def _render_debate(history: list[dict]) -> str:
    if not history:
        return "<p>No debate available.</p>"
    out = ""
    for entry in history:
        role = entry.get("role", "?").upper()
        rnd = entry.get("round_number", "?")
        color = "#16a34a" if role == "BULL" else "#dc2626"
        out += f"""
        <div style="background: #f9fafb; padding: 15px; border-left: 4px solid {color}; margin-bottom: 10px; border-radius: 4px;">
          <div style="font-weight: bold; color: {color}; margin-bottom: 5px;">{role} - Round {rnd}</div>
          <p style="margin: 0 0 8px 0;">{_esc(entry.get('argument', ''))}</p>
          <ul style="margin: 5px 0; padding-left: 20px;">
            {"".join(f"<li>{_esc(p)}</li>" for p in entry.get('key_points', []))}
          </ul>
        </div>
        """
    return out


def _render_grid(grid: dict) -> str:
    if not grid or not grid.get("strategies"):
        return ""
    score = grid.get("score", 0)
    verdict = grid.get("verdict", "N/A")
    color = "#16a34a" if score >= 70 else "#ea580c" if score >= 50 else "#dc2626"

    out = f"""
    <h3 style="color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Grid Trading Strategies</h3>
    <p>Suitability: <span style="color: {color}; font-weight: bold;">{score}/100 ({verdict})</span> |
       Annual Volatility: {grid.get('annual_volatility_pct', 0)}%</p>
    <p><strong>Best Strategy:</strong> {_esc(grid.get('best_strategy_name', 'none'))}
       (~{grid.get('best_monthly_return_pct', 0)}%/month)</p>
    <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
      <tr style="background: #f3f4f6;">
        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Strategy</th>
        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Range</th>
        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">Grids</th>
        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">Shares</th>
        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">Profit/Cycle</th>
        <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">Est. Monthly</th>
      </tr>
    """
    for s in grid["strategies"]:
        out += f"""
        <tr>
          <td style="padding: 8px; border: 1px solid #e5e7eb;">{_esc(s['name'])}<br><small style="color: #6b7280;">{_esc(s['horizon'])}</small></td>
          <td style="padding: 8px; border: 1px solid #e5e7eb;">{s['lower_price']} - {s['upper_price']}</td>
          <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">{s['grid_count']}</td>
          <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">{s['shares_per_grid']}</td>
          <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">{s['profit_per_cycle']} CNY</td>
          <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">{s['estimated_monthly_return_pct']}%</td>
        </tr>
        """
    out += "</table>"
    return out


def render_batch_summary(results: list[dict]) -> tuple[str, str, str]:
    """
    Render a batch summary email when analyzing multiple stocks.

    Returns:
        (subject, html_body, text_body)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"[Stock Watchlist] Daily Analysis Summary - {timestamp}"

    rows = ""
    text_lines = [f"Stock Watchlist Summary - {timestamp}", "=" * 60]
    for result in results:
        ticker = result.get("ticker", "?")
        rec = result.get("recommendation", {}).get("recommendation", "N/A")
        conf = result.get("recommendation", {}).get("confidence", 0)
        price = result.get("market_data", {}).get("current_price", "N/A")
        change = result.get("market_data", {}).get("price_change_pct", 0)
        risk_score = result.get("risk", {}).get("risk_score", "N/A")
        quant_score = result.get("quant", {}).get("score", "N/A")

        color = _color_for_recommendation(rec)
        rows += f"""
        <tr>
          <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>{_esc(ticker)}</strong></td>
          <td style="padding: 10px; border: 1px solid #e5e7eb;">${_esc(price)}</td>
          <td style="padding: 10px; border: 1px solid #e5e7eb;">{_esc(change)}%</td>
          <td style="padding: 10px; border: 1px solid #e5e7eb;"><span style="color: {color}; font-weight: bold;">{_esc(rec.upper())}</span></td>
          <td style="padding: 10px; border: 1px solid #e5e7eb;">{conf:.0%}</td>
          <td style="padding: 10px; border: 1px solid #e5e7eb;">{_esc(quant_score)}/100</td>
          <td style="padding: 10px; border: 1px solid #e5e7eb;">{_esc(risk_score)}/10</td>
        </tr>
        """
        text_lines.append(
            f"  {ticker:12} ${price:>10} ({change:+.2f}%)  {rec.upper():4} {conf:.0%}  Quant:{quant_score}  Risk:{risk_score}"
        )

    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #1f2937;">
<h1>Daily Stock Watchlist Summary</h1>
<p style="color: #6b7280;">Generated {timestamp}</p>
<table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
  <tr style="background: #f3f4f6;">
    <th style="padding: 10px; border: 1px solid #e5e7eb; text-align: left;">Ticker</th>
    <th style="padding: 10px; border: 1px solid #e5e7eb; text-align: left;">Price</th>
    <th style="padding: 10px; border: 1px solid #e5e7eb; text-align: left;">Change</th>
    <th style="padding: 10px; border: 1px solid #e5e7eb; text-align: left;">Action</th>
    <th style="padding: 10px; border: 1px solid #e5e7eb; text-align: left;">Confidence</th>
    <th style="padding: 10px; border: 1px solid #e5e7eb; text-align: left;">Quant</th>
    <th style="padding: 10px; border: 1px solid #e5e7eb; text-align: left;">Risk</th>
  </tr>
  {rows}
</table>
<p style="margin-top: 30px; padding: 15px; background: #fef3c7; border-left: 4px solid #f59e0b; font-size: 13px; color: #78350f;">
  <strong>Disclaimer:</strong> This analysis is for educational and informational purposes only. Not financial advice.
</p>
</body></html>"""

    text_body = "\n".join(text_lines)
    return subject, html_body, text_body
