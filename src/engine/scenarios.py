"""
Calibrates a simple mean-reverting (Ornstein-Uhlenbeck style) rate model
from REAL historical SOFR data, then simulates many random future paths.

The model: next_rate = current_rate + kappa*(theta - current_rate) + shock
  - kappa: mean-reversion speed (how strongly rates get pulled back toward
    the long-run average each quarter)
  - theta: the long-run average rate reverts toward
  - shock: random noise, drawn from a normal distribution whose spread
    (sigma) matches real historical quarter-to-quarter SOFR volatility

Calibration method: this is mathematically equivalent to a simple linear
regression of (change in rate) on (previous rate) - a completely standard
way to fit this kind of model, done here with plain numpy, no need for
scipy or any specialized statistics package.
"""

import numpy as np


def calibrate_ou(quarterly_values):
    """
    Fits kappa, theta, sigma from a real historical quarterly rate series.

    Regression: dx_t = a + b * x_(t-1) + noise
    Then: kappa = -b, theta = a / kappa, sigma = std dev of residuals

    Falls back to a reasonable default kappa if the fitted value comes out
    zero or negative (meaning the data didn't show clear mean reversion
    over this window) - explicitly flagged when that happens, rather than
    silently using a nonsensical calibration.
    """
    x = np.array(quarterly_values[:-1])
    dx = np.array(quarterly_values[1:]) - x

    slope, intercept = np.polyfit(x, dx, 1)
    kappa = -slope
    fallback_used = False

    if kappa <= 0:
        kappa = 0.15  # reasonable illustrative default
        theta = float(np.mean(quarterly_values))
        fallback_used = True
    else:
        theta = intercept / kappa

    residuals = dx - (slope * x + intercept)
    sigma = float(np.std(residuals, ddof=1))

    return {"kappa": float(kappa), "theta": float(theta), "sigma": sigma, "fallback_used": fallback_used}


def simulate_paths(current_value, kappa, theta, sigma, horizon_periods, n_paths, floor=0.0, seed=42):
    """
    Simulates n_paths random future rate paths, horizon_periods steps
    ahead, starting from current_value.

    floor: rates are held at this minimum (default 0%) - a simplifying
    assumption, since deeply negative rates are historically rare for the
    US and modeling them isn't the point of this exercise.

    seed: fixed by default so results are REPRODUCIBLE - re-running this
    gives the same "random" paths every time, which matters for being
    able to debug and explain a specific result rather than getting a
    different answer on every run.
    """
    rng = np.random.default_rng(seed)
    paths = []

    for _ in range(n_paths):
        path = [current_value]
        rate = current_value
        for _ in range(horizon_periods):
            shock = rng.normal(0, sigma)
            rate = rate + kappa * (theta - rate) + shock
            rate = max(rate, floor)
            path.append(rate)
        paths.append(path)

    return paths
