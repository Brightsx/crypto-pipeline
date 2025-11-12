from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def ensure_dir(p): Path(p).mkdir(parents=True, exist_ok=True)
def _style(): plt.style.use("seaborn-v0_8-whitegrid")

def plot_ic_by_month(df, symbol, out_dir, logger, metric="spearman"):
    _style()
    for (fac, ret), sub in df.groupby(["factor","ret_col"]):
        outp = Path(out_dir)
        ensure_dir(outp)
        xs = list(sub["ym"]); ys = list(sub["value"])
        plt.figure(figsize=(9,4))
        plt.plot(xs, ys, marker="o")
        plt.title(f"{metric.title()} IC by Month — {fac} & {ret}")
        plt.xlabel("Year-Month"); plt.ylabel("IC"); plt.xticks(rotation=45, ha="right")
        plt.tight_layout(); plt.savefig(outp / f"ic_by_month__{ret}.png", dpi=150); plt.close()
    logger.info(f"[{symbol}] {metric} IC-by-month plots saved at {out_dir}")

def plot_ic_by_hour(df, symbol, out_dir, logger, metric="spearman"):
    _style()
    for (fac, ret), sub in df.groupby(["factor","ret_col"]):
        outp = Path(out_dir)
        ensure_dir(outp)
        xs = list(sub.sort_values("hour")["hour"]); ys = list(sub.sort_values("hour")["value"])
        plt.figure(figsize=(7,4))
        plt.bar(xs, ys)
        plt.title(f"{metric.title()} IC by Hour — {fac} & {ret}")
        plt.xlabel("Hour (0-23)"); plt.ylabel("IC")
        plt.tight_layout(); plt.savefig(outp / f"ic_by_hour__{ret}.png", dpi=150); plt.close()
    logger.info(f"[{symbol}] {metric} IC-by-hour plots saved at {out_dir}")

def plot_ic_by_wday(df, symbol, out_dir, logger, metric="spearman"):
    _style()
    for (fac, ret), sub in df.groupby(["factor","ret_col"]):
        outp = Path(out_dir)
        ensure_dir(outp)
        xs = list(sub.sort_values("wday")["wday"]); ys = list(sub.sort_values("wday")["value"])
        plt.figure(figsize=(7,4))
        plt.bar(xs, ys)
        plt.title(f"{metric.title()} IC by Weekday — {fac} & {ret}")
        plt.xlabel("Weekday (Mon=0)"); plt.ylabel("IC")
        plt.tight_layout(); plt.savefig(outp / f"ic_by_wday__{ret}.png", dpi=150); plt.close()
    logger.info(f"[{symbol}] {metric} IC-by-wday plots saved at {out_dir}")

def _period_key(p):
    import re
    m = re.match(r"(\d+)([smhd])", str(p))
    if not m: return 0
    n,u = int(m.group(1)), m.group(2)
    if u == 's': return max(1, n//60)
    if u == 'm': return n
    if u == 'h': return n*60
    if u == 'd': return n*1440
    return n

def plot_ic_decay(df, symbol, out_dir, logger, metric="spearman"):
    _style()
    for fac, sub in df.groupby("factor"):
        outp = Path(out_dir)
        ensure_dir(outp)
        plt.figure(figsize=(9,4))
        for delay, subd in sub.groupby("delay"):
            subd = subd.sort_values("period", key=lambda s: s.map(_period_key))
            xs = list(subd["period"]); ys = list(subd["value"])
            plt.plot(xs, ys, marker="o", label=f"delay={delay}")
        plt.legend(title="Delay")
        plt.title(f"{metric.title()} IC-Decay — {fac}")
        plt.xlabel("Period"); plt.ylabel("IC")
        plt.tight_layout(); plt.savefig(outp / "ic_decay.png", dpi=150); plt.close()
    logger.info(f"[{symbol}] {metric} IC-decay plots saved at {out_dir}")

def plot_quantile_bars(df_pair, fcol, rcol, out_dir, logger):
    _style()
    outp = Path(out_dir)
    ensure_dir(outp)
    nb = df_pair[(df_pair["bin"]>=1) & (df_pair["bin"]<=50)]
    if nb.empty: return
    xs = list(nb["bin"]); ys = list(nb["mean"])
    plt.figure(figsize=(7,4))
    plt.bar(xs, ys)
    plt.title(f"Quantile Returns — {fcol} & {rcol}")
    plt.xlabel("Quantile bin"); plt.ylabel("Mean future return")
    plt.tight_layout(); plt.savefig(outp / f"quantiles__{rcol}.png", dpi=150); plt.close()
    logger.info(f"Quantile plot saved: {outp / f'quantiles__{rcol}.png'}")
