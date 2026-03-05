from __future__ import annotations

from pathlib import Path
from typing import Optional


def normalize_names(raw_names: list[str]) -> list[str]:
    unique_by_folded: dict[str, str] = {}
    for raw_name in raw_names:
        normalized_name = str(raw_name).strip()
        if normalized_name == "" or normalized_name.casefold() == "nan":
            continue
        folded_name = normalized_name.casefold()
        if folded_name not in unique_by_folded:
            unique_by_folded[folded_name] = normalized_name

    return sorted(unique_by_folded.values(), key=lambda name: name.casefold())


def _load_name_index(path: Path, *, missing_label: str) -> tuple[list[str], Optional[str]]:
    if not path.exists():
        return [], f"Saknar {missing_label}: {path.name}"

    try:
        content = path.read_text(encoding="utf-8-sig")
        names = normalize_names(content.splitlines())
        return names, None
    except Exception as exc:
        return [], str(exc)


def _save_name_index(path: Path, names: list[str]) -> None:
    normalized_names = normalize_names(names)
    body = "\n".join(normalized_names)
    if body != "":
        body += "\n"
    path.write_text(body, encoding="utf-8-sig")


def load_suppliers_from_index(path: Path) -> tuple[list[str], Optional[str]]:
    return _load_name_index(path, missing_label="leverantörsindex")


def save_suppliers_to_index(path: Path, suppliers: list[str]) -> None:
    _save_name_index(path, suppliers)


def load_brands_from_index(path: Path) -> tuple[list[str], Optional[str]]:
    return _load_name_index(path, missing_label="varumärkesindex")


def save_brands_to_index(path: Path, brands: list[str]) -> None:
    _save_name_index(path, brands)
