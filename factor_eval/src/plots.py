from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def ensure_dir(p): Path(p).mkdir(parents=True, exist_ok=True)

def _style():
    plt.style.use("seaborn-v0_8-whitegrid")

def plot_ic_by_month(df, symbol, out_dir, logger):
    _style()
    for (fac, ret), sub in df.groupby(["factor","ret_col"]):
        fac_dir = Path(out_dir) / fac
        ensure_dir(fac_dir)
        xs = list(sub["ym"]); ys = list(sub["rank_ic"])
        plt.figure(figsize=(9,4))
        plt.plot(xs, ys, marker="o")
        plt.title(f"RankIC by Month — {fac} & {ret}")
        plt.xlabel("Year-Month"); plt.ylabel("RankIC"); plt.xticks(rotation=45, ha="right")
        plt.tight_layout(); plt.savefig(fac_dir / f"ic_by_month__{ret}.png", dpi=150); plt.close()
    logger.info(f"[{symbol}] IC-by-month plots saved per factor.")

def plot_ic_by_hour(df, symbol, out_dir, logger):
    _style()
    for (fac, ret), sub in df.groupby(["factor","ret_col"]):
        fac_dir = Path(out_dir) / fac
        ensure_dir(fac_dir)
        xs = list(sub.sort_values("hour")["hour"]); ys = list(sub.sort_values("hour")["rank_ic"])
        plt.figure(figsize=(7,4))
        plt.bar(xs, ys)
        plt.title(f"RankIC by Hour — {fac} & {ret}")
        plt.xlabel("Hour (0-23)"); plt.ylabel("RankIC")
        plt.tight_layout(); plt.savefig(fac_dir / f"ic_by_hour__{ret}.png", dpi=150); plt.close()
    logger.info(f"[{symbol}] IC-by-hour plots saved per factor.")

def plot_ic_by_wday(df, symbol, out_dir, logger):
    _style()
    for (fac, ret), sub in df.groupby(["factor","ret_col"]):
        fac_dir = Path(out_dir) / fac
        ensure_dir(fac_dir)
        xs = list(sub.sort_values("wday")["wday"]); ys = list(sub.sort_values("wday")["rank_ic"])
        plt.figure(figsize=(7,4))
        plt.bar(xs, ys)
        plt.title(f"RankIC by Weekday — {fac} & {ret}")
        plt.xlabel("Weekday (Mon=0)"); plt.ylabel("RankIC")
        plt.tight_layout(); plt.savefig(fac_dir / f"ic_by_wday__{ret}.png", dpi=150); plt.close()
    logger.info(f"[{symbol}] IC-by-wday plots saved per factor.")

def _period_key(p):
    import re
    m = re.match(r"(\d+)([smhd])", str(p))
    if not m: return 0
    n,u = int(m.group(1)), m.group(2)
    return n if u=='m' else (n*60 if u=='h' else (n*1440 if u=='d' else max(1,n//60)))

def plot_ic_decay(df, symbol, out_dir, logger):
    _style()
    for fac, sub in df.groupby("factor"):
        fac_dir = Path(out_dir) / fac
        ensure_dir(fac_dir)
        # group by delay, plot colored lines
        plt.figure(figsize=(9,4))
        for delay, subd in sub.groupby("delay"):
            subd = subd.sort_values("period", key=lambda s: s.map(_period_key))
            xs = list(subd["period"]); ys = list(subd["rank_ic"])
            plt.plot(xs, ys, marker="o", label=f"delay={delay}")
        plt.legend(title="Delay")
        plt.title(f"IC-Decay — {fac}")
        plt.xlabel("Period"); plt.ylabel("RankIC")
        plt.tight_layout(); plt.savefig(fac_dir / "ic_decay.png", dpi=150); plt.close()
    logger.info(f"[{symbol}] IC-decay plots saved per factor.")

def plot_quantile_bars(df_pair, fcol, rcol, out_dir, logger):
    _style()
    fac_dir = Path(out_dir) / fcol
    ensure_dir(fac_dir)
    nb = df_pair[(df_pair["bin"]>=1) & (df_pair["bin"]<=50)]
    if nb.empty: return
    xs = list(nb["bin"]); ys = list(nb["mean"])
    plt.figure(figsize=(7,4))
    plt.bar(xs, ys)
    plt.title(f"Quantile Returns — {fcol} & {rcol}")
    plt.xlabel("Quantile bin"); plt.ylabel("Mean future return")
    plt.tight_layout(); plt.savefig(fac_dir / f"quantiles__{rcol}.png", dpi=150); plt.close()
    logger.info(f"Quantile plot saved: {fac_dir / f'quantiles__{rcol}.png'}")
