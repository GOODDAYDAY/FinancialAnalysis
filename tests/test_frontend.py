"""
Playwright 前端测试 — 操控浏览器，输入股票查询，验证页面输出。
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from playwright.sync_api import sync_playwright


STREAMLIT_URL = "http://localhost:8501"


def test_frontend_stock(page, query: str, expected_ticker: str, test_name: str):
    """在浏览器中输入查询，等待结果，验证页面内容。"""
    print(f"\n{'='*60}")
    print(f"[Frontend] {test_name}: \"{query}\"")
    print(f"{'='*60}")

    start = time.time()

    # Navigate to app
    page.goto(STREAMLIT_URL, wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)

    # Find chat input and type query
    chat_input = page.locator('textarea[data-testid="stChatInputTextArea"]')
    chat_input.fill(query)
    chat_input.press("Enter")

    # Wait for response (up to 120s for LLM calls)
    print(f"  等待 Agent 分析中...")
    try:
        # Wait for the spinner to appear and then disappear
        page.wait_for_selector('text="Agents are analyzing"', timeout=10000)
    except Exception:
        pass  # Spinner might be too fast to catch

    # Wait for analysis to complete — look for "Recommendation" or "Analysis Result" in page
    try:
        page.wait_for_selector('text="Analysis Result"', timeout=120000)
    except Exception:
        try:
            page.wait_for_selector('text="Recommendation"', timeout=30000)
        except Exception:
            pass

    elapsed = time.time() - start

    # Check FULL page HTML (not just visible viewport)
    content = page.content()
    found_ticker = expected_ticker in content or "Analysis Result" in content
    has_recommendation = any(w in content.lower() for w in ["buy", "hold", "sell"])
    has_debate = "bull" in content.lower() and "bear" in content.lower()
    has_disclaimer = "disclaimer" in content.lower() or ("not" in content.lower() and "financial advice" in content.lower())
    has_error = "NameError" in content or "Traceback" in content

    print(f"  Ticker 显示: {'YES' if found_ticker else 'NO'}")
    print(f"  推荐显示: {'YES' if has_recommendation else 'NO'}")
    print(f"  辩论显示: {'YES' if has_debate else 'NO'}")
    print(f"  免责声明: {'YES' if has_disclaimer else 'NO'}")
    print(f"  错误: {'YES' if has_error else 'NO'}")
    print(f"  耗时: {elapsed:.1f}s")

    # Take screenshot
    screenshot_path = f"tests/screenshots/{expected_ticker}_{int(time.time())}.png"
    os.makedirs("tests/screenshots", exist_ok=True)
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"  截图: {screenshot_path}")

    result = {
        "test": test_name,
        "query": query,
        "ticker": expected_ticker,
        "found_ticker": found_ticker,
        "has_recommendation": has_recommendation,
        "has_debate": has_debate,
        "has_disclaimer": has_disclaimer,
        "has_error": has_error,
        "time": round(elapsed, 1),
        "pass": found_ticker and has_recommendation and not has_error,
    }

    status = "PASS" if result["pass"] else "FAIL"
    print(f"  结果: {status}")
    return result


def run_frontend_tests(stocks: list[dict]):
    """批量跑前端测试。"""
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        for stock in stocks:
            try:
                r = test_frontend_stock(
                    page,
                    query=stock["query"],
                    expected_ticker=stock["ticker"],
                    test_name=stock["name"],
                )
                results.append(r)
            except Exception as e:
                print(f"  EXCEPTION: {e}")
                results.append({
                    "test": stock["name"], "ticker": stock["ticker"],
                    "pass": False, "error": str(e), "time": 0,
                })

            # Refresh page between tests for clean state
            page.goto(STREAMLIT_URL, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)

        browser.close()

    return results


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    stocks = [
        {"query": "分析一下贵州茅台", "ticker": "600519.SS", "name": "贵州茅台"},
        {"query": "Analyze 000858.SZ", "ticker": "000858.SZ", "name": "五粮液"},
    ]

    results = run_frontend_tests(stocks)

    print(f"\n{'#'*60}")
    print(f"  前端测试汇总")
    print(f"{'#'*60}")
    passed = sum(1 for r in results if r.get("pass"))
    total = len(results)
    for r in results:
        status = "PASS" if r.get("pass") else "FAIL"
        print(f"  [{status}] {r.get('test')} ({r.get('ticker')}) - {r.get('time')}s")
    print(f"\n  总计: {passed}/{total} 通过")
