from dataclasses import dataclass
import yaml

@dataclass
class Config:
    utc: bool
    symbols: list
    paths: dict
    columns: dict
    preprocess: dict
    evaluation: dict
    stability: dict
    annualization: dict
    output: dict
    logging: dict

def load_config(path: str) -> 'Config':
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Config(**raw)

def dump_config_snapshot(cfg: 'Config', path: str):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg.__dict__, f, allow_unicode=True, sort_keys=False)
