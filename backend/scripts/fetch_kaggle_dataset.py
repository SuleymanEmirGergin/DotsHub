#!/usr/bin/env python3
"""Download Kaggle CSV files and normalize them into backend/raw_data/.

This script prepares the exact file names expected by preprocess_kaggle.py:
  - dataset.csv
  - Symptom-severity.csv
  - symptom_Description.csv
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DEFAULT_DOWNLOAD_DIR = BACKEND_DIR / ".tmp_kaggle_download"
DEFAULT_RAW_DATA_DIR = BACKEND_DIR / "raw_data"

TARGET_FILE_NAMES: Dict[str, str] = {
    "dataset": "dataset.csv",
    "severity": "Symptom-severity.csv",
    "description": "symptom_Description.csv",
}


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _pick_best_match(
    files: Iterable[Path],
    *,
    exact_tokens: Tuple[str, ...],
    required_tokens: Tuple[str, ...],
) -> Optional[Path]:
    ranked: List[Tuple[int, int, str, Path]] = []
    for file_path in files:
        token = _normalize_name(file_path.name)
        if token in exact_tokens:
            ranked.append((0, len(file_path.name), str(file_path), file_path))
            continue
        if all(req in token for req in required_tokens):
            ranked.append((1, len(file_path.name), str(file_path), file_path))

    if not ranked:
        return None

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return ranked[0][3]


def _discover_csvs(download_dir: Path) -> List[Path]:
    csv_files = [
        p
        for p in download_dir.rglob("*")
        if p.is_file() and p.suffix.lower() == ".csv"
    ]
    return sorted(csv_files, key=lambda p: str(p))


def _resolve_sources(csv_files: List[Path]) -> Dict[str, Optional[Path]]:
    return {
        "dataset": _pick_best_match(
            csv_files,
            exact_tokens=("datasetcsv",),
            required_tokens=("dataset",),
        ),
        "severity": _pick_best_match(
            csv_files,
            exact_tokens=("symptomseveritycsv",),
            required_tokens=("symptom", "severity"),
        ),
        "description": _pick_best_match(
            csv_files,
            exact_tokens=("symptomdescriptioncsv",),
            required_tokens=("symptom", "description"),
        ),
    }


def _check_kaggle_env() -> None:
    missing = [
        key
        for key in ("KAGGLE_USERNAME", "KAGGLE_KEY")
        if not os.getenv(key, "").strip()
    ]
    if missing:
        raise RuntimeError(
            "Missing Kaggle credentials in environment: "
            + ", ".join(sorted(missing))
        )
    if shutil.which("kaggle") is None:
        raise RuntimeError("kaggle CLI not found. Install with `pip install kaggle`.")


def _run_download(dataset_slug: str, download_dir: Path) -> None:
    _check_kaggle_env()

    if download_dir.exists():
        shutil.rmtree(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "kaggle",
        "datasets",
        "download",
        "-d",
        dataset_slug,
        "--unzip",
        "-p",
        str(download_dir),
    ]
    print(f"Downloading Kaggle dataset: {dataset_slug}")
    subprocess.run(cmd, check=True)


def _sync_raw_data(
    sources: Dict[str, Optional[Path]],
    raw_data_dir: Path,
) -> Dict[str, Optional[Path]]:
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    synced: Dict[str, Optional[Path]] = {}

    for key, target_name in TARGET_FILE_NAMES.items():
        source_path = sources.get(key)
        target_path = raw_data_dir / target_name

        if source_path is None:
            if target_path.exists():
                target_path.unlink()
            synced[key] = None
            continue

        shutil.copy2(source_path, target_path)
        synced[key] = target_path

    return synced


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Kaggle CSVs and normalize them for preprocess_kaggle.py.",
    )
    parser.add_argument(
        "--dataset-slug",
        required=True,
        help="Kaggle dataset slug in owner/name format.",
    )
    parser.add_argument(
        "--download-dir",
        default=str(DEFAULT_DOWNLOAD_DIR),
        help="Temporary download directory (default: backend/.tmp_kaggle_download).",
    )
    parser.add_argument(
        "--raw-data-dir",
        default=str(DEFAULT_RAW_DATA_DIR),
        help="Output directory for normalized raw CSV files (default: backend/raw_data).",
    )
    parser.add_argument(
        "--keep-download",
        action="store_true",
        help="Keep temporary downloaded files after sync.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    dataset_slug = str(args.dataset_slug).strip()
    download_dir = Path(args.download_dir).resolve()
    raw_data_dir = Path(args.raw_data_dir).resolve()

    if "/" not in dataset_slug:
        print("ERROR: --dataset-slug must be in owner/name format.")
        return 2

    try:
        _run_download(dataset_slug, download_dir)
        csv_files = _discover_csvs(download_dir)
        if not csv_files:
            print(f"ERROR: No CSV files found under {download_dir}")
            return 2

        sources = _resolve_sources(csv_files)
        if sources.get("dataset") is None:
            print("ERROR: Could not locate dataset CSV in downloaded files.")
            print("Found CSV files:")
            for file_path in csv_files:
                print(f"  - {file_path}")
            return 2

        synced = _sync_raw_data(sources, raw_data_dir)
        print("Synced raw_data files:")
        for key, target_name in TARGET_FILE_NAMES.items():
            source_path = sources.get(key)
            if source_path is None:
                print(f"  - {target_name}: not found in dataset (removed if existed)")
            else:
                print(f"  - {target_name}: {source_path}")

        if not args.keep_download and download_dir.exists():
            shutil.rmtree(download_dir)

        return 0
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: Kaggle download failed with exit code {exc.returncode}")
        return int(exc.returncode or 1)
    except Exception as exc:  # pragma: no cover - defensive logging for CI
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
