"""Pure calculation layer. All rates are decimals, not percentage points."""
from dataclasses import dataclass, asdict
from math import isfinite

@dataclass(frozen=True)
class Inputs:
    beta: float
    tax: float
    erp: float
    debt: float
    us_yield: float
    foreign_yield: float
    usd_spread: float
    foreign_spread: float = None


def calculate(x):
    values = asdict(x)
    if any(not isfinite(v) for v in values.values() if v is not None):
        raise ValueError('Inputs must be finite.')
    if not 0 <= x.debt < 1 or not 0 <= x.tax <= 1:
        raise ValueError('Debt must be in [0,1); tax in [0,1].')
    if min(x.beta, x.erp, x.usd_spread) < 0 or (x.foreign_spread is not None and x.foreign_spread < 0):
        raise ValueError('Beta, ERP and credit spreads must be nonnegative.')
    if min(x.us_yield, x.foreign_yield) <= -1:
        raise ValueError('Government yields must exceed -100%.')
    bl = x.beta * (1 + (1-x.tax)*x.debt/(1-x.debt))
    q = (1+x.foreign_yield)/(1+x.us_yield)
    ke = x.us_yield + bl*x.erp
    kd = x.us_yield + x.usd_spread
    fs = x.usd_spread*q if x.foreign_spread is None else x.foreign_spread
    kef = (1+ke)*q-1
    kdf = x.foreign_yield+fs
    return dict(levered_beta=bl, conversion_factor=q, foreign_spread=fs,
                usd_equity=ke, usd_debt=kd, usd_wacc=(1-x.debt)*ke+x.debt*kd*(1-x.tax),
                foreign_equity=kef, foreign_debt=kdf,
                foreign_wacc=(1-x.debt)*kef+x.debt*kdf*(1-x.tax))
