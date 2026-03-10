from __future__ import annotations

from datetime import date


def safe_filename_part(value: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid_chars else ch for ch in str(value).strip())
    cleaned = "_".join(part for part in cleaned.split())
    return cleaned if cleaned != "" else "leverantor"


def rebuilt_supplier_file_name(supplier_name: str, *, extension: str = ".xlsx") -> str:
    safe_supplier = safe_filename_part(supplier_name)
    normalized_extension = str(extension).strip()
    if normalized_extension == "":
        normalized_extension = ".xlsx"
    if not normalized_extension.startswith("."):
        normalized_extension = f".{normalized_extension}"
    return f"{safe_supplier}_prislista_{date.today().isoformat()}{normalized_extension}"
