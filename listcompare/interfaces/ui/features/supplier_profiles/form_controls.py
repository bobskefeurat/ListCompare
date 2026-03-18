from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_ARTICLE_NUMBER_COLUMN,
    SUPPLIER_HICORE_NAME_COLUMN,
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS,
    normalize_supplier_transform_profile_filters as _normalize_supplier_transform_profile_filters,
)
from .view_model import supplier_file_unique_values as _supplier_file_unique_values

NAME_MODE_SINGLE = "single"
NAME_MODE_COMPOSITE = "composite"


@dataclass(frozen=True)
class ProfileFormControls:
    file_token: str
    current_name_mode: str
    composite_name_sources: list[str]
    target_to_source: dict[str, str]
    composite_fields: dict[str, list[str]]
    current_profile_filters: dict[str, object]
    strip_leading_zeros_from_sku: bool


def _seed_source_widget(
    *,
    widget_key: str,
    saved_source: object,
    source_columns: list[str],
    should_seed_defaults: bool,
) -> None:
    if saved_source is None:
        return
    normalized_saved_source = str(saved_source).strip()
    current_value = st.session_state.get(widget_key)
    current_value_normalized = "" if current_value is None else str(current_value).strip()
    if normalized_saved_source in source_columns and (
        should_seed_defaults
        or widget_key not in st.session_state
        or current_value_normalized == ""
        or current_value_normalized not in source_columns
    ):
        st.session_state[widget_key] = normalized_saved_source


def _profile_file_token(
    *,
    selected_supplier_name: str,
    supplier_file_name: str,
    supplier_bytes: bytes,
) -> str:
    supplier_key_token = selected_supplier_name if selected_supplier_name != "" else "no_supplier"
    return f"{Path(supplier_file_name).name}_{len(supplier_bytes)}_{supplier_key_token}"


def _render_name_mapping_controls(
    *,
    file_token: str,
    source_columns: list[str],
    saved_profile: dict[str, str],
    saved_composite_fields: dict[str, list[str]],
    should_seed_defaults: bool,
) -> tuple[str, list[str], dict[str, str], dict[str, list[str]]]:
    target_to_source: dict[str, str] = {}
    composite_fields: dict[str, list[str]] = {}
    name_mode_key = f"supplier_transform_name_mode_{file_token}"
    if should_seed_defaults or name_mode_key not in st.session_state:
        st.session_state[name_mode_key] = (
            NAME_MODE_COMPOSITE
            if saved_composite_fields.get(SUPPLIER_HICORE_NAME_COLUMN)
            else NAME_MODE_SINGLE
        )

    st.markdown(f"**{SUPPLIER_HICORE_NAME_COLUMN}**")
    current_name_mode = str(st.session_state.get(name_mode_key, NAME_MODE_SINGLE))
    if current_name_mode not in (NAME_MODE_SINGLE, NAME_MODE_COMPOSITE):
        current_name_mode = NAME_MODE_SINGLE
        st.session_state[name_mode_key] = current_name_mode
    current_name_mode = st.radio(
        "Namnl\u00e4ge",
        options=[NAME_MODE_SINGLE, NAME_MODE_COMPOSITE],
        format_func=lambda value: "En kolumn" if value == NAME_MODE_SINGLE else "Kombinera kolumner",
        horizontal=True,
        key=name_mode_key,
    )

    composite_name_sources: list[str] = []
    if current_name_mode == NAME_MODE_SINGLE:
        name_widget_key = f"supplier_transform_map_{SUPPLIER_HICORE_NAME_COLUMN}_{file_token}"
        _seed_source_widget(
            widget_key=name_widget_key,
            saved_source=saved_profile.get(SUPPLIER_HICORE_NAME_COLUMN),
            source_columns=source_columns,
            should_seed_defaults=should_seed_defaults,
        )
        selected_name_source = st.selectbox(
            SUPPLIER_HICORE_NAME_COLUMN,
            options=source_columns,
            index=None,
            placeholder="V\u00e4lj motsvarande kolumn i leverant\u00f6rsfilen...",
            key=name_widget_key,
        )
        if selected_name_source is not None and str(selected_name_source).strip() != "":
            target_to_source[SUPPLIER_HICORE_NAME_COLUMN] = str(selected_name_source).strip()
    else:
        saved_name_parts = saved_composite_fields.get(SUPPLIER_HICORE_NAME_COLUMN, [])
        name_part_count_key = f"supplier_transform_name_part_count_{file_token}"
        if should_seed_defaults or name_part_count_key not in st.session_state:
            st.session_state[name_part_count_key] = max(
                2,
                len(saved_name_parts) if saved_name_parts else 2,
            )
        max_name_parts = max(2, len(source_columns))
        requested_name_parts = int(
            st.number_input(
                "Antal kolumner i Artikelnamn",
                min_value=2,
                max_value=max_name_parts,
                step=1,
                key=name_part_count_key,
            )
        )
        for idx in range(requested_name_parts):
            widget_key = f"supplier_transform_name_part_{idx}_{file_token}"
            saved_source = saved_name_parts[idx] if idx < len(saved_name_parts) else None
            _seed_source_widget(
                widget_key=widget_key,
                saved_source=saved_source,
                source_columns=source_columns,
                should_seed_defaults=should_seed_defaults,
            )
            selected_name_part = st.selectbox(
                f"Artikelnamn del {idx + 1}",
                options=source_columns,
                index=None,
                placeholder="V\u00e4lj kolumn...",
                key=widget_key,
            )
            if selected_name_part is not None and str(selected_name_part).strip() != "":
                composite_name_sources.append(str(selected_name_part).strip())

    if current_name_mode == NAME_MODE_COMPOSITE:
        composite_fields[SUPPLIER_HICORE_NAME_COLUMN] = composite_name_sources

    return current_name_mode, composite_name_sources, target_to_source, composite_fields


def _render_target_mapping_controls(
    *,
    file_token: str,
    source_columns: list[str],
    saved_profile: dict[str, str],
    should_seed_defaults: bool,
    target_to_source: dict[str, str],
) -> None:
    other_target_columns = [
        target_column
        for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
        if target_column != SUPPLIER_HICORE_NAME_COLUMN
    ]
    for target_column in other_target_columns:
        widget_key = f"supplier_transform_map_{target_column}_{file_token}"
        _seed_source_widget(
            widget_key=widget_key,
            saved_source=saved_profile.get(target_column),
            source_columns=source_columns,
            should_seed_defaults=should_seed_defaults,
        )
        selected_source = st.selectbox(
            target_column,
            options=source_columns,
            index=None,
            placeholder="V\u00e4lj motsvarande kolumn i leverant\u00f6rsfilen...",
            key=widget_key,
        )
        if selected_source is not None and str(selected_source).strip() != "":
            target_to_source[target_column] = str(selected_source).strip()


def _render_sku_rule_controls(
    *,
    file_token: str,
    saved_profile_options: dict[str, bool],
    should_seed_defaults: bool,
) -> bool:
    st.subheader("SKU-regler")
    st.caption(f'G\u00e4ller kolumnen "{SUPPLIER_HICORE_SKU_COLUMN}" n\u00e4r den \u00e4r mappad.')
    st.caption(
        f'Rader utan "{SUPPLIER_HICORE_SKU_COLUMN}" anv\u00e4nder "{SUPPLIER_HICORE_ARTICLE_NUMBER_COLUMN}" '
        "som reserv om b\u00e5da kolumnerna \u00e4r mappade. Rader utan b\u00e5da f\u00e4lten utel\u00e4mnas."
    )
    strip_zeros_key = f"supplier_transform_option_strip_zeros_{file_token}"
    if should_seed_defaults or strip_zeros_key not in st.session_state:
        st.session_state[strip_zeros_key] = saved_profile_options[
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS
        ]
    strip_leading_zeros_from_sku = bool(
        st.checkbox("Ta bort inledande nollor i SKU", key=strip_zeros_key)
    )
    return strip_leading_zeros_from_sku


def _render_brand_filter_controls(
    *,
    file_token: str,
    df_supplier,
    source_columns: list[str],
    saved_filters: dict[str, object],
    should_seed_defaults: bool,
) -> dict[str, object]:
    st.subheader("Varum\u00e4rkesfilter")
    brand_source_key = f"supplier_transform_brand_source_{file_token}"
    saved_brand_source = str(saved_filters.get(SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN, "")).strip()
    if should_seed_defaults and saved_brand_source in source_columns:
        st.session_state[brand_source_key] = saved_brand_source
    elif should_seed_defaults and brand_source_key not in st.session_state:
        st.session_state[brand_source_key] = None

    selected_brand_source = st.selectbox(
        "Brand-kolumn f\u00f6r exkludering",
        options=source_columns,
        index=None,
        placeholder="V\u00e4lj brand-kolumn i leverant\u00f6rsfilen...",
        key=brand_source_key,
    )
    selected_brand_source_name = (
        str(selected_brand_source).strip() if selected_brand_source is not None else ""
    )
    available_brand_values = (
        _supplier_file_unique_values(df_supplier, column_name=selected_brand_source_name)
        if selected_brand_source_name != ""
        else []
    )
    saved_excluded_brand_values = [
        str(value)
        for value in saved_filters.get(
            SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
            [],
        )
    ]
    missing_saved_excluded_brand_values = [
        brand_name
        for brand_name in saved_excluded_brand_values
        if brand_name.casefold() not in {value.casefold() for value in available_brand_values}
    ]
    brand_value_options = list(available_brand_values)
    for brand_name in missing_saved_excluded_brand_values:
        brand_value_options.append(brand_name)

    excluded_brand_values_key = f"supplier_transform_excluded_brands_{file_token}"
    if should_seed_defaults or excluded_brand_values_key not in st.session_state:
        st.session_state[excluded_brand_values_key] = saved_excluded_brand_values
    if missing_saved_excluded_brand_values:
        st.warning(
            "Sparade exkluderade varum\u00e4rken saknas i aktuell fil men beh\u00e5lls tills du \u00e4ndrar profilen: "
            + ", ".join(missing_saved_excluded_brand_values)
        )
    selected_excluded_brand_values = st.multiselect(
        "Varum\u00e4rkesv\u00e4rden som ska exkluderas",
        options=brand_value_options,
        placeholder="V\u00e4lj ett eller flera v\u00e4rden...",
        disabled=selected_brand_source_name == "",
        key=excluded_brand_values_key,
    )
    return _normalize_supplier_transform_profile_filters(
        {
            SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN: selected_brand_source_name,
            SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES: selected_excluded_brand_values,
        }
    )


def render_profile_form_controls(
    *,
    selected_supplier_name: str,
    supplier_file_name: str,
    supplier_bytes: bytes,
    df_supplier,
    source_columns: list[str],
    saved_profile: dict[str, str],
    saved_composite_fields: dict[str, list[str]],
    saved_filters: dict[str, object],
    saved_profile_options: dict[str, bool],
) -> ProfileFormControls:
    file_token = _profile_file_token(
        selected_supplier_name=selected_supplier_name,
        supplier_file_name=supplier_file_name,
        supplier_bytes=supplier_bytes,
    )
    seed_key = f"supplier_transform_seeded_defaults_{file_token}"
    should_seed_defaults = not bool(st.session_state.get(seed_key, False))

    current_name_mode, composite_name_sources, target_to_source, composite_fields = (
        _render_name_mapping_controls(
            file_token=file_token,
            source_columns=source_columns,
            saved_profile=saved_profile,
            saved_composite_fields=saved_composite_fields,
            should_seed_defaults=should_seed_defaults,
        )
    )
    _render_target_mapping_controls(
        file_token=file_token,
        source_columns=source_columns,
        saved_profile=saved_profile,
        should_seed_defaults=should_seed_defaults,
        target_to_source=target_to_source,
    )
    strip_leading_zeros_from_sku = _render_sku_rule_controls(
        file_token=file_token,
        saved_profile_options=saved_profile_options,
        should_seed_defaults=should_seed_defaults,
    )
    current_profile_filters = _render_brand_filter_controls(
        file_token=file_token,
        df_supplier=df_supplier,
        source_columns=source_columns,
        saved_filters=saved_filters,
        should_seed_defaults=should_seed_defaults,
    )
    if should_seed_defaults:
        st.session_state[seed_key] = True
    return ProfileFormControls(
        file_token=file_token,
        current_name_mode=current_name_mode,
        composite_name_sources=composite_name_sources,
        target_to_source=target_to_source,
        composite_fields=composite_fields,
        current_profile_filters=current_profile_filters,
        strip_leading_zeros_from_sku=strip_leading_zeros_from_sku,
    )
