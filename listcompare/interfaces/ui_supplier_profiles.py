from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from .supplier_profile_utils import (
    SUPPLIER_HICORE_RENAME_COLUMNS,
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
    SUPPLIER_TRANSFORM_DEFAULT_OPTIONS,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU,
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS,
    build_supplier_hicore_renamed_copy as _build_supplier_hicore_renamed_copy,
    filter_supplier_names as _filter_supplier_names,
    normalize_supplier_transform_profile as _normalize_supplier_transform_profile,
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
from .ui.data_io import _df_excel_bytes, _read_supplier_upload
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
def _render_supplier_profile_editor(
    *,
    supplier_options: list[str],
    supplier_index_error: Optional[str],
) -> None:
    normalized_transform_supplier = _normalize_selected_supplier_for_options(
        st.session_state.get("supplier_internal_name"),
        supplier_options,
    )
    if st.session_state.get("supplier_internal_name") != normalized_transform_supplier:
        st.session_state["supplier_internal_name"] = normalized_transform_supplier
    if st.session_state.get("supplier_transform_internal_name") != normalized_transform_supplier:
        st.session_state["supplier_transform_internal_name"] = normalized_transform_supplier

    st.subheader("Profilredigering")
    st.caption(
        "Matcha leverant\u00f6rens kolumner mot HiCore-kolumner och exportera en kopia med omd\u00f6pta kolumnnamn."
    )
    st.caption(
        f'Kolumnen "{SUPPLIER_HICORE_SUPPLIER_COLUMN}" s\u00e4tts fr\u00e5n vald leverant\u00f6r i leverant\u00f6rslistan.'
    )
    st.caption("Endast matchade kolumner exporteras. Resultatet exporteras som Excel (.xlsx).")

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
    saved_profile_options = dict(SUPPLIER_TRANSFORM_DEFAULT_OPTIONS)
    if selected_supplier_name:
        raw_profile = supplier_transform_profiles.get(selected_supplier_name, {})
        if isinstance(raw_profile, dict):
            saved_profile, saved_profile_options = _normalize_supplier_transform_profile(raw_profile)
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
                    "Leverantörskolumn": saved_profile.get(target_column, "(ej mappad)"),
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

    st.caption(f"Antal kolumner i leverant\u00f6rsfilen: {len(source_columns)}")
    st.dataframe(
        pd.DataFrame({"Leverant\u00f6rskolumner": source_columns}),
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
        missing_saved_targets = [
            target
            for target, source in saved_profile.items()
            if target in SUPPLIER_HICORE_RENAME_COLUMNS and source not in source_columns
        ]
        if valid_saved_targets:
            st.success(
                f'Sparad profil hittad för "{selected_supplier_name}". '
                f"Förifyller {len(valid_saved_targets)} kolumnval."
            )
        if missing_saved_targets:
            st.warning(
                "Den sparade profilen matchar inte fullt ut mot aktuell fil. "
                "Välj om följande HiCore-kolumner: "
                + ", ".join(missing_saved_targets)
            )
    elif selected_supplier_name:
        st.info(
            f'Ingen sparad profil finns för "{selected_supplier_name}". '
            "Matcha kolumnerna och spara en profil."
        )

    st.subheader("Matcha mot HiCore-kolumner")
    supplier_key_token = selected_supplier_name if selected_supplier_name != "" else "no_supplier"
    file_token = f"{Path(supplier_file_name).name}_{len(supplier_bytes)}_{supplier_key_token}"
    target_to_source: dict[str, str] = {}

    for idx, target_column in enumerate(SUPPLIER_HICORE_RENAME_COLUMNS):
        widget_key = f"supplier_transform_map_{idx}_{file_token}"
        saved_source = saved_profile.get(target_column)
        if (
            widget_key not in st.session_state
            and saved_source is not None
            and str(saved_source).strip() in source_columns
        ):
            st.session_state[widget_key] = str(saved_source).strip()

        selected_source = st.selectbox(
            target_column,
            options=source_columns,
            index=None,
            placeholder="V\u00e4lj motsvarande kolumn i leverant\u00f6rsfilen...",
            key=widget_key,
        )
        if selected_source is not None and str(selected_source).strip() != "":
            target_to_source[target_column] = str(selected_source).strip()

    st.subheader("SKU-regler")
    st.caption(f'Gäller kolumnen "{SUPPLIER_HICORE_SKU_COLUMN}" när den är mappad.')
    strip_zeros_key = f"supplier_transform_option_strip_zeros_{file_token}"
    ignore_missing_sku_key = f"supplier_transform_option_ignore_missing_sku_{file_token}"
    if strip_zeros_key not in st.session_state:
        st.session_state[strip_zeros_key] = saved_profile_options[
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS
        ]
    if ignore_missing_sku_key not in st.session_state:
        st.session_state[ignore_missing_sku_key] = saved_profile_options[
            SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU
        ]
    strip_leading_zeros_from_sku = bool(
        st.checkbox("Ta bort inledande nollor i SKU", key=strip_zeros_key)
    )
    ignore_rows_missing_sku = bool(
        st.checkbox("Ignorera rader som saknar SKU", key=ignore_missing_sku_key)
    )

    selected_sources = [target_to_source[target] for target in target_to_source]
    duplicate_selected_sources = _find_duplicate_names(selected_sources)
    if duplicate_selected_sources:
        st.error(
            "Du har valt samma leverant\u00f6rskolumn flera g\u00e5nger: "
            + ", ".join(duplicate_selected_sources)
        )

    missing_target_columns = [
        column for column in SUPPLIER_HICORE_RENAME_COLUMNS if column not in target_to_source
    ]
    if duplicate_selected_sources:
        return
    if selected_supplier_name == "":
        st.info(
            f'V\u00e4lj "{SUPPLIER_HICORE_SUPPLIER_COLUMN}" fr\u00e5n leverant\u00f6rslistan f\u00f6r att skapa exportfilen.'
        )
        return
    if not target_to_source:
        st.info("Matcha minst en HiCore-kolumn f\u00f6r att skapa exportfilen.")
        return
    if missing_target_columns:
        st.info(
            "Omatchade HiCore-kolumner tas inte med i exportfilen: "
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
    current_profile_options = _normalize_supplier_transform_profile_options(
        {
            SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: strip_leading_zeros_from_sku,
            SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU: ignore_rows_missing_sku,
        }
    )
    has_saved_complete_profile = (
        saved_profile == current_profile_mapping
        and saved_profile_options == current_profile_options
    )
    save_profile_label = (
        "Uppdatera profil"
        if selected_supplier_name in supplier_transform_profiles
        else "Spara profil"
    )
    if has_saved_complete_profile and selected_supplier_name != "":
        st.caption("Aktuell kolumnmappning och SKU-regler matchar den sparade profilen.")

    if st.button(
        save_profile_label,
        type="secondary",
        key=f"save_supplier_transform_profile_{file_token}",
    ):
        profile_save_error = _persist_supplier_transform_profile(
            supplier_name=selected_supplier_name,
            target_to_source=current_profile_mapping,
            options=current_profile_options,
        )
        if profile_save_error is None:
            profile_save_success = f'Profil sparad för "{selected_supplier_name}".'
            saved_profile = dict(current_profile_mapping)
            saved_profile_options = dict(current_profile_options)
            supplier_transform_profiles = st.session_state.get("supplier_transform_profiles", {})

    if profile_save_error:
        st.error(profile_save_error)
    if profile_save_success:
        st.success(profile_save_success)

    mapping_rows = [
        {
            "HiCore-kolumn": target_column,
            "Leverant\u00f6rskolumn": target_to_source[target_column],
        }
        for target_column in SUPPLIER_HICORE_RENAME_COLUMNS
        if target_column in target_to_source
    ]
    mapping_rows.append(
        {
            "HiCore-kolumn": SUPPLIER_HICORE_SUPPLIER_COLUMN,
            "Leverant\u00f6rskolumn": f"V\u00e4rde fr\u00e5n supplier_index: {selected_supplier_name}",
        }
    )
    if missing_target_columns:
        st.success(
            "Delvis kolumnmappning klar. Omatchade HiCore-kolumner utel\u00e4mnas i exportfilen."
        )
    else:
        st.success("Kolumnmappningen \u00e4r komplett. Exportfilen \u00e4r klar.")
    st.caption(
        "SKU-regler i exporten: "
        f"ta bort inledande nollor = {'Ja' if strip_leading_zeros_from_sku else 'Nej'}, "
        f"ignorera rader utan SKU = {'Ja' if ignore_rows_missing_sku else 'Nej'}."
    )
    st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True)

    preview_rows = min(len(renamed_df), 20)
    st.caption(f"F\u00f6rhandsvisning av resultatet ({preview_rows} f\u00f6rsta raderna)")
    st.dataframe(renamed_df.head(preview_rows), use_container_width=True)

    export_file_name = f"{Path(supplier_file_name).stem}_hicore_kolumnnamn.xlsx"
    st.download_button(
        label="Ladda ner ombyggd leverant\u00f6rsfil (Excel)",
        data=_df_excel_bytes(renamed_df, sheet_name="HiCore-format"),
        file_name=export_file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_supplier_hicore_renamed_{file_token}",
    )



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
