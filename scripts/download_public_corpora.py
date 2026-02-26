#!/usr/bin/env python3
"""Download and place public rPPG datasets under the project data layout.

Notes:
- Some datasets require registration/approval before obtaining a direct URL.
- Provide direct downloadable archive links via CLI flags or a JSON mapping file.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tarfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

try:
    import gdown  # type: ignore
except Exception:
    gdown = None


DATASET_LAYOUT = {
    "ubfc_rppg_v1": {
        "target_root": Path("data/public/UBFC-rPPG"),
        "expected_root": Path("data/public/UBFC-rPPG/DATASET_2"),
        "info_url": "https://sites.google.com/view/ybenezeth/ubfcrppg",
    },
    "cohface": {
        "target_root": Path("data/public/COHFACE"),
        "expected_root": Path("data/public/COHFACE"),
        "info_url": "https://www.idiap.ch/dataset/cohface",
    },
    "pure": {
        "target_root": Path("data/public/PURE"),
        "expected_root": Path("data/public/PURE"),
        "info_url": "https://www.tu-ilmenau.de/en/neurob/data-sets-code/pulse/",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--datasets",
        default="ubfc_rppg_v1",
        help="Comma list from: ubfc_rppg_v1,cohface,pure or 'all'",
    )
    parser.add_argument("--data-root", default=Path("data/public"), type=Path)
    parser.add_argument("--ubfc-url", default="", help="Direct downloadable archive URL for UBFC-rPPG.")
    parser.add_argument("--cohface-url", default="", help="Direct downloadable archive URL for COHFACE.")
    parser.add_argument("--pure-url", default="", help="Direct downloadable archive URL for PURE.")
    parser.add_argument(
        "--urls-json",
        default=None,
        type=Path,
        help="Optional JSON with keys: ubfc_rppg_v1, cohface, pure -> URL",
    )
    parser.add_argument("--force", action="store_true", help="Re-download and overwrite existing target roots.")
    return parser.parse_args()


def read_url_map(args: argparse.Namespace) -> dict[str, str]:
    url_map = {
        "ubfc_rppg_v1": args.ubfc_url.strip(),
        "cohface": args.cohface_url.strip(),
        "pure": args.pure_url.strip(),
    }
    if args.urls_json is not None:
        if not args.urls_json.exists():
            raise FileNotFoundError(f"URL JSON not found: {args.urls_json}")
        data = json.loads(args.urls_json.read_text(encoding="utf-8"))
        for key in ("ubfc_rppg_v1", "cohface", "pure"):
            if isinstance(data.get(key), str) and data[key].strip():
                url_map[key] = data[key].strip()
    return url_map


def parse_datasets(spec: str) -> list[str]:
    if spec.strip() == "all":
        return ["ubfc_rppg_v1", "cohface", "pure"]
    items = [x.strip() for x in spec.split(",") if x.strip()]
    for item in items:
        if item not in DATASET_LAYOUT:
            raise ValueError(f"Unsupported dataset id: {item}")
    return items


def download_file(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _hook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        downloaded = block_num * block_size
        pct = min(100.0, 100.0 * downloaded / total_size)
        print(f"\rDownloading {out_path.name}: {pct:6.2f}%", end="")

    urllib.request.urlretrieve(url, out_path, reporthook=_hook)
    print()


def is_google_drive_url(url: str) -> bool:
    return "drive.google.com" in url.lower()


def require_gdown() -> None:
    if gdown is None:
        raise RuntimeError(
            "Google Drive URL detected but 'gdown' is not installed. "
            "Run: make install"
        )


def download_google_drive(url: str, downloads_root: Path, dataset_id: str) -> tuple[Path, bool]:
    require_gdown()
    dataset_download_dir = downloads_root / f"{dataset_id}_gdrive"
    if dataset_download_dir.exists():
        shutil.rmtree(dataset_download_dir)
    dataset_download_dir.mkdir(parents=True, exist_ok=True)

    is_folder = "/folders/" in url
    if is_folder:
        print(f"[INFO] Downloading Google Drive folder for {dataset_id} ...")
        out = gdown.download_folder(url=url, output=str(dataset_download_dir), quiet=False, use_cookies=False)  # type: ignore[union-attr]
        if not out:
            raise RuntimeError(f"Failed to download Google Drive folder: {url}")
        return dataset_download_dir, True

    parsed = urllib.parse.urlparse(url)
    fallback_name = Path(parsed.path).name or f"{dataset_id}_gdrive_download"
    out_path = dataset_download_dir / fallback_name
    print(f"[INFO] Downloading Google Drive file for {dataset_id} ...")
    ret = gdown.download(url=url, output=str(out_path), quiet=False, fuzzy=True, use_cookies=False)  # type: ignore[union-attr]
    if ret is None:
        raise RuntimeError(f"Failed to download Google Drive file: {url}")
    return Path(ret), False


def extract_archive(archive_path: Path, extract_dir: Path) -> None:
    extract_dir.mkdir(parents=True, exist_ok=True)
    name = archive_path.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(extract_dir)
        return
    if name.endswith(".tar.gz") or name.endswith(".tgz") or name.endswith(".tar"):
        with tarfile.open(archive_path, "r:*") as tf:
            tf.extractall(extract_dir)
        return
    raise ValueError(f"Unsupported archive type: {archive_path}")


def find_dir_containing(root: Path, required_file: str) -> Path | None:
    for p in root.rglob(required_file):
        if p.is_file():
            return p.parent
    return None


def normalize_ubfc_layout(extract_root: Path, target_root: Path) -> None:
    dataset2 = next(iter(extract_root.rglob("DATASET_2")), None)
    if dataset2 and dataset2.is_dir():
        target_root.mkdir(parents=True, exist_ok=True)
        dest = target_root / "DATASET_2"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(dataset2, dest)
        return

    candidate = find_dir_containing(extract_root, "vid.avi")
    if candidate is None:
        raise RuntimeError("Could not locate UBFC dataset content (missing vid.avi).")
    target_root.mkdir(parents=True, exist_ok=True)
    dest = target_root / "DATASET_2"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(candidate.parent if candidate.name.startswith("subject") else candidate, dest)


def normalize_generic_layout(extract_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    children = [p for p in extract_root.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        src = children[0]
    else:
        src = extract_root
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(src, target_root)


def dataset_target_paths(dataset_id: str, data_root: Path) -> tuple[Path, Path]:
    layout = DATASET_LAYOUT[dataset_id]
    target_root = data_root / layout["target_root"].relative_to("data/public")
    expected_root = data_root / layout["expected_root"].relative_to("data/public")
    return target_root, expected_root


def main() -> int:
    args = parse_args()
    url_map = read_url_map(args)
    datasets = parse_datasets(args.datasets)

    downloads_root = args.data_root / "_downloads"
    downloads_root.mkdir(parents=True, exist_ok=True)

    for dataset_id in datasets:
        target_root, expected_root = dataset_target_paths(dataset_id, args.data_root)
        url = url_map.get(dataset_id, "")
        if not url:
            info_url = DATASET_LAYOUT[dataset_id]["info_url"]
            print(f"[SKIP] {dataset_id}: no direct URL provided.")
            print(f"       Request/access dataset from: {info_url}")
            continue

        if target_root.exists() and not args.force:
            print(f"[SKIP] {dataset_id}: target already exists at {target_root}. Use --force to overwrite.")
            continue
        if target_root.exists() and args.force:
            shutil.rmtree(target_root)

        parsed = urllib.parse.urlparse(url)
        archive_name = Path(parsed.path).name or f"{dataset_id}.archive"
        archive_path = downloads_root / archive_name
        extract_dir = downloads_root / f"{dataset_id}_extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)

        if is_google_drive_url(url):
            downloaded_path, already_extracted = download_google_drive(url, downloads_root, dataset_id)
            if already_extracted:
                extract_dir = downloaded_path
            else:
                print(f"[INFO] Extracting {downloaded_path} ...")
                extract_archive(downloaded_path, extract_dir)
        else:
            print(f"[INFO] Downloading {dataset_id} ...")
            download_file(url, archive_path)
            print(f"[INFO] Extracting {archive_path} ...")
            extract_archive(archive_path, extract_dir)

        print(f"[INFO] Normalizing layout for {dataset_id} ...")
        if dataset_id == "ubfc_rppg_v1":
            normalize_ubfc_layout(extract_dir, target_root)
        else:
            normalize_generic_layout(extract_dir, target_root)

        print(f"[OK] {dataset_id} placed at {target_root}")
        print(f"     expected root: {expected_root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
