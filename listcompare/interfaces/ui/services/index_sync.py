from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..io.index_names import (
    _load_brands_from_index,
    _load_names_from_uploaded_hicore,
    _load_suppliers_from_index,
    _merge_brand_lists,
    _merge_supplier_lists,
    _save_brands_to_index,
    _save_suppliers_to_index,
)
from ..runtime_paths import (
    brand_index_path as _brand_index_path,
    supplier_index_path as _supplier_index_path,
)
from .shared_sync import (
    BRAND_INDEX_FILE_NAME as _BRAND_INDEX_FILE_NAME,
    SUPPLIER_INDEX_FILE_NAME as _SUPPLIER_INDEX_FILE_NAME,
    sync_shared_files as _sync_shared_files,
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
    sync_warning_message: Optional[str] = None
    pre_sync_status = _sync_shared_files(
        targets=(_SUPPLIER_INDEX_FILE_NAME, _BRAND_INDEX_FILE_NAME)
    )
    if pre_sync_status.level == "success":
        supplier_options, supplier_index_error = _load_suppliers_from_index(_supplier_index_path())
        brand_options, brand_index_error = _load_brands_from_index(_brand_index_path())
        if supplier_index_error:
            supplier_options = list(indexed_suppliers)
        if brand_index_error:
            brand_options = list(indexed_brands)
    else:
        supplier_options = list(indexed_suppliers)
        brand_options = list(indexed_brands)
        if pre_sync_status.level in ("warning", "error"):
            sync_warning_message = pre_sync_status.message
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

        if new_supplier_names or new_brand_names:
            post_sync_status = _sync_shared_files(
                targets=(_SUPPLIER_INDEX_FILE_NAME, _BRAND_INDEX_FILE_NAME)
            )
            if post_sync_status.level in ("warning", "error"):
                sync_warning_message = post_sync_status.message

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
        warning_message=sync_warning_message,
    )
