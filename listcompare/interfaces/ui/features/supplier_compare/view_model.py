from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class UiMessage:
    level: str
    text: str


@dataclass(frozen=True)
class SupplierCompareFlags:
    has_prepared_supplier_df: bool
    has_pending_conflicts: bool
    can_prepare_uploaded_file: bool
    can_run: bool
    can_manage_profile: bool
    profile_action_label: str
    show_prepare_hint: bool


def build_supplier_compare_flags(
    *,
    supplier_file_present: bool,
    hicore_file_present: bool,
    selected_supplier_name: str,
    profile_exists: bool,
    profile_ready: bool,
    supplier_file_read_error: Optional[str],
    file_matches_profile_output_format: bool,
    profile_matches_uploaded_file: bool,
    df_supplier_uploaded: Optional[pd.DataFrame],
    current_prepare_signature: Optional[str],
    stored_prepare_signature: object,
    prepared_supplier_df: object,
    prepare_analysis: object,
) -> SupplierCompareFlags:
    has_prepared_supplier_df = (
        current_prepare_signature is not None
        and stored_prepare_signature == current_prepare_signature
        and isinstance(prepared_supplier_df, pd.DataFrame)
    )
    has_pending_conflicts = (
        current_prepare_signature is not None
        and stored_prepare_signature == current_prepare_signature
        and getattr(prepare_analysis, "conflicts", None) is not None
        and bool(getattr(prepare_analysis, "conflicts", ()))
    )
    can_prepare_uploaded_file = (
        supplier_file_present
        and selected_supplier_name != ""
        and profile_ready
        and supplier_file_read_error is None
        and (file_matches_profile_output_format or profile_matches_uploaded_file)
        and df_supplier_uploaded is not None
    )
    can_run = (
        hicore_file_present
        and supplier_file_present
        and selected_supplier_name != ""
        and has_prepared_supplier_df
    )
    can_manage_profile = selected_supplier_name != ""
    profile_action_label = (
        "Uppdatera leverantörsprofil" if profile_exists else "Skapa leverantörsprofil"
    )
    show_prepare_hint = (
        hicore_file_present
        and supplier_file_present
        and profile_ready
        and can_prepare_uploaded_file
        and not has_prepared_supplier_df
        and not has_pending_conflicts
    )
    return SupplierCompareFlags(
        has_prepared_supplier_df=has_prepared_supplier_df,
        has_pending_conflicts=has_pending_conflicts,
        can_prepare_uploaded_file=can_prepare_uploaded_file,
        can_run=can_run,
        can_manage_profile=can_manage_profile,
        profile_action_label=profile_action_label,
        show_prepare_hint=show_prepare_hint,
    )


def profile_status_message(
    *,
    selected_supplier_name: str,
    profile_exists: bool,
    profile_has_required_sku: bool,
    sku_column_name: str,
) -> UiMessage:
    if selected_supplier_name == "":
        return UiMessage(level="info", text="Välj leverantör för att kontrollera profilstatus.")
    if not profile_exists:
        return UiMessage(
            level="error",
            text=(
                f'Saknar sparad leverantörsprofil för "{selected_supplier_name}". '
                "Skapa en profil i fliken Leverantörsprofiler."
            ),
        )
    if not profile_has_required_sku:
        return UiMessage(
            level="error",
            text=(
                f'Profilen för "{selected_supplier_name}" saknar mappning av "{sku_column_name}". '
                "SKU måste alltid vara matchad."
            ),
        )
    return UiMessage(
        level="success",
        text=f'Färdig leverantörsprofil hittad för "{selected_supplier_name}".',
    )


def supplier_file_status_message(
    *,
    supplier_file_present: bool,
    supplier_file_read_error: Optional[str],
    profile_ready: bool,
    file_matches_profile_output_format: bool,
    profile_matches_uploaded_file: bool,
    missing_profile_columns_for_file: list[str],
) -> Optional[UiMessage]:
    if not supplier_file_present:
        return None
    if supplier_file_read_error is not None:
        return UiMessage(
            level="error",
            text=f"Kunde inte läsa leverantörsfilen: {supplier_file_read_error}",
        )
    if profile_ready and file_matches_profile_output_format:
        return UiMessage(
            level="info",
            text=(
                "Uppladdad leverantörsfil matchar redan HiCore-formatet. "
                "Byggsteget kör ändå dublettkontrollen innan jämförelse."
            ),
        )
    if profile_ready and not profile_matches_uploaded_file:
        return UiMessage(
            level="warning",
            text=(
                "Uppladdad leverantörsfil matchar inte den sparade profilen. Saknade kolumner: "
                + ", ".join(missing_profile_columns_for_file)
            ),
        )
    return None
