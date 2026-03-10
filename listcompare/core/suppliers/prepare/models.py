from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_SOURCE_ROW_COLUMN = "__lc_source_row_number"
SUPPLIER_PREPARE_IGNORE_GROUP = "__ignore_conflict_group__"


@dataclass(frozen=True)
class SupplierConflictCandidate:
    candidate_id: str
    source_row_numbers: tuple[int, ...]
    row_values: dict[str, str]


@dataclass(frozen=True)
class SupplierDuplicateConflict:
    group_key: str
    sku: str
    candidates: tuple[SupplierConflictCandidate, ...]


@dataclass(frozen=True)
class SupplierPrepareAnalysis:
    output_columns: tuple[str, ...]
    exact_duplicate_rows_removed: int
    rows_ready_without_conflicts: pd.DataFrame
    conflicts: tuple[SupplierDuplicateConflict, ...]
