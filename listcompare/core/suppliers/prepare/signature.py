from __future__ import annotations

import hashlib
import json
from typing import Optional

from ..profile import (
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU,
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS,
    normalize_supplier_transform_profile_composite_fields,
    normalize_supplier_transform_profile_filters,
    normalize_supplier_transform_profile_mapping,
    normalize_supplier_transform_profile_options,
    ordered_supplier_transform_profile_composite_fields,
    ordered_supplier_transform_profile_mapping,
)


def supplier_prepare_signature(
    *,
    supplier_name: str,
    supplier_file_name: str,
    supplier_bytes: bytes,
    profile_mapping: Optional[dict[str, str]] = None,
    profile_composite_fields: Optional[dict[str, list[str]]] = None,
    profile_filters: Optional[dict[str, object]] = None,
    profile_options: Optional[dict[str, bool]] = None,
) -> str:
    normalized_profile_mapping = normalize_supplier_transform_profile_mapping(
        profile_mapping if isinstance(profile_mapping, dict) else {}
    )
    normalized_profile_composite_fields = normalize_supplier_transform_profile_composite_fields(
        profile_composite_fields if isinstance(profile_composite_fields, dict) else {}
    )
    normalized_profile_filters = normalize_supplier_transform_profile_filters(
        profile_filters if isinstance(profile_filters, dict) else {}
    )
    normalized_profile_options = normalize_supplier_transform_profile_options(
        profile_options if isinstance(profile_options, dict) else {}
    )

    payload = {
        "supplier_name": str(supplier_name).strip(),
        "supplier_file_name": str(supplier_file_name).strip(),
        "supplier_file_sha1": hashlib.sha1(supplier_bytes).hexdigest(),
        "profile_mapping": ordered_supplier_transform_profile_mapping(
            normalized_profile_mapping
        ),
        "profile_composite_fields": ordered_supplier_transform_profile_composite_fields(
            normalized_profile_composite_fields
        ),
        "profile_filters": {
            SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN: str(
                normalized_profile_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]
            ).strip(),
            SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES: [
                str(value)
                for value in normalized_profile_filters[
                    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES
                ]
            ],
        },
        "profile_options": {
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: bool(
                normalized_profile_options[SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS]
            ),
            SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU: bool(
                normalized_profile_options[SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU]
            ),
        },
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()
