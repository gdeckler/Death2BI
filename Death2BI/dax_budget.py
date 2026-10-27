"""Server-controlled limits and diagnostics shared by a visual's DAX contexts."""
import os
import time


def limits():
    seconds = float(os.environ.get('D2PBI_DAX_SECONDS', '60'))
    steps = int(os.environ.get('D2PBI_DAX_STEPS', '5000000'))
    if not 0 < seconds <= 300 or not 0 < steps <= 100000000:
        raise ValueError('DAX limits must be above zero, at most 300 seconds and 100,000,000 steps.')
    return seconds, steps


class DaxBudgetExceeded(RuntimeError):
    pass


def check_budget(budget, increment=0):
    budget['steps'] += increment
    now = time.monotonic()
    elapsed = now - budget.setdefault('started', now)
    reason = 'time' if now > budget['deadline'] else 'step' if budget['steps'] > budget.get('max_steps', 5000000) else None
    if reason:
        limit = f"{budget.get('seconds', 8):g} seconds" if reason == 'time' else f"{budget.get('max_steps', 5000000):,} steps"
        location = budget.get('location', 'DAX expression')
        raise DaxBudgetExceeded(f"Python DAX {reason} limit exceeded ({limit}). Elapsed: {elapsed:.2f}s; evaluation steps: {budget['steps']:,}. Evaluating {location}.")
