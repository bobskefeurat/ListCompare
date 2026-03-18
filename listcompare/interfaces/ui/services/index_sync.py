from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..io.index_names import (
    _load_names_from_uploaded_hicore,
    _merge_brand_lists,
    _merge_supplier_lists,
    _save_brands_to_index,
    _save_suppliers_to_index,
)
from ..runtime_paths import (
    brand_index_path as _brand_index_path,
    supplier_index_path as _supplier_index_path,
)


@dataclass(frozen=True)
class IndexSyncResult:
    supplier_options: list[str]
    brand_options: list[str]
    new_supplier_names: list[str]
    new_brand_names: list[str]
    hicore_missing_brand_column: bool
    warning_message: Optional[str]


def sync_index_options_from_uploaded_hicore(
    *,
    indexed_suppliers: list[str],
    indexed_brands: list[str],
    stored_hicore_file: Optional[dict[str, object]],
) -> IndexSyncResult:
    supplier_options = list(indexed_suppliers)
    brand_options = list(indexed_brands)
    new_supplier_names: list[str] = []
    new_brand_names: list[str] = []
    hicore_missing_brand_column = False

    if stored_hicore_file is None:
        return IndexSyncResult(
            supplier_options=supplier_options,
            brand_options=brand_options,
            new_supplier_names=new_supplier_names,
            new_brand_names=new_brand_names,
            hicore_missing_brand_column=hicore_missing_brand_column,
            warning_message=None,
        )

    try:
        (
            uploaded_suppliers,
            uploaded_brands,
            _has_supplier_column,
            has_brand_column,
        ) = _load_names_from_uploaded_hicore(
            str(stored_hicore_file["name"]),
            stored_hicore_file["bytes"],  # type: ignore[index]
        )
        supplier_options, new_supplier_names = _merge_supplier_lists(
            supplier_options,
            uploaded_suppliers,
        )
        if new_supplier_names:
            _save_suppliers_to_index(_supplier_index_path(), supplier_options)

        brand_options, new_brand_names = _merge_brand_lists(
            brand_options,
            uploaded_brands,
        )
        if new_brand_names:
            _save_brands_to_index(_brand_index_path(), brand_options)

        hicore_missing_brand_column = not has_brand_column
    except Exception as exc:
        return IndexSyncResult(
            supplier_options=supplier_options,
            brand_options=brand_options,
            new_supplier_names=[],
            new_brand_names=[],
            hicore_missing_brand_column=False,
            warning_message=f"Kunde inte läsa leverantörs-/varumärkeslista från uppladdad HiCore-fil: {exc}",
        )

    return IndexSyncResult(
        supplier_options=supplier_options,
        brand_options=brand_options,
        new_supplier_names=new_supplier_names,
        new_brand_names=new_brand_names,
        hicore_missing_brand_column=hicore_missing_brand_column,
        warning_message=None,
    )
