"""ワークスペース（サーベイを作業するリポジトリ）のパス。

エンジン（このパッケージ）はワークスペースの外にインストールされる。ワークスペースの構成:

reports/YYYYMMDD_<slug>.md     … 人が読むレポート（管理ブロックは priorwork が再生成）
.priorwork/surveys/*.json      … 論文候補・採否・検索履歴などの状態（Git 管理）
.priorwork/config.json         … ワークスペースの設定（言語など。Git 管理）
.priorwork/cache/              … 抽出した本文・Zotero の一覧（Git 管理外）
.priorwork/data/               … SSCI 収録リストの CSV（Git 管理外）
.env                           … API キー（Git 管理外）
"""

import json
import os
from pathlib import Path
from typing import Optional

from . import i18n

ENGINE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = ENGINE_DIR / "assets"

META = ".priorwork"


def find_root(start: Optional[Path] = None) -> Path:
    """PRIORWORK_WORKSPACE、無ければ現在のディレクトリから上へ `.priorwork/` を探す。見つからなければ現在のディレクトリ。"""
    env = os.environ.get("PRIORWORK_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    start = (start or Path.cwd()).resolve()
    for d in (start, *start.parents):
        if (d / META).is_dir():
            return d
    return start


def reports_dir(root: Path) -> Path:
    return root / "reports"


def meta_dir(root: Path) -> Path:
    return root / META


def state_dir(root: Path) -> Path:
    return root / META / "surveys"


def cache_dir(root: Path) -> Path:
    return root / META / "cache"


def data_dir(root: Path) -> Path:
    return root / META / "data"


def config_path(root: Path) -> Path:
    return root / META / "config.json"


def load_config(root: Path) -> dict:
    try:
        return json.loads(config_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(root: Path, config: dict):
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def workspace_lang(root: Path) -> str:
    """ワークスペースの言語（レポートの見出し・AGENTS.md・スキル）。`priorwork init` が config.json に書く。
    設定が無ければ英語。"""
    return i18n.normalize(load_config(root).get("lang") or "en")


def assets_dir(lang: str) -> Path:
    return ASSETS_DIR / i18n.normalize(lang)


def template_path(lang: str) -> Path:
    return assets_dir(lang) / "templates" / "literature_review.md"


ROOT = find_root()
REPORTS_DIR = reports_dir(ROOT)
STATE_DIR = state_dir(ROOT)
CACHE_DIR = cache_dir(ROOT)
DATA_DIR = data_dir(ROOT)
