from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_SUPPLIER_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
    SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU,
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS,
)
from ...common import (
    SUPPLIER_INDEX_PATH,
    SUPPLIER_PROFILE_MODE_OVERVIEW,
    SUPPLIER_TRANSFORM_PROFILES_PATH,
)
from ...io.uploads import _read_supplier_upload
from ...session.file_inputs import render_file_input as _render_file_input
from ...session.navigation import rerun as _rerun
from ...session.profile_state import (
    delete_supplier_transform_profile as _delete_supplier_transform_profile,
)
from ...session.run_state import clear_supplier_state as _clear_supplier_state
from ...session.supplier_selection import (
    normalize_selected_supplier_for_options as _normalize_selected_supplier_for_options,
    sync_selected_supplier_between_views as _sync_selected_supplier_between_views,
)
from ...shared.presentation import with_one_based_index as _with_one_based_index
from .form import _render_profile_mapping_form
from .view_model import (
    selected_supplier_profile_state as _selected_supplier_profile_state,
    supplier_file_prompt_message as _supplier_file_prompt_message,
    supplier_file_unique_values as _supplier_file_unique_values,
    supplier_profile_filter_summary as _supplier_profile_filter_summary,
    supplier_profile_file_messages as _supplier_profile_file_messages,
    supplier_profile_summary_rows as _supplier_profile_summary_rows,
    supplier_source_preview_state as _supplier_source_preview_state,
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
        session_state=st.session_state,
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
        st.session_state,
        selected_supplier_name if selected_supplier_name != "" else None,
        supplier_options,
        target_key="supplier_transform_internal_name",
    )
    supplier_transform_profiles_raw = st.session_state.get("supplier_transform_profiles", {})
    supplier_transform_profiles = (
        supplier_transform_profiles_raw if isinstance(supplier_transform_profiles_raw, dict) else {}
    )
    profile_state = _selected_supplier_profile_state(
        selected_supplier_name=selected_supplier_name,
        supplier_transform_profiles_raw=supplier_transform_profiles,
    )
    saved_profile = profile_state.mapping
    saved_composite_fields = profile_state.composite_fields
    saved_filters = profile_state.filters
    saved_profile_options = profile_state.options
    has_saved_profile = profile_state.has_saved_profile

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
            delete_error = _delete_supplier_transform_profile(
                st.session_state,
                supplier_name=selected_supplier_name,
            )
            st.session_state["supplier_profiles_delete_confirm"] = False
            if delete_error is not None:
                st.error(delete_error)
            else:
                st.session_state["supplier_profiles_mode"] = SUPPLIER_PROFILE_MODE_OVERVIEW
                st.session_state["supplier_profiles_active_supplier"] = None
                _clear_supplier_state(st.session_state)
                _rerun()
        if cancel_col.button("Avbryt", key="supplier_profile_delete_cancel_button"):
            st.session_state["supplier_profiles_delete_confirm"] = False
            _rerun()

    if selected_supplier_name != "":
        st.markdown(f"**Profil: {selected_supplier_name}**")
        st.markdown("**Nuvarande inställningar**")
        if has_saved_profile:
            st.dataframe(
                _with_one_based_index(
                    pd.DataFrame(
                        _supplier_profile_summary_rows(
                            selected_supplier_name=selected_supplier_name,
                            profile_mapping=saved_profile,
                            profile_composite_fields=saved_composite_fields,
                        )
                    )
                ),
                use_container_width=True,
            )
            st.caption(
                "SKU-regler: "
                f"ta bort inledande nollor = {'Ja' if saved_profile_options[SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS] else 'Nej'}, "
                f"ignorera rader utan SKU = {'Ja' if saved_profile_options[SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU] else 'Nej'}."
            )
            filter_summary = _supplier_profile_filter_summary(saved_filters)
            if filter_summary is not None:
                st.caption(filter_summary)
        else:
            st.info("Ingen profil är sparad ännu för vald leverantör.")

    if supplier_file is None:
        supplier_file_prompt = _supplier_file_prompt_message(
            selected_supplier_name=selected_supplier_name,
        )
        getattr(st, supplier_file_prompt.level)(supplier_file_prompt.text)
        return

    supplier_file_name = str(supplier_file["name"])  # type: ignore[index]
    supplier_bytes = supplier_file["bytes"]  # type: ignore[index]
    try:
        df_supplier = _read_supplier_upload(supplier_file_name, supplier_bytes)
    except Exception as exc:
        st.error(f"Kunde inte l\u00e4sa leverant\u00f6rsfilen: {exc}")
        return

    source_preview_state = _supplier_source_preview_state(df_supplier)
    source_columns = source_preview_state.source_columns
    if not source_columns:
        st.warning("Leverant\u00f6rsfilen inneh\u00e5ller inga kolumnnamn.")
        return

    if source_preview_state.duplicate_source_columns:
        st.warning(
            "Filen inneh\u00e5ller dubblettkolumnnamn. Det kan g\u00f6ra mappningen tvetydig: "
            + ", ".join(source_preview_state.duplicate_source_columns)
        )

    st.caption(f"Antal kolumner i leverant\u00f6rsfilen: {len(source_columns)}")
    st.caption(
        "F\u00f6rhandsvisning av leverant\u00f6rsfilen "
        f"({source_preview_state.preview_row_count} f\u00f6rsta raderna med kolumnnamn)"
    )
    st.dataframe(
        _with_one_based_index(
            source_preview_state.preview_df.head(source_preview_state.preview_row_count)
        ),
        use_container_width=True,
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
    current_brand_values: list[str] = []
    if saved_excluded_brands and saved_brand_source != "" and saved_brand_source in source_columns:
        current_brand_values = _supplier_file_unique_values(
            df_supplier,
            column_name=saved_brand_source,
        )
    for message in _supplier_profile_file_messages(
        selected_supplier_name=selected_supplier_name,
        saved_profile=saved_profile,
        saved_composite_fields=saved_composite_fields,
        source_columns=source_columns,
        saved_brand_source=saved_brand_source,
        saved_excluded_brands=saved_excluded_brands,
        current_brand_values=current_brand_values,
    ):
        getattr(st, message.level)(message.text)

    _render_profile_mapping_form(
        selected_supplier_name=selected_supplier_name,
        supplier_file_name=supplier_file_name,
        supplier_bytes=supplier_bytes,
        df_supplier=df_supplier,
        source_columns=source_columns,
        saved_profile=saved_profile,
        saved_composite_fields=saved_composite_fields,
        saved_filters=saved_filters,
        saved_profile_options=saved_profile_options,
        supplier_transform_profiles=supplier_transform_profiles,
    )

