from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU,
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS,
    build_supplier_hicore_renamed_copy as _build_supplier_hicore_renamed_copy,
    find_duplicate_names as _find_duplicate_names,
    normalize_supplier_transform_profile_options as _normalize_supplier_transform_profile_options,
)


@dataclass(frozen=True)
class ProfilePreviewDecision:
    duplicate_name_sources: list[str]
    missing_target_columns: list[str]
    blocking_error: Optional[str]
    blocking_info: Optional[str]
    show_missing_target_info: bool
    show_sku_rule_info: bool


@dataclass(frozen=True)
class CurrentProfileState:
    mapping: dict[str, str]
    composite_fields: dict[str, list[str]]
    options: dict[str, bool]


@dataclass(frozen=True)
class ProfileSaveState:
    has_saved_complete_profile: bool
    save_profile_label: str


@dataclass(frozen=True)
class ProfilePreviewArtifacts:
    renamed_df: pd.DataFrame
    current_profile_state: CurrentProfileState
    save_state: ProfileSaveState


def evaluate_profile_preview(
    *,
    selected_supplier_name: str,
    target_to_source: dict[str, str],
    composite_fields: dict[str, list[str]],
    composite_name_sources: list[str],
    current_name_mode: str,
    composite_name_mode: str,
    current_profile_filters: dict[str, object],
    strip_leading_zeros_from_sku: bool,
    ignore_rows_missing_sku: bool,
) -> ProfilePreviewDecision:
    duplicate_name_sources = _find_duplicate_names(composite_name_sources)
    if duplicate_name_sources:
        return ProfilePreviewDecision(
            duplicate_name_sources=duplicate_name_sources,
            missing_target_columns=[],
            blocking_error=(
                "Samma kolumn kan inte användas flera gånger i det sammansatta artikelnamnet: "
                + ", ".join(duplicate_name_sources)
            ),
            blocking_info=None,
            show_missing_target_info=False,
            show_sku_rule_info=False,
        )

    missing_target_columns = [
        column
        for column in SUPPLIER_HICORE_RENAME_COLUMNS
        if column not in target_to_source and column not in composite_fields
    ]
    if selected_supplier_name == "":
        return ProfilePreviewDecision(
            duplicate_name_sources=[],
            missing_target_columns=missing_target_columns,
            blocking_error=None,
            blocking_info='Välj "Leverantör" från leverantörslistan för att arbeta vidare med profilen.',
            show_missing_target_info=False,
            show_sku_rule_info=False,
        )
    if not target_to_source and not composite_fields:
        return ProfilePreviewDecision(
            duplicate_name_sources=[],
            missing_target_columns=missing_target_columns,
            blocking_error=None,
            blocking_info="Matcha minst en HiCore-kolumn för att visa förhandsvisningen.",
            show_missing_target_info=False,
            show_sku_rule_info=False,
        )
    if current_name_mode == composite_name_mode and len(composite_name_sources) < 2:
        return ProfilePreviewDecision(
            duplicate_name_sources=[],
            missing_target_columns=missing_target_columns,
            blocking_error=None,
            blocking_info="Välj minst två kolumner för att bygga ett sammansatt artikelnamn.",
            show_missing_target_info=False,
            show_sku_rule_info=False,
        )
    if (
        current_profile_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
        and str(current_profile_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]).strip() == ""
    ):
        return ProfilePreviewDecision(
            duplicate_name_sources=[],
            missing_target_columns=missing_target_columns,
            blocking_error=None,
            blocking_info="Välj en brand-kolumn innan du exkluderar varumärkesvärden.",
            show_missing_target_info=False,
            show_sku_rule_info=False,
        )

    return ProfilePreviewDecision(
        duplicate_name_sources=[],
        missing_target_columns=missing_target_columns,
        blocking_error=None,
        blocking_info=None,
        show_missing_target_info=bool(missing_target_columns),
        show_sku_rule_info=(
            SUPPLIER_HICORE_SKU_COLUMN not in target_to_source
            and (strip_leading_zeros_from_sku or ignore_rows_missing_sku)
        ),
    )


def build_profile_preview_artifacts(
    *,
    df_supplier: pd.DataFrame,
    selected_supplier_name: str,
    supplier_transform_profiles: dict[str, dict[str, object]],
    saved_profile: dict[str, str],
    saved_composite_fields: dict[str, list[str]],
    saved_filters: dict[str, object],
    saved_profile_options: dict[str, bool],
    target_to_source: dict[str, str],
    composite_fields: dict[str, list[str]],
    current_profile_filters: dict[str, object],
    strip_leading_zeros_from_sku: bool,
    ignore_rows_missing_sku: bool,
) -> ProfilePreviewArtifacts:
    renamed_df = _build_supplier_hicore_renamed_copy(
        df_supplier,
        target_to_source=target_to_source,
        supplier_name=selected_supplier_name,
        composite_fields=composite_fields,
        brand_source_column=str(
            current_profile_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]
        ),
        excluded_brand_values=[
            str(value)
            for value in current_profile_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
        ],
        strip_leading_zeros_from_sku=strip_leading_zeros_from_sku,
        ignore_rows_missing_sku=ignore_rows_missing_sku,
    )
    current_profile_state = build_current_profile_state(
        target_to_source=target_to_source,
        composite_fields=composite_fields,
        strip_leading_zeros_from_sku=strip_leading_zeros_from_sku,
        ignore_rows_missing_sku=ignore_rows_missing_sku,
    )
    save_state = build_profile_save_state(
        selected_supplier_name=selected_supplier_name,
        supplier_transform_profiles=supplier_transform_profiles,
        saved_profile=saved_profile,
        saved_composite_fields=saved_composite_fields,
        saved_filters=saved_filters,
        saved_profile_options=saved_profile_options,
        current_profile_mapping=current_profile_state.mapping,
        current_profile_composite_fields=current_profile_state.composite_fields,
        current_profile_filters=current_profile_filters,
        current_profile_options=current_profile_state.options,
    )
    return ProfilePreviewArtifacts(
        renamed_df=renamed_df,
        current_profile_state=current_profile_state,
        save_state=save_state,
    )


def build_current_profile_state(
    *,
    target_to_source: dict[str, str],
    composite_fields: dict[str, list[str]],
    strip_leading_zeros_from_sku: bool,
    ignore_rows_missing_sku: bool,
) -> CurrentProfileState:
    current_profile_mapping = {
        target_column: target_to_source[target_column]
        for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
        if target_column in target_to_source
    }
    current_profile_composite_fields = {
        target_column: list(source_columns_for_target)
        for target_column, source_columns_for_target in composite_fields.items()
        if source_columns_for_target
    }
    current_profile_options = _normalize_supplier_transform_profile_options(
        {
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: strip_leading_zeros_from_sku,
            SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU: ignore_rows_missing_sku,
        }
    )
    return CurrentProfileState(
        mapping=current_profile_mapping,
        composite_fields=current_profile_composite_fields,
        options=current_profile_options,
    )


def build_profile_save_state(
    *,
    selected_supplier_name: str,
    supplier_transform_profiles: dict[str, dict[str, object]],
    saved_profile: dict[str, str],
    saved_composite_fields: dict[str, list[str]],
    saved_filters: dict[str, object],
    saved_profile_options: dict[str, bool],
    current_profile_mapping: dict[str, str],
    current_profile_composite_fields: dict[str, list[str]],
    current_profile_filters: dict[str, object],
    current_profile_options: dict[str, bool],
) -> ProfileSaveState:
    has_saved_complete_profile = (
        saved_profile == current_profile_mapping
        and saved_composite_fields == current_profile_composite_fields
        and saved_filters == current_profile_filters
        and saved_profile_options == current_profile_options
    )
    save_profile_label = (
        "Uppdatera profil"
        if selected_supplier_name in supplier_transform_profiles
        else "Spara profil"
    )
    return ProfileSaveState(
        has_saved_complete_profile=has_saved_complete_profile,
        save_profile_label=save_profile_label,
    )
