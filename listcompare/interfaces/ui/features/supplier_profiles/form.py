from __future__ import annotations

from typing import Optional

import streamlit as st

from listcompare.core.suppliers.profile import (
    SUPPLIER_HICORE_SKU_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN,
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES,
)
from ...shared.presentation import with_one_based_index as _with_one_based_index
from ...session.profile_state import (
    persist_supplier_transform_profile as _persist_supplier_transform_profile,
)
from .form_controls import (
    NAME_MODE_COMPOSITE,
    render_profile_form_controls as _render_profile_form_controls,
)
from .form_logic import (
    build_profile_preview_artifacts as _build_profile_preview_artifacts,
    evaluate_profile_preview as _evaluate_profile_preview,
)


def _render_profile_mapping_form(
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
    supplier_transform_profiles: dict[str, dict[str, object]],
) -> None:
    st.subheader("Matcha mot HiCore-kolumner")
    control_state = _render_profile_form_controls(
        selected_supplier_name=selected_supplier_name,
        supplier_file_name=supplier_file_name,
        supplier_bytes=supplier_bytes,
        df_supplier=df_supplier,
        source_columns=source_columns,
        saved_profile=saved_profile,
        saved_composite_fields=saved_composite_fields,
        saved_filters=saved_filters,
        saved_profile_options=saved_profile_options,
    )

    preview_decision = _evaluate_profile_preview(
        selected_supplier_name=selected_supplier_name,
        target_to_source=control_state.target_to_source,
        composite_fields=control_state.composite_fields,
        composite_name_sources=control_state.composite_name_sources,
        current_name_mode=control_state.current_name_mode,
        composite_name_mode=NAME_MODE_COMPOSITE,
        current_profile_filters=control_state.current_profile_filters,
        strip_leading_zeros_from_sku=control_state.strip_leading_zeros_from_sku,
        ignore_rows_missing_sku=control_state.ignore_rows_missing_sku,
    )
    if preview_decision.blocking_error:
        st.error(preview_decision.blocking_error)
        return
    if preview_decision.blocking_info:
        st.info(preview_decision.blocking_info)
        return
    if preview_decision.show_missing_target_info:
        st.info(
            "Omatchade HiCore-kolumner tas inte med i f\u00f6rhandsvisningen: "
            + ", ".join(preview_decision.missing_target_columns)
        )
    if preview_decision.show_sku_rule_info:
        st.info(
            f'SKU-reglerna anv\u00e4nds f\u00f6rst n\u00e4r "{SUPPLIER_HICORE_SKU_COLUMN}" \u00e4r mappad.'
        )

    try:
        preview_artifacts = _build_profile_preview_artifacts(
            df_supplier=df_supplier,
            selected_supplier_name=selected_supplier_name,
            supplier_transform_profiles=supplier_transform_profiles,
            saved_profile=saved_profile,
            saved_composite_fields=saved_composite_fields,
            saved_filters=saved_filters,
            saved_profile_options=saved_profile_options,
            target_to_source=control_state.target_to_source,
            composite_fields=control_state.composite_fields,
            current_profile_filters=control_state.current_profile_filters,
            strip_leading_zeros_from_sku=control_state.strip_leading_zeros_from_sku,
            ignore_rows_missing_sku=control_state.ignore_rows_missing_sku,
        )
    except Exception as exc:
        st.error(str(exc))
        return

    profile_save_error: Optional[str] = None
    profile_save_success: Optional[str] = None
    renamed_df = preview_artifacts.renamed_df
    current_profile_state = preview_artifacts.current_profile_state
    save_state = preview_artifacts.save_state
    if save_state.has_saved_complete_profile and selected_supplier_name != "":
        st.caption(
            "Aktuell kolumnmappning, namnregler, filter och SKU-regler matchar den sparade profilen."
        )

    if st.button(
        save_state.save_profile_label,
        type="secondary",
        key=f"save_supplier_transform_profile_{control_state.file_token}",
    ):
        profile_save_error = _persist_supplier_transform_profile(
            st.session_state,
            supplier_name=selected_supplier_name,
            target_to_source=current_profile_state.mapping,
            composite_fields=current_profile_state.composite_fields,
            filters=control_state.current_profile_filters,
            options=current_profile_state.options,
        )
        if profile_save_error is None:
            profile_save_success = f'Profil sparad f\u00f6r "{selected_supplier_name}".'

    if profile_save_error:
        st.error(profile_save_error)
    if profile_save_success:
        st.success(profile_save_success)

    if preview_decision.missing_target_columns:
        st.success(
            "Delvis kolumnmappning klar. Omatchade HiCore-kolumner utel\u00e4mnas i f\u00f6rhandsvisningen nedan."
        )
    else:
        st.success("Kolumnmappningen \u00e4r komplett. F\u00f6rhandsvisning finns nedan.")
    st.caption(
        "SKU-regler i f\u00f6rhandsvisningen: "
        f"ta bort inledande nollor = {'Ja' if control_state.strip_leading_zeros_from_sku else 'Nej'}, "
        f"ignorera rader utan SKU = {'Ja' if control_state.ignore_rows_missing_sku else 'Nej'}."
    )
    st.caption(
        "Varum\u00e4rkesfilter i f\u00f6rhandsvisningen: "
        f"brand-kolumn = {str(control_state.current_profile_filters[SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN]).strip() or '(ingen vald)'}, "
        f"exkluderade v\u00e4rden = "
        + (
            ", ".join(
                [
                    str(value)
                    for value in control_state.current_profile_filters[
                        SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES
                    ]
                ]
            )
            if control_state.current_profile_filters[SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES]
            else "(inga)"
        )
        + "."
    )
    preview_rows = min(len(renamed_df), 20)
    st.caption(
        f"F\u00f6rhandsvisning av transformerade kolumner ({preview_rows} f\u00f6rsta raderna)"
    )
    st.dataframe(_with_one_based_index(renamed_df.head(preview_rows)), use_container_width=True)
