from __future__ import annotations

SUPPLIER_HICORE_ARTICLE_NUMBER_COLUMN = "Lev.artnr"
SUPPLIER_HICORE_RENAME_COLUMNS = (
    "Art.märkning",
    "Artikelnamn",
    "Varumärke",
    "Inköpspris",
    "UtprisInklMoms",
    SUPPLIER_HICORE_ARTICLE_NUMBER_COLUMN,
)
SUPPLIER_HICORE_SUPPLIER_COLUMN = "Leverantör"
SUPPLIER_HICORE_SKU_COLUMN = "Art.märkning"
SUPPLIER_HICORE_NAME_COLUMN = "Artikelnamn"

SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS = "strip_leading_zeros_from_sku"
# Legacy profile option. Existing saved profiles may still contain it, but
# current transforms always drop rows that have neither SKU nor article number.
SUPPLIER_TRANSFORM_OPTION_IGNORE_ROWS_MISSING_SKU = "ignore_rows_missing_sku"
SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN = "brand_source_column"
SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES = "excluded_brand_values"

SUPPLIER_TRANSFORM_DEFAULT_OPTIONS: dict[str, bool] = {
    SUPPLIER_TRANSFORM_OPTION_STRIP_LEADING_ZEROS: False,
}
SUPPLIER_TRANSFORM_DEFAULT_FILTERS: dict[str, object] = {
    SUPPLIER_TRANSFORM_FILTER_BRAND_SOURCE_COLUMN: "",
    SUPPLIER_TRANSFORM_FILTER_EXCLUDED_BRAND_VALUES: [],
}
SUPPLIER_TRANSFORM_COMPOSITE_SUPPORTED_TARGETS = (SUPPLIER_HICORE_NAME_COLUMN,)
