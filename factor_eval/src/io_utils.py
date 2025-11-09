import re
import pandas as pd

def _select_columns(df: pd.DataFrame, include):
    if not include:
        return df
    cols = set()
    for pat in include:
        try:
            r = re.compile(pat)
            for c in df.columns:
                if r.search(c): cols.add(c)
        except re.error:
            if pat in df.columns: cols.add(pat)
    return df.loc[:, sorted(cols)]

def read_and_align(factors_path, returns_path, include_factors, include_returns, how="inner"):
    f = pd.read_parquet(factors_path)
    r = pd.read_parquet(returns_path)
    if not isinstance(f.index, pd.DatetimeIndex):
        f.index = pd.to_datetime(f.index, utc=True)
    if not isinstance(r.index, pd.DatetimeIndex):
        r.index = pd.to_datetime(r.index, utc=True)
    f = _select_columns(f, include_factors)
    r = _select_columns(r, include_returns)
    if how == "inner":
        idx = f.index.intersection(r.index)
        return f.loc[idx].sort_index(), r.loc[idx].sort_index()
    idx = f.index.union(r.index)
    return f.reindex(idx).sort_index(), r.reindex(idx).sort_index()
