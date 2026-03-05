#!/usr/bin/env python3
"""Download and place the UBFC-rPPG public dataset under project layout."""

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


TARGET_ROOT = Path("data/public/UBFC-rPPG")
EXPECTED_ROOT = Path("data/public/UBFC-rPPG/DATASET_2")
INFO_URL = "https://sites.google.com/view/ybenezeth/ubfcrppg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=Path("data/public"), type=Path)
    parser.add_argument("--ubfc-url", default="", help="Direct downloadable archive URL for UBFC-rPPG.")
    parser.add_argument(
        "--urls-json",
        default=None,
        type=Path,
        help="Optional JSON with key: ubfc_rppg_v1 -> URL",
    )
    parser.add_argument("--force", action="store_true", help="Re-download and overwrite existing target root.")
    return parser.parse_args()


def read_url(args: argparse.Namespace) -> str:
    url = args.ubfc_url.strip()
    if args.urls_json is not None:
        if not args.urls_json.exists():
            raise FileNotFoundError(f"URL JSON not found: {args.urls_json}")
        data = json.loads(args.urls_json.read_text(encoding="utf-8"))
        v = data.get("ubfc_rppg_v1", "")
        if isinstance(v, str) and v.strip():
            url = v.strip()
    return url


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
        raise RuntimeError("Google Drive URL detected but 'gdown' is not installed. Run: make install")


def download_google_drive(url: str, downloads_root: Path) -> tuple[Path, bool]:
    require_gdown()
    dataset_download_dir = downloads_root / "ubfc_rppg_v1_gdrive"
    if dataset_download_dir.exists():
        shutil.rmtree(dataset_download_dir)
    dataset_download_dir.mkdir(parents=True, exist_ok=True)

    is_folder = "/folders/" in url
    if is_folder:
        print("[INFO] Downloading Google Drive folder for ubfc_rppg_v1 ...")
        out = gdown.download_folder(url=url, output=str(dataset_download_dir), quiet=False, use_cookies=False)  # type: ignore[union-attr]
        if not out:
            raise RuntimeError(f"Failed to download Google Drive folder: {url}")
        return dataset_download_dir, True

    parsed = urllib.parse.urlparse(url)
    fallback_name = Path(parsed.path).name or "ubfc_rppg_v1_gdrive_download"
    out_path = dataset_download_dir / fallback_name
    print("[INFO] Downloading Google Drive file for ubfc_rppg_v1 ...")
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


def main() -> int:
    args = parse_args()
    url = read_url(args)

    target_root = args.data_root / TARGET_ROOT.relative_to("data/public")
    expected_root = args.data_root / EXPECTED_ROOT.relative_to("data/public")

    if not url:
        print("[SKIP] ubfc_rppg_v1: no direct URL provided.")
        print(f"       Request/access dataset from: {INFO_URL}")
        return 0

    if target_root.exists() and not args.force:
        print(f"[SKIP] ubfc_rppg_v1: target already exists at {target_root}. Use --force to overwrite.")
        return 0
    if target_root.exists() and args.force:
        shutil.rmtree(target_root)

    downloads_root = args.data_root / "_downloads"
    downloads_root.mkdir(parents=True, exist_ok=True)

    parsed = urllib.parse.urlparse(url)
    archive_name = Path(parsed.path).name or "ubfc_rppg_v1.archive"
    archive_path = downloads_root / archive_name
    extract_dir = downloads_root / "ubfc_rppg_v1_extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    if is_google_drive_url(url):
        downloaded_path, already_extracted = download_google_drive(url, downloads_root)
        if already_extracted:
            extract_dir = downloaded_path
        else:
            print(f"[INFO] Extracting {downloaded_path} ...")
            extract_archive(downloaded_path, extract_dir)
    else:
        print("[INFO] Downloading ubfc_rppg_v1 ...")
        download_file(url, archive_path)
        print(f"[INFO] Extracting {archive_path} ...")
        extract_archive(archive_path, extract_dir)

    print("[INFO] Normalizing layout for ubfc_rppg_v1 ...")
    normalize_ubfc_layout(extract_dir, target_root)

    print(f"[OK] ubfc_rppg_v1 placed at {target_root}")
    print(f"     expected root: {expected_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
