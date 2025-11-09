import pandas as pd

def ic_by_month(f: pd.Series, r: pd.Series) -> pd.Series:
    df = pd.concat([f.rename("f"), r.rename("ret")], axis=1).dropna()
    if df.empty: return pd.Series(dtype=float)
    g = df.groupby([df.index.year, df.index.month]).apply(lambda d: d["f"].corr(d["ret"], method="spearman"))
    g.index = [f"{int(i[0])}-{int(i[1]):02d}" for i in g.index]
    return g

def ic_by_hour(f: pd.Series, r: pd.Series) -> pd.Series:
    df = pd.concat([f.rename("f"), r.rename("ret")], axis=1).dropna()
    if df.empty: return pd.Series(dtype=float)
    return df.groupby(df.index.hour).apply(lambda d: d["f"].corr(d["ret"], method="spearman"))

def ic_by_wday(f: pd.Series, r: pd.Series) -> pd.Series:
    df = pd.concat([f.rename("f"), r.rename("ret")], axis=1).dropna()
    if df.empty: return pd.Series(dtype=float)
    return df.groupby(df.index.dayofweek).apply(lambda d: d["f"].corr(d["ret"], method="spearman"))
