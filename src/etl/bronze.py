import shutil
from pathlib import Path


def copy_to_bronze(src_path: Path, catalog_dir: Path) -> Path:
    """バトルログJSONをunity-catalogのbronze層にコピーする"""
    catalog_dir.mkdir(parents=True, exist_ok=True)
    dest = catalog_dir / f"bronze_{src_path.name}"
    shutil.copy2(src_path, dest)
    return dest
