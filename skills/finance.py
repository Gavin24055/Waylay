"""
J — Finance Skills
Expense logging, budget tracking, savings, stock prices, finance reports.
"""

import logging
from skills.loader import skill

logger = logging.getLogger("j.skills.finance")


def _get_db():
    from memory.structured import StructuredMemory
    return StructuredMemory()


@skill
def log_expense(amount_inr: float, category: str, description: str = None, method: str = "upi") -> str:
    """Log an expense."""
    db = _get_db()
    db.log_expense(amount_inr, category, description, method)
    logger.info("Logged expense: ₹%.0f for %s (%s)", amount_inr, category, description)
    return f"Logged ₹{amount_inr:.0f} under {category}" + (f" — {description}" if description else "")


@skill
def budget_status(month: str = None) -> str:
    """Get budget vs actual spending for a month."""
    db = _get_db()
    budgets = db.budget_status(month)
    if not budgets:
        return "No budgets set up yet. Tell me your monthly budget categories and I'll track them."

    lines = ["Budget status:"]
    for b in budgets:
        remaining = b["budget_inr"] - b["spent_inr"]
        pct = (b["spent_inr"] / b["budget_inr"] * 100) if b["budget_inr"] > 0 else 0
        status = "✅" if remaining > 0 else "🔴"
        lines.append(
            f"  {status} {b['category']}: ₹{b['spent_inr']:.0f} / ₹{b['budget_inr']:.0f} ({pct:.0f}%)"
        )
    return "\n".join(lines)


@skill
def savings_progress() -> str:
    """Check progress on savings goals."""
    db = _get_db()
    goals = db.savings_progress()
    if not goals:
        return "No savings goals set. Want to create one?"

    lines = ["Savings goals:"]
    for g in goals:
        pct = (g["current_inr"] / g["target_inr"] * 100) if g["target_inr"] > 0 else 0
        bar_filled = int(pct / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        deadline = f" (deadline: {g['deadline']})" if g.get("deadline") else ""
        lines.append(
            f"  {g['name']}: ₹{g['current_inr']:.0f} / ₹{g['target_inr']:.0f} [{bar}] {pct:.0f}%{deadline}"
        )
    return "\n".join(lines)


@skill
def stock_price(symbol: str) -> str:
    """Get current stock price using yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("regularMarketPreviousClose", 0)
        name = info.get("shortName", symbol)
        currency = info.get("currency", "")

        if price is None:
            # Try fast_info
            try:
                price = ticker.fast_info.get("last_price")
            except Exception:
                return f"Couldn't fetch price for {symbol}"

        if price and prev_close:
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            direction = "📈" if change >= 0 else "📉"
            return f"{direction} {name} ({symbol}): {currency} {price:.2f} ({change:+.2f}, {change_pct:+.1f}%)"
        elif price:
            return f"{name} ({symbol}): {currency} {price:.2f}"
        else:
            return f"Couldn't fetch price for {symbol}"

    except Exception as e:
        logger.error("Stock price fetch failed for %s: %s", symbol, e)
        return f"Stock lookup failed: {e}"


@skill
def add_stock_alert(symbol: str, above: float = None, below: float = None) -> str:
    """Add a stock price alert."""
    db = _get_db()
    db.add_stock_alert(symbol, above, below)
    parts = [f"Alert set for {symbol.upper()}:"]
    if above:
        parts.append(f"  Notify when above ₹{above:.2f}")
    if below:
        parts.append(f"  Notify when below ₹{below:.2f}")
    return "\n".join(parts)


@skill
def finance_report(month: str = None) -> str:
    """Generate a monthly finance report."""
    db = _get_db()
    report = db.finance_report(month)

    if report["total_spent"] == 0:
        return f"No expenses recorded for {report['month']}."

    lines = [f"Finance Report — {report['month']}:", f"  Total spent: ₹{report['total_spent']:.0f}", ""]
    for cat in report["by_category"]:
        lines.append(f"  {cat['category']}: ₹{cat['total']:.0f} ({cat['count']} transactions)")

    return "\n".join(lines)
