# factor_eval_v12

A robust, clean factor evaluation pipeline for Binance futures factors.

## Highlights
- UTC alignment + optional time filter
- IC (Pearson) / RankIC (Spearman) / Newey–West regression
- Stability tables (by month/hour/weekday)
- IC‑decay (supports multiple delays; separate colored lines)
- Quantile backtest (bars) with LS / top-only stats, turnover
- **Per‑factor plot folders**; clear file structure & logs

## Run
```bash
python factor_eval_v12/main.py --config factor_eval_v12/config/config.yaml
```
