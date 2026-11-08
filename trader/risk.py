"""Risk rules. These run BEFORE any order and can't be overridden by the AI layer."""


def daily_loss_exceeded(equity: float, last_equity: float, limit_pct: float) -> bool:
    """True if today's equity drop is bigger than the limit (kill switch for new buys)."""
    if last_equity <= 0:
        return False
    return (equity - last_equity) / last_equity <= -limit_pct


def position_size(equity: float, cash: float, max_position_pct: float) -> float:
    """Dollar size of a new position: capped by equity share, and never uses the last 5% of cash."""
    return round(max(0.0, min(equity * max_position_pct, cash * 0.95)), 2)


def stop_loss_hit(unrealized_plpc: float, stop_loss_pct: float) -> bool:
    """unrealized_plpc is a fraction, e.g. -0.08 means down 8%."""
    return unrealized_plpc <= -stop_loss_pct
