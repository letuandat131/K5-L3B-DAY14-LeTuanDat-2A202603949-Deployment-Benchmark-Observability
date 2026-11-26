"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r, redis_healthy

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_in_memory_cost = 0.0


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    budget = settings.daily_budget_usd
    current_cost = 0.0
    if redis_healthy():
        try:
            val = r.get("cost:total")
            if val:
                current_cost = float(val)
        except Exception:
            current_cost = _in_memory_cost
    else:
        current_cost = _in_memory_cost

    if current_cost >= budget:
        raise HTTPException(
            status_code=402,
            detail=f"Budget exceeded: spent ${current_cost:.6f} >= limit ${budget:.6f}"
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    global _in_memory_cost
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    if cost <= 0:
        cost = 0.0001
    if redis_healthy():
        try:
            r.incrbyfloat("cost:total", cost)
        except Exception:
            _in_memory_cost += cost
    else:
        _in_memory_cost += cost
    return cost
