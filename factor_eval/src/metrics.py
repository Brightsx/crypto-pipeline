import numpy as np
import pandas as pd

def pearson_ic(x: pd.Series, y: pd.Series) -> float:
    if x.size < 2: return np.nan
    return x.corr(y, method="pearson")

def spearman_ic(x: pd.Series, y: pd.Series) -> float:
    if x.size < 2: return np.nan
    return x.corr(y, method="spearman")

def newey_west_beta(x: pd.Series, y: pd.Series, lags: int = 10):
    df = pd.concat([x, y], axis=1).dropna()
    df.columns = ["x", "y"]; n = len(df)
    if n < 3:
        return dict(alpha=np.nan, beta=np.nan, r2=np.nan, t_beta=np.nan, p_beta=np.nan, n=n)
    X = np.vstack([np.ones(n), df["x"].values]).T
    Y = df["y"].values
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta_hat = XtX_inv @ (X.T @ Y)  # [a, b]
    resid = Y - X @ beta_hat
    Z = X * resid[:, None]
    S = Z.T @ Z
    for k in range(1, min(lags, n-1)+1):
        w = 1 - k/(lags+1)
        G = Z[k:].T @ Z[:-k]
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv
    b = beta_hat[1]; var_b = cov[1,1]
    se_b = np.sqrt(var_b) if var_b >= 0 else np.nan
    t_b = b / se_b if (se_b and not np.isnan(se_b) and se_b != 0) else np.nan
    ss_tot = ((Y - Y.mean())**2).sum()
    ss_res = (resid**2).sum()
    r2 = 1 - ss_res/ss_tot if ss_tot > 0 else np.nan
    try:
        from scipy.stats import norm
        p_b = 2*(1 - norm.cdf(abs(t_b))) if not np.isnan(t_b) else np.nan
    except Exception:
        p_b = np.nan
    return dict(alpha=beta_hat[0], beta=b, r2=r2, t_beta=t_b, p_beta=p_b, n=n)
