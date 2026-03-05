from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from .supplier_profile_utils import (
    SUPPLIER_HICORE_NAME_COLUMN,
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
    SUPPLIER_TRANSFORM_DEFAULT_FILTERS,
    SUPPLIER_TRANSFORM_DEFAULT_OPTIONS,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU,
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS,
    build_supplier_hicore_renamed_copy as _build_supplier_hicore_renamed_copy,
    filter_supplier_names as _filter_supplier_names,
    normalize_supplier_transform_profile_details as _normalize_supplier_transform_profile_details,
    normalize_supplier_transform_profile_filters as _normalize_supplier_transform_profile_filters,
    normalize_supplier_transform_profile_options as _normalize_supplier_transform_profile_options,
    selected_dataframe_row_index as _selected_dataframe_row_index,
    find_duplicate_names as _find_duplicate_names,
)
from .ui.common import (
    SUPPLIER_INDEX_PATH,
    SUPPLIER_PROFILE_MODE_EDITOR,
    SUPPLIER_PROFILE_MODE_OVERVIEW,
    SUPPLIER_TRANSFORM_PROFILES_PATH,
)
from .ui.data_io import _read_supplier_upload
from .ui.state import (
    _clear_supplier_state,
    _delete_supplier_transform_profile,
    _normalize_selected_supplier_for_options,
    _persist_supplier_transform_profile,
    _render_file_input,
    _request_supplier_profile_editor,
    _rerun,
    _split_suppliers_by_profile,
    _sync_selected_supplier_between_views,
)

_NAME_MODE_SINGLE = "single"
_NAME_MODE_COMPOSITE = "composite"


def _supplier_profile_summary_value(
    target_column: str,
    *,
    profile_mapping: dict[str, str],
    profile_composite_fields: dict[str, list[str]],
) -> str:
    if target_column in profile_composite_fields:
        return " + ".join(profile_composite_fields[target_column])
    return profile_mapping.get(target_column, "(ej mappad)")


def _supplier_file_unique_values(df_supplier: pd.DataFrame, *, column_name: str) -> list[str]:
    if column_name not in df_supplier.columns:
        return []

    unique_by_folded: dict[str, str] = {}
    for raw_value in df_supplier[column_name].tolist():
        if pd.isna(raw_value):
            continue
        value = str(raw_value).strip()
        if value == "" or value.casefold() == "nan":
            continue
        folded = value.casefold()
        if folded not in unique_by_folded:
            unique_by_folded[folded] = value
    return sorted(unique_by_folded.values(), key=lambda item: item.casefold())


def _render_supplier_profile_editor(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
) -> None:
    normalized_transform_supplier = _normalize_selected_supplier_for_options(
        st.session_state.get("supplier_internal_name"),
        supplier_options,
    )
    if normalized_transform_supplier is None:
        normalized_transform_supplier = _normalize_selected_supplier_for_options(
            st.session_state.get("supplier_profiles_active_supplier"),
            supplier_options,
        )
    if st.session_state.get("supplier_internal_name") != normalized_transform_supplier:
        st.session_state["supplier_internal_name"] = normalized_transform_supplier
    if st.session_state.get("supplier_transform_internal_name") != normalized_transform_supplier:
        st.session_state["supplier_transform_internal_name"] = normalized_transform_supplier

    st.subheader("Profilredigering")
    st.caption(
        "Matcha leverant\u00f6rens kolumner mot HiCore-kolumner och spara regler f\u00f6r den valda leverant\u00f6ren."
    )
    st.caption(
        f'Kolumnen "{SUPPLIER_HICORE_SUPPLIER_COLUMN}" s\u00e4tts fr\u00e5n vald leverant\u00f6r i leverant\u00f6rslistan.'
    )
    st.caption("F\u00f6rhandsvisningen visar bara de kolumner som matchas av profilreglerna.")

    supplier_file = _render_file_input(
        kind="supplier",
        label="Leverant\u00f6rsfil (.csv/.xlsx/.xls/.xlsm)",
        file_types=["csv", "xlsx", "xls", "xlsm"],
        uploader_key="supplier_transform_uploader",
    )

    if supplier_index_error:
        st.warning(
            f"Kunde inte l\u00e4sa {SUPPLIER_INDEX_PATH.name} vid uppstart: {supplier_index_error}"
        )
    if st.session_state.get("supplier_transform_profiles_load_error"):
        st.warning(
            "Kunde inte l\u00e4sa "
            f"{SUPPLIER_TRANSFORM_PROFILES_PATH.name} vid uppstart: "
            f"{st.session_state['supplier_transform_profiles_load_error']}"
        )
    if st.session_state.get("supplier_transform_profiles_save_error"):
        st.warning(
            f"Kunde inte spara {SUPPLIER_TRANSFORM_PROFILES_PATH.name}: "
            f"{st.session_state['supplier_transform_profiles_save_error']}"
        )
    if not supplier_options:
        st.warning(
            f"Inga leverant\u00f6rer hittades i {SUPPLIER_INDEX_PATH.name}. L\u00e4gg till leverant\u00f6rer f\u00f6rst."
        )
        return
    supplier_internal_name = st.selectbox(
        "Leverant\u00f6r",
        options=supplier_options,
        index=None,
        placeholder="V\u00e4lj leverant\u00f6r fr\u00e5n supplier_index...",
        key="supplier_internal_name",
    )
    selected_supplier_name = (
        str(supplier_internal_name).strip() if supplier_internal_name is not None else ""
    )
    if st.session_state.get("supplier_profiles_active_supplier") != (
        selected_supplier_name if selected_supplier_name != "" else None
    ):
        st.session_state["supplier_profiles_active_supplier"] = (
            selected_supplier_name if selected_supplier_name != "" else None
        )
    _sync_selected_supplier_between_views(
        selected_supplier_name if selected_supplier_name != "" else None,
        supplier_options,
        target_key="supplier_transform_internal_name",
    )
    supplier_transform_profiles_raw = st.session_state.get("supplier_transform_profiles", {})
    supplier_transform_profiles = (
        supplier_transform_profiles_raw if isinstance(supplier_transform_profiles_raw, dict) else {}
    )
    saved_profile: dict[str, str] = {}
    saved_composite_fields: dict[str, list[str]] = {}
    saved_filters = dict(SUPPLIER_TRANSFORM_DEFAULT_FILTERS)
    saved_profile_options = dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    if selected_supplier_name:
        raw_profile = supplier_transform_profiles.get(selected_supplier_name, {})
        if isinstance(raw_profile, dict):
            (
                saved_profile,
                saved_composite_fields,
                saved_filters,
                saved_profile_options,
            ) = _normalize_supplier_transform_profile_details(raw_profile)
    has_saved_profile = bool(saved_profile)

    action_col_back, action_col_delete, _ = st.columns([1, 1, 3])
    if action_col_back.button("Tillbaka", type="secondary", key="supplier_profile_back_button"):
        st.session_state["supplier_profiles_mode"] = SUPPLIER_PROFILE_MODE_OVERVIEW
        st.session_state["supplier_profiles_delete_confirm"] = False
        st.session_state["supplier_profiles_active_supplier"] = None
        _rerun()
    if action_col_delete.button(
        "Ta bort profil",
        type="secondary",
        disabled=not (selected_supplier_name != "" and has_saved_profile),
        key="supplier_profile_delete_button",
    ):
        st.session_state["supplier_profiles_delete_confirm"] = True
        _rerun()

    if st.session_state.get("supplier_profiles_delete_confirm", False):
        st.warning(
            f'\u00c4r du s\u00e4ker p\u00e5 att du vill ta bort profilen f\u00f6r "{selected_supplier_name}"?'
        )
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button(
            "Bekräfta radering",
            type="primary",
            key="supplier_profile_delete_confirm_button",
        ):
            delete_error = _delete_supplier_transform_profile(supplier_name=selected_supplier_name)
            st.session_state["supplier_profiles_delete_confirm"] = False
            if delete_error is not None:
                st.error(delete_error)
            else:
                st.session_state["supplier_profiles_mode"] = SUPPLIER_PROFILE_MODE_OVERVIEW
                st.session_state["supplier_profiles_active_supplier"] = None
                _clear_supplier_state()
                _rerun()
        if cancel_col.button("Avbryt", key="supplier_profile_delete_cancel_button"):
            st.session_state["supplier_profiles_delete_confirm"] = False
            _rerun()

    if selected_supplier_name != "":
        st.markdown(f"**Profil: {selected_supplier_name}**")
        st.markdown("**Nuvarande inställningar**")
        if has_saved_profile:
            saved_rows = [
                {
                    "HiCore-kolumn": target_column,
                    "Leverantörskolumn": _supplier_profile_summary_value(
                        target_column,
                        profile_mapping=saved_profile,
                        profile_composite_fields=saved_composite_fields,
                    ),
                }
                for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
            ]
            saved_rows.append(
                {
                    "HiCore-kolumn": SUPPLIER_HICORE_SUPPLIER_COLUMN,
                    "Leverantörskolumn": f"Värde från supplier_index: {selected_supplier_name}",
                }
            )
            st.dataframe(pd.DataFrame(saved_rows), use_container_width=True)
            st.caption(
                "SKU-regler: "
                f"ta bort inledande nollor = {'Ja' if saved_profile_options[SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS] else 'Nej'}, "
                f"ignorera rader utan SKU = {'Ja' if saved_profile_options[SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU] else 'Nej'}."
            )
            saved_brand_source = str(
                saved_filters.get(SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN, "")
            ).strip()
            saved_excluded_brands = [
                str(value)
                for value in saved_filters.get(
                    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
                    [],
                )
            ]
            if saved_brand_source != "" or saved_excluded_brands:
                st.caption(
                    "Varumärkesfilter: "
                    f"brand-kolumn = {saved_brand_source or '(ingen vald)'}, "
                    f"exkluderade värden = {', '.join(saved_excluded_brands) if saved_excluded_brands else '(inga)'}."
                )
        else:
            st.info("Ingen profil är sparad ännu för vald leverantör.")

    if supplier_file is None:
        if selected_supplier_name == "":
            st.info("V\u00e4lj leverant\u00f6r och ladda upp en leverant\u00f6rsfil f\u00f6r att mappa kolumner.")
        else:
            st.info(
                "Ladda upp en leverant\u00f6rsfil f\u00f6r att mappa kolumner f\u00f6r vald leverant\u00f6r. "
                "Uppladdning \u00e4r obligatorisk f\u00f6r att skapa eller uppdatera profil."
            )
        return

    supplier_file_name = str(supplier_file["name"])  # type: ignore[index]
    supplier_bytes = supplier_file["bytes"]  # type: ignore[index]
    try:
        df_supplier = _read_supplier_upload(supplier_file_name, supplier_bytes)
    except Exception as exc:
        st.error(f"Kunde inte l\u00e4sa leverant\u00f6rsfilen: {exc}")
        return

    source_columns = [str(col).strip() for col in df_supplier.columns]
    if not source_columns:
        st.warning("Leverant\u00f6rsfilen inneh\u00e5ller inga kolumnnamn.")
        return

    duplicate_source_columns = _find_duplicate_names(source_columns)
    if duplicate_source_columns:
        st.warning(
            "Filen inneh\u00e5ller dubblettkolumnnamn. Det kan g\u00f6ra mappningen tvetydig: "
            + ", ".join(duplicate_source_columns)
        )

    source_preview_rows = min(len(df_supplier), 10)
    source_preview_df = df_supplier.copy()
    source_preview_df.columns = source_columns
    st.caption(f"Antal kolumner i leverant\u00f6rsfilen: {len(source_columns)}")
    st.caption(
        "F\u00f6rhandsvisning av leverant\u00f6rsfilen "
        f"({source_preview_rows} f\u00f6rsta raderna med kolumnnamn)"
    )
    st.dataframe(
        source_preview_df.head(source_preview_rows),
        use_container_width=True,
    )

    if selected_supplier_name == "":
        st.info("V\u00e4lj leverant\u00f6r f\u00f6r att kunna ladda eller spara en profil.")
    elif saved_profile:
        valid_saved_targets = [
            target
            for target, source in saved_profile.items()
            if target in SUPPLIER_HICORE_RENAME_COLUMNS and source in source_columns
        ]
        valid_saved_targets.extend(
            [
                target
                for target, source_list in saved_composite_fields.items()
                if target in SUPPLIER_HICORE_RENAME_COLUMNS
                and all(source in source_columns for source in source_list)
            ]
        )
        missing_saved_targets = [
            target
            for target, source in saved_profile.items()
            if target in SUPPLIER_HICORE_RENAME_COLUMNS and source not in source_columns
        ]
        missing_saved_targets.extend(
            [
                target
                for target, source_list in saved_composite_fields.items()
                if target in SUPPLIER_HICORE_RENAME_COLUMNS
                and any(source not in source_columns for source in source_list)
            ]
        )
        saved_brand_source = str(
            saved_filters.get(SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN, "")
        ).strip()
        saved_excluded_brands = [
            str(value)
            for value in saved_filters.get(
                SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
                [],
            )
        ]
        if valid_saved_targets:
            st.success(
                f'Sparad profil hittad för "{selected_supplier_name}". '
                f"Förifyller {len(set(valid_saved_targets))} kolumnval."
            )
        if missing_saved_targets:
            st.warning(
                "Den sparade profilen matchar inte fullt ut mot aktuell fil. "
                "Välj om följande HiCore-kolumner: "
                + ", ".join(sorted(set(missing_saved_targets), key=lambda item: item.casefold()))
            )
        if saved_brand_source != "" and saved_brand_source not in source_columns:
            st.warning(
                "Den sparade profilens brand-kolumn finns inte i aktuell fil: "
                + saved_brand_source
            )
        elif saved_excluded_brands and saved_brand_source != "":
            current_brand_values = _supplier_file_unique_values(
                df_supplier,
                column_name=saved_brand_source,
            )
            current_brand_values_folded = {value.casefold() for value in current_brand_values}
            missing_saved_excluded = [
                brand_name
                for brand_name in saved_excluded_brands
                if brand_name.casefold() not in current_brand_values_folded
            ]
            if missing_saved_excluded:
                st.warning(
                    "Den sparade profilen innehåller exkluderade varumärken som inte finns i aktuell fil: "
                    + ", ".join(missing_saved_excluded)
                )
    elif selected_supplier_name:
        st.info(
            f'Ingen sparad profil finns för "{selected_supplier_name}". '
            "Matcha kolumnerna och spara en profil."
        )

    st.subheader("Matcha mot HiCore-kolumner")
    supplier_key_token = selected_supplier_name if selected_supplier_name != "" else "no_supplier"
    file_token = f"{Path(supplier_file_name).name}_{len(supplier_bytes)}_{supplier_key_token}"
    seed_key = f"supplier_transform_seeded_defaults_{file_token}"
    should_seed_defaults = not bool(st.session_state.get(seed_key, False))
    target_to_source: dict[str, str] = {}
    name_mode_key = f"supplier_transform_name_mode_{file_token}"
    if should_seed_defaults or name_mode_key not in st.session_state:
        st.session_state[name_mode_key] = (
            _NAME_MODE_COMPOSITE
            if saved_composite_fields.get(SUPPLIER_HICORE_NAME_COLUMN)
            else _NAME_MODE_SINGLE
        )

    st.markdown(f"**{SUPPLIER_HICORE_NAME_COLUMN}**")
    current_name_mode = str(st.session_state.get(name_mode_key, _NAME_MODE_SINGLE))
    if current_name_mode not in (_NAME_MODE_SINGLE, _NAME_MODE_COMPOSITE):
        current_name_mode = _NAME_MODE_SINGLE
        st.session_state[name_mode_key] = current_name_mode
    current_name_mode = st.radio(
        "Namnläge",
        options=[_NAME_MODE_SINGLE, _NAME_MODE_COMPOSITE],
        format_func=lambda value: "En kolumn" if value == _NAME_MODE_SINGLE else "Kombinera kolumner",
        horizontal=True,
        key=name_mode_key,
    )

    composite_name_sources: list[str] = []
    if current_name_mode == _NAME_MODE_SINGLE:
        name_widget_key = f"supplier_transform_map_{SUPPLIER_HICORE_NAME_COLUMN}_{file_token}"
        saved_name_source = saved_profile.get(SUPPLIER_HICORE_NAME_COLUMN)
        if saved_name_source is not None:
            normalized_saved_source = str(saved_name_source).strip()
            current_value = st.session_state.get(name_widget_key)
            current_value_normalized = "" if current_value is None else str(current_value).strip()
            if normalized_saved_source in source_columns and (
                should_seed_defaults
                or name_widget_key not in st.session_state
                or current_value_normalized == ""
                or current_value_normalized not in source_columns
            ):
                st.session_state[name_widget_key] = normalized_saved_source

        selected_name_source = st.selectbox(
            SUPPLIER_HICORE_NAME_COLUMN,
            options=source_columns,
            index=None,
            placeholder="Välj motsvarande kolumn i leverantörsfilen...",
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
            if idx < len(saved_name_parts):
                normalized_saved_source = str(saved_name_parts[idx]).strip()
                current_value = st.session_state.get(widget_key)
                current_value_normalized = "" if current_value is None else str(current_value).strip()
                if normalized_saved_source in source_columns and (
                    should_seed_defaults
                    or widget_key not in st.session_state
                    or current_value_normalized == ""
                    or current_value_normalized not in source_columns
                ):
                    st.session_state[widget_key] = normalized_saved_source

            selected_name_part = st.selectbox(
                f"Artikelnamn del {idx + 1}",
                options=source_columns,
                index=None,
                placeholder="Välj kolumn...",
                key=widget_key,
            )
            if selected_name_part is not None and str(selected_name_part).strip() != "":
                composite_name_sources.append(str(selected_name_part).strip())

    other_target_columns = [
        target_column
        for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
        if target_column != SUPPLIER_HICORE_NAME_COLUMN
    ]
    for target_column in other_target_columns:
        widget_key = f"supplier_transform_map_{target_column}_{file_token}"
        saved_source = saved_profile.get(target_column)
        if saved_source is not None:
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

        selected_source = st.selectbox(
            target_column,
            options=source_columns,
            index=None,
            placeholder="Välj motsvarande kolumn i leverantörsfilen...",
            key=widget_key,
        )
        if selected_source is not None and str(selected_source).strip() != "":
            target_to_source[target_column] = str(selected_source).strip()

    composite_fields: dict[str, list[str]] = {}
    if current_name_mode == _NAME_MODE_COMPOSITE:
        composite_fields[SUPPLIER_HICORE_NAME_COLUMN] = composite_name_sources

    st.subheader("SKU-regler")
    st.caption(f'Gäller kolumnen "{SUPPLIER_HICORE_SKU_COLUMN}" när den är mappad.')
    strip_zeros_key = f"supplier_transform_option_strip_zeros_{file_token}"
    ignore_missing_sku_key = f"supplier_transform_option_ignore_missing_sku_{file_token}"
    if should_seed_defaults or strip_zeros_key not in st.session_state:
        st.session_state[strip_zeros_key] = saved_profile_options[
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS
        ]
    if should_seed_defaults or ignore_missing_sku_key not in st.session_state:
        st.session_state[ignore_missing_sku_key] = saved_profile_options[
            SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU
        ]
    if should_seed_defaults:
        st.session_state[seed_key] = True
    strip_leading_zeros_from_sku = bool(
        st.checkbox("Ta bort inledande nollor i SKU", key=strip_zeros_key)
    )
    ignore_rows_missing_sku = bool(
        st.checkbox("Ignorera rader som saknar SKU", key=ignore_missing_sku_key)
    )

    st.subheader("Varumärkesfilter")
    brand_source_key = f"supplier_transform_brand_source_{file_token}"
    saved_brand_source = str(saved_filters.get(SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN, "")).strip()
    if should_seed_defaults and saved_brand_source in source_columns:
        st.session_state[brand_source_key] = saved_brand_source
    elif should_seed_defaults and brand_source_key not in st.session_state:
        st.session_state[brand_source_key] = None

    selected_brand_source = st.selectbox(
        "Brand-kolumn för exkludering",
        options=source_columns,
        index=None,
        placeholder="Välj brand-kolumn i leverantörsfilen...",
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
    current_profile_filters = _normalize_supplier_transform_profile_filters(
        {
            SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN: selected_brand_source_name,
            SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES: selected_excluded_brand_values,
        }
    )

    duplicate_name_sources = _find_duplicate_names(composite_name_sources)
    if duplicate_name_sources:
        st.error(
            "Samma kolumn kan inte anv\u00e4ndas flera g\u00e5nger i det sammansatta artikelnamnet: "
            + ", ".join(duplicate_name_sources)
        )

    missing_target_columns = [
        column
        for column in SUPPLIER_HICORE_RENAME_COLUMNS
        if column not in target_to_source and column not in composite_fields
    ]
    if duplicate_name_sources:
        return
    if selected_supplier_name == "":
        st.info(
            f'V\u00e4lj "{SUPPLIER_HICORE_SUPPLIER_COLUMN}" fr\u00e5n leverant\u00f6rslistan f\u00f6r att arbeta vidare med profilen.'
        )
        return
    if not target_to_source and not composite_fields:
        st.info("Matcha minst en HiCore-kolumn f\u00f6r att visa f\u00f6rhandsvisningen.")
        return
    if current_name_mode == _NAME_MODE_COMPOSITE and len(composite_name_sources) < 2:
        st.info("V\u00e4lj minst tv\u00e5 kolumner f\u00f6r att bygga ett sammansatt artikelnamn.")
        return
    if (
        current_profile_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
        and str(current_profile_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]).strip() == ""
    ):
        st.info("V\u00e4lj en brand-kolumn innan du exkluderar varum\u00e4rkesv\u00e4rden.")
        return
    if missing_target_columns:
        st.info(
            "Omatchade HiCore-kolumner tas inte med i f\u00f6rhandsvisningen: "
            + ", ".join(missing_target_columns)
        )
    if (
        SUPPLIER_HICORE_SKU_COLUMN not in target_to_source
        and (strip_leading_zeros_from_sku or ignore_rows_missing_sku)
    ):
        st.info(
            f'SKU-reglerna används först när "{SUPPLIER_HICORE_SKU_COLUMN}" är mappad.'
        )

    try:
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
                for value in current_profile_filters[
                    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES
                ]
            ],
            strip_leading_zeros_from_sku=strip_leading_zeros_from_sku,
            ignore_rows_missing_sku=ignore_rows_missing_sku,
        )
    except Exception as exc:
        st.error(str(exc))
        return

    profile_save_error: Optional[str] = None
    profile_save_success: Optional[str] = None
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
    if has_saved_complete_profile and selected_supplier_name != "":
        st.caption("Aktuell kolumnmappning, namnregler, filter och SKU-regler matchar den sparade profilen.")

    if st.button(
        save_profile_label,
        type="secondary",
        key=f"save_supplier_transform_profile_{file_token}",
    ):
        profile_save_error = _persist_supplier_transform_profile(
            supplier_name=selected_supplier_name,
            target_to_source=current_profile_mapping,
            composite_fields=current_profile_composite_fields,
            filters=current_profile_filters,
            options=current_profile_options,
        )
        if profile_save_error is None:
            profile_save_success = f'Profil sparad för "{selected_supplier_name}".'
            saved_profile = dict(current_profile_mapping)
            saved_composite_fields = {
                target: list(source_columns_for_target)
                for target, source_columns_for_target in current_profile_composite_fields.items()
            }
            saved_filters = dict(current_profile_filters)
            saved_profile_options = dict(current_profile_options)
            supplier_transform_profiles = st.session_state.get("supplier_transform_profiles", {})

    if profile_save_error:
        st.error(profile_save_error)
    if profile_save_success:
        st.success(profile_save_success)

    mapping_rows = [
        {
            "HiCore-kolumn": target_column,
            "Leverant\u00f6rskolumn": _supplier_profile_summary_value(
                target_column,
                profile_mapping=current_profile_mapping,
                profile_composite_fields=current_profile_composite_fields,
            ),
        }
        for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
        if target_column in current_profile_mapping or target_column in current_profile_composite_fields
    ]
    mapping_rows.append(
        {
            "HiCore-kolumn": SUPPLIER_HICORE_SUPPLIER_COLUMN,
            "Leverant\u00f6rskolumn": f"V\u00e4rde fr\u00e5n supplier_index: {selected_supplier_name}",
        }
    )
    if missing_target_columns:
        st.success(
            "Delvis kolumnmappning klar. Omatchade HiCore-kolumner utel\u00e4mnas i f\u00f6rhandsvisningen nedan."
        )
    else:
        st.success("Kolumnmappningen \u00e4r komplett. F\u00f6rhandsvisning finns nedan.")
    st.caption(
        "SKU-regler i f\u00f6rhandsvisningen: "
        f"ta bort inledande nollor = {'Ja' if strip_leading_zeros_from_sku else 'Nej'}, "
        f"ignorera rader utan SKU = {'Ja' if ignore_rows_missing_sku else 'Nej'}."
    )
    st.caption(
        "Varumärkesfilter i förhandsvisningen: "
        f"brand-kolumn = {str(current_profile_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]).strip() or '(ingen vald)'}, "
        f"exkluderade värden = "
        + (
            ", ".join(
                [
                    str(value)
                    for value in current_profile_filters[
                        SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES
                    ]
                ]
            )
            if current_profile_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
            else "(inga)"
        )
        + "."
    )
    st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True)

    preview_rows = min(len(renamed_df), 20)
    st.caption(f"F\u00f6rhandsvisning av transformerade kolumner ({preview_rows} f\u00f6rsta raderna)")
    st.dataframe(renamed_df.head(preview_rows), use_container_width=True)




def _render_supplier_profiles_overview(*, supplier_options: list[str]) -> None:
    st.subheader("Leverantörsprofiler")
    st.caption("Profilerna är ett fristående bibliotek. Välj leverantör för att öppna eller skapa profil.")

    search_query = st.text_input(
        "Sök leverantör",
        placeholder="Sök i båda listorna...",
        key="supplier_profiles_search_query",
    )
    suppliers_with_profile, suppliers_without_profile = _split_suppliers_by_profile(supplier_options)
    filtered_with_profile = _filter_supplier_names(suppliers_with_profile, search_query)
    filtered_without_profile = _filter_supplier_names(suppliers_without_profile, search_query)

    with_col, without_col = st.columns(2)

    with with_col:
        st.markdown(f"**Har profil ({len(filtered_with_profile)}/{len(suppliers_with_profile)})**")
        selected_with_profile: Optional[str] = None
        if filtered_with_profile:
            st.caption("Välj leverantör med profil")
            with st.container(height=320, border=True):
                with_profile_event = st.dataframe(
                    pd.DataFrame({"Leverantör": filtered_with_profile}),
                    hide_index=True,
                    use_container_width=True,
                    height=300,
                    key="supplier_profiles_with_profile_table",
                    on_select="rerun",
                    selection_mode="single-cell",
                )
            selected_idx = _selected_dataframe_row_index(with_profile_event)
            if selected_idx is not None:
                if 0 <= selected_idx < len(filtered_with_profile):
                    selected_with_profile = filtered_with_profile[selected_idx]
        else:
            st.caption("Inga leverantörer matchar sökningen.")

        if st.button(
            "\u00d6ppna profil",
            type="secondary",
            disabled=selected_with_profile is None,
            key="open_supplier_profile_from_overview_button",
        ):
            _request_supplier_profile_editor(str(selected_with_profile))

    with without_col:
        st.markdown(
            f"**Saknar profil ({len(filtered_without_profile)}/{len(suppliers_without_profile)})**"
        )
        selected_without_profile: Optional[str] = None
        if filtered_without_profile:
            st.caption("Välj leverantör utan profil")
            with st.container(height=320, border=True):
                without_profile_event = st.dataframe(
                    pd.DataFrame({"Leverantör": filtered_without_profile}),
                    hide_index=True,
                    use_container_width=True,
                    height=300,
                    key="supplier_profiles_without_profile_table",
                    on_select="rerun",
                    selection_mode="single-cell",
                )
            selected_idx = _selected_dataframe_row_index(without_profile_event)
            if selected_idx is not None:
                if 0 <= selected_idx < len(filtered_without_profile):
                    selected_without_profile = filtered_without_profile[selected_idx]
        else:
            st.caption("Inga leverantörer matchar sökningen.")

        if st.button(
            "Skapa profil",
            type="secondary",
            disabled=selected_without_profile is None,
            key="create_supplier_profile_from_overview_button",
        ):
            _request_supplier_profile_editor(str(selected_without_profile))



def _render_supplier_transform_tab(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
) -> None:
    if not supplier_options:
        st.warning(
            f"Inga leverantörer hittades i {SUPPLIER_INDEX_PATH.name}. Lägg till leverantörer först."
        )
        return

    profile_mode = st.session_state.get("supplier_profiles_mode", SUPPLIER_PROFILE_MODE_OVERVIEW)
    if profile_mode not in (SUPPLIER_PROFILE_MODE_OVERVIEW, SUPPLIER_PROFILE_MODE_EDITOR):
        profile_mode = SUPPLIER_PROFILE_MODE_OVERVIEW
        st.session_state["supplier_profiles_mode"] = profile_mode

    if profile_mode == SUPPLIER_PROFILE_MODE_EDITOR:
        _render_supplier_profile_editor(
            supplier_options=supplier_options,
            supplier_index_error=supplier_index_error,
        )
        return

    if supplier_index_error:
        st.warning(
            f"Kunde inte läsa {SUPPLIER_INDEX_PATH.name} vid uppstart: {supplier_index_error}"
        )
    if st.session_state.get("supplier_transform_profiles_load_error"):
        st.warning(
            "Kunde inte läsa "
            f"{SUPPLIER_TRANSFORM_PROFILES_PATH.name} vid uppstart: "
            f"{st.session_state['supplier_transform_profiles_load_error']}"
        )
    if st.session_state.get("supplier_transform_profiles_save_error"):
        st.warning(
            f"Kunde inte spara {SUPPLIER_TRANSFORM_PROFILES_PATH.name}: "
            f"{st.session_state['supplier_transform_profiles_save_error']}"
        )
    _render_supplier_profiles_overview(supplier_options=supplier_options)
