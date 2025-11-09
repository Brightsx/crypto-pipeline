import numpy as np
import pandas as pd

def winsorize_series(s: pd.Series, cfg: dict) -> pd.Series:
    if not cfg.get("enabled", False): return s
    method = cfg.get("method", "quantile")
    if method == "quantile":
        lo = s.quantile(cfg.get("q_low", 0.01))
        hi = s.quantile(cfg.get("q_high", 0.99))
        return s.clip(lo, hi)
    if method == "mad":
        med = s.median()
        mad = np.median(np.abs(s - med))
        k = cfg.get("mad_k", 5.0)
        return s.clip(med - k*mad, med + k*mad)
    return s

def standardize_series(s: pd.Series, cfg: dict) -> pd.Series:
    if not cfg.get("enabled", False): return s
    mu, sd = s.mean(), s.std(ddof=0)
    if sd == 0 or np.isnan(sd): return s*0.0
    return (s - mu) / sd

def prepare_factors(factors: pd.DataFrame, pp_cfg: dict, logger) -> pd.DataFrame:
    out = factors.copy()
    wcfg, scfg = pp_cfg.get("winsor", {}), pp_cfg.get("standardize", {})
    for c in out.columns:
        s = winsorize_series(out[c], wcfg)
        s = standardize_series(s, scfg)
        out[c] = s
    return out
