import argparse, logging, sys, time
from pathlib import Path
import numpy as np, pandas as pd

from .config_loader import load_config
from .io_utils import read_and_align
from .preprocess import prepare_factors
from .metrics import pearson_ic, spearman_ic, newey_west_beta
from .portfolio import quantile_backtest
from .stability import ic_by_month, ic_by_hour, ic_by_wday
from .utils import timed, parse_delay_period
from .plots import (
    plot_ic_by_month, plot_ic_by_hour, plot_ic_by_wday, plot_ic_decay, plot_quantile_bars
)

def setup_logger(cfg):
    logger = logging.getLogger("factor_eval")
    logger.handlers = []
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(getattr(logging, cfg.get("level_console", "INFO").upper()))
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    logger.addHandler(ch)
    Path(cfg.get("log_file","logs/factor_eval.log")).parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(cfg.get("log_file","logs/factor_eval.log"), encoding="utf-8")
    fh.setLevel(getattr(logging, cfg.get("level_file","DEBUG").upper()))
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s | %(message)s"))
    logger.addHandler(fh)
    return logger


def evaluate_symbol(symbol, cfg, logger):
    import numpy as np
    import pandas as pd
    logger.info(f"==== Evaluating {symbol} ====")
    fpath = cfg["paths"]["factors_pattern"].format(symbol=symbol)
    rpath = cfg["paths"]["returns_pattern"].format(symbol=symbol)
    include_f, include_r = cfg["columns"]["include_factors"], cfg["columns"]["include_returns"]

    with timed(f"read & align {symbol}", logger):
        f_raw, r_raw = read_and_align(fpath, rpath, include_f, include_r, cfg['preprocess']['join_how'])
    logger.info(f"{symbol}: {f_raw.shape} factors, {r_raw.shape} returns")

    # time filter
    tf = cfg["preprocess"].get("time_filter",{})
    s,e = tf.get("start_time"), tf.get("end_time")
    if s or e:
        s = pd.to_datetime(s, utc=True) if s else None
        e = pd.to_datetime(e, utc=True) if e else None
        if s: f_raw, r_raw = f_raw.loc[f_raw.index>=s], r_raw.loc[r_raw.index>=s]
        if e: f_raw, r_raw = f_raw.loc[f_raw.index<e], r_raw.loc[r_raw.index<e]
        logger.info(f"{symbol}: time filtered to {s} ~ {e}")

    with timed(f"preprocess factors ({symbol})", logger):
        f = prepare_factors(f_raw, cfg["preprocess"], logger)

    per_dir = Path("reports/per_symbol")/symbol
    stab_dir, quant_dir, plot_dir = per_dir/"stability", per_dir/"quantiles", per_dir/"plots"
    for d in [stab_dir, quant_dir, plot_dir]: d.mkdir(parents=True, exist_ok=True)

    all_summary = []
    all_month, all_hour, all_wday, all_decay = [], [], [], []

    # iterate per factor
    for f_idx, fcol in enumerate(f.columns, 1):
        logger.info(f"[{symbol}] factor {f_idx}/{len(f.columns)}: {fcol}")
        fac_month, fac_hour, fac_wday, fac_decay = [], [], [], []
        fac_pairs = 0

        for rcol in r_raw.columns:
            mask = (~f[fcol].isna()) & (~r_raw[rcol].isna())
            if mask.sum() < cfg["preprocess"]["min_samples"]:
                continue
            x, y = f.loc[mask, fcol], r_raw.loc[mask, rcol]
            delay, period = parse_delay_period(rcol)
            icp, ics = pearson_ic(x,y), spearman_ic(x,y)
            reg = newey_west_beta(x,y) if cfg["evaluation"]["regression"]["newey_west"].get("enabled",True) else {}
            all_summary.append(dict(symbol=symbol,factor=fcol,ret_col=rcol,ic_pearson=icp,ic_spearman=ics,**reg))

            # stability rows (Spearman)
            s = ic_by_month(x,y)
            for ym, v in s.items():
                fac_month.append(dict(metric="spearman",symbol=symbol,factor=fcol,ret_col=rcol,ym=ym,value=v))
            s = ic_by_hour(x,y)
            for h, v in s.items():
                fac_hour.append(dict(metric="spearman",symbol=symbol,factor=fcol,ret_col=rcol,hour=int(h),value=v))
            s = ic_by_wday(x,y)
            for d, v in s.items():
                fac_wday.append(dict(metric="spearman",symbol=symbol,factor=fcol,ret_col=rcol,wday=int(d),value=v))
            if cfg["stability"].get("ic_decay", True):
                fac_decay.append(dict(metric="spearman",symbol=symbol,factor=fcol,delay=delay,period=period,value=ics))

            # Pearson版本稳定性
            s = ic_by_month(x,y,method="pearson") if "method" in ic_by_month.__code__.co_varnames else ic_by_month(x,y)
            for ym, v in s.items():
                fac_month.append(dict(metric="pearson",symbol=symbol,factor=fcol,ret_col=rcol,ym=ym,value=v))
            s = ic_by_hour(x,y,method="pearson") if "method" in ic_by_hour.__code__.co_varnames else ic_by_hour(x,y)
            for h, v in s.items():
                fac_hour.append(dict(metric="pearson",symbol=symbol,factor=fcol,ret_col=rcol,hour=int(h),value=v))
            s = ic_by_wday(x,y,method="pearson") if "method" in ic_by_wday.__code__.co_varnames else ic_by_wday(x,y)
            for d, v in s.items():
                fac_wday.append(dict(metric="pearson",symbol=symbol,factor=fcol,ret_col=rcol,wday=int(d),value=v))
            if cfg["stability"].get("ic_decay", True):
                fac_decay.append(dict(metric="pearson",symbol=symbol,factor=fcol,delay=delay,period=period,value=icp))

            # quantile plot
            if cfg["evaluation"]["quantile"].get("enabled", True):
                q = int(cfg["evaluation"]["quantile"]["q"])
                qres = quantile_backtest(x,y,q=q, compute_turnover=cfg["evaluation"]["quantile"].get("compute_turnover", True))
                if not qres.empty:
                    qpath = quant_dir / f"{fcol}__{rcol}.csv"
                    qres.to_csv(qpath, index=False)
                    if cfg["output"].get("plots", True):
                        qplot_dir = plot_dir / fcol / "quantiles"
                        plot_quantile_bars(qres, fcol, rcol, str(qplot_dir), logger)
            fac_pairs += 1

        # 绘图输出
        import pandas as pd
        if cfg["output"].get("plots", True):
            for metric in ["spearman", "pearson"]:
                df_m = pd.DataFrame([r for r in fac_month if r["metric"] == metric])
                df_h = pd.DataFrame([r for r in fac_hour if r["metric"] == metric])
                df_w = pd.DataFrame([r for r in fac_wday if r["metric"] == metric])
                df_d = pd.DataFrame([r for r in fac_decay if r["metric"] == metric])
                base_dir = plot_dir / fcol / metric
                if not df_m.empty: plot_ic_by_month(df_m, symbol, str(base_dir), logger, metric)
                if not df_h.empty: plot_ic_by_hour(df_h, symbol, str(base_dir), logger, metric)
                if not df_w.empty: plot_ic_by_wday(df_w, symbol, str(base_dir), logger, metric)
                if not df_d.empty: plot_ic_decay(df_d, symbol, str(base_dir), logger, metric)
            logger.info(f"[{symbol}] factor {fcol} plots saved to {plot_dir/fcol} (pairs={fac_pairs})")

    # 汇总
    pd.DataFrame(all_summary).to_csv(per_dir/"summary_factor_metrics.csv", index=False)
    if all_month: pd.DataFrame(all_month).to_csv(stab_dir/"ic_by_month.csv", index=False)
    if all_hour: pd.DataFrame(all_hour).to_csv(stab_dir/"ic_by_hour.csv", index=False)
    if all_wday: pd.DataFrame(all_wday).to_csv(stab_dir/"ic_by_wday.csv", index=False)
    if all_decay: pd.DataFrame(all_decay).to_csv(stab_dir/"ic_decay.csv", index=False)
    logger.info(f"[{symbol}] evaluation completed. Reports at {per_dir}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    logger = setup_logger(cfg.logging)
    logger.info("Factor evaluation started.")
    for sym in cfg.symbols:
        evaluate_symbol(sym, cfg.__dict__, logger)
    logger.info("All symbols done.")
