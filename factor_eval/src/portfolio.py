import numpy as np
import pandas as pd

def _global_quantile_bins(x: pd.Series, q: int) -> pd.Series:
    ranks = x.rank(method="first", pct=True)
    return np.ceil(ranks * q).clip(1, q).astype("Int64")

def quantile_backtest(f: pd.Series, r: pd.Series, q: int = 5, compute_turnover: bool = True):
    df = pd.concat([f.rename("f"), r.rename("ret")], axis=1).dropna()
    if df.empty: return pd.DataFrame()
    bins = _global_quantile_bins(df["f"], q)
    df = df.assign(bin=bins.values)
    rows = []
    for k in range(1, q+1):
        sub = df.loc[df["bin"] == k, "ret"]
        n = sub.size; mu = sub.mean(); sd = sub.std(ddof=1)
        t = mu / (sd/np.sqrt(n)) if (n>1 and sd>0) else np.nan
        rows.append(dict(bin=int(k), n=int(n), mean=mu, std=sd, t=t))
    res = pd.DataFrame(rows)
    if not res.empty:
        top = res.iloc[-1]; bot = res.iloc[0]
        res.attrs["ls_mean"] = top["mean"] - bot["mean"]
        if top["std"]==top["std"] and bot["std"]==bot["std"] and min(top["n"], bot["n"])>1:
            ls_std = (top["std"]**2 + bot["std"]**2) ** 0.5
            res.attrs["ls_t"] = (res.attrs["ls_mean"] / (ls_std / np.sqrt(min(top["n"], bot["n"])))) if ls_std>0 else np.nan
        else:
            res.attrs["ls_t"] = np.nan
        res.attrs["top_only_mean"] = top["mean"]
        res.attrs["top_only_t"] = top["t"]
    if compute_turnover:
        turns = (df["bin"] != df["bin"].shift(1)).astype(float)
        res.attrs["turnover"] = float(turns.mean())
    return res
