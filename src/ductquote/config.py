import os
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_settings() -> dict:
    return yaml.safe_load((ROOT / "config" / "settings.yaml").read_text())


def load_catalog() -> dict:
    return yaml.safe_load((ROOT / "config" / "pricing_catalog.yaml").read_text())


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
