import os
import sqlite3
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


ROOT = Path(__file__).resolve().parent
IMAGE_DIR = ROOT / "static" / "images"
DB_PATH = ROOT / "tfc_admin.db"
SOURCE_EXTS = {".jpg", ".jpeg", ".png"}
MAX_SIZE = (1200, 1200)
QUALITY = 78


def optimize_one(path: Path) -> tuple[bool, int, int, str]:
    target = path.with_suffix(".webp")
    if target.exists() and target.stat().st_mtime >= path.stat().st_mtime:
        return False, path.stat().st_size, target.stat().st_size, target.name

    try:
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        image.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=QUALITY, method=6)
        return True, path.stat().st_size, target.stat().st_size, target.name
    except (UnidentifiedImageError, OSError) as exc:
        print(f"skip {path.name}: {exc}")
        return False, path.stat().st_size, 0, path.name


def update_db(mapping: dict[str, str]) -> None:
    if not DB_PATH.exists() or not mapping:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for old, new in mapping.items():
        cur.execute("UPDATE foods SET image_url = ? WHERE image_url = ?", (new, old))
        cur.execute("UPDATE aktsii SET image_url = ? WHERE image_url = ?", (new, old))
        cur.execute("UPDATE reviews SET image_url = ? WHERE image_url = ?", (new, old))
    conn.commit()
    conn.close()


def main() -> None:
    mapping: dict[str, str] = {}
    original_total = 0
    webp_total = 0
    changed = 0

    for path in IMAGE_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTS:
            continue
        did_change, original_size, webp_size, old_name = optimize_one(path)
        target_name = path.with_suffix(".webp").name
        if webp_size and webp_size < original_size:
            mapping[old_name] = target_name
        if did_change:
            changed += 1
        original_total += original_size
        webp_total += webp_size

    update_db(mapping)
    saved = original_total - webp_total
    print(f"optimized={changed}")
    print(f"db_updated={len(mapping)}")
    print(f"original_mb={original_total / 1024 / 1024:.2f}")
    print(f"webp_mb={webp_total / 1024 / 1024:.2f}")
    print(f"saved_mb={saved / 1024 / 1024:.2f}")


if __name__ == "__main__":
    main()
