import pandas as pd

def _to_str(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()

def repair_shifted_magento_rows(df_magento: pd.DataFrame) -> tuple[pd.DataFrame, int]:

    df = df_magento.copy()
    fixed = 0

    col_name = "name"
    col_sku = "sku"
    col_price = "price"
    col_qty = "qty"
    col_url = "url"

    for c in (col_name, col_sku, col_price, col_qty, col_url):
        if c not in df.columns:
            return df_magento, 0

    for i in range(len(df)):
        name = _to_str(df.at[i, col_name])
        sku = _to_str(df.at[i, col_sku])
        price = _to_str(df.at[i, col_price])
        qty = _to_str(df.at[i, col_qty])
        url = _to_str(df.at[i, col_url])

        if url != "":
            continue
        if not qty.lower().startswith("http"):
            continue
        if ";" not in name:
            continue

        name_left, sku_right = name.split(";", 1)

        sku_right = sku_right.strip().strip('"').strip()

        if sku_right == "":
            continue

        df.at[i, col_url] = qty
        df.at[i, col_qty] = price
        df.at[i, col_price] = sku
        df.at[i, col_sku] = sku_right
        df.at[i, col_name] = name_left.strip().strip('"').strip()

        fixed += 1

    return df, fixed


def repair_magento_shift_rows_v1(df_magento: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    # Backward-compatible alias.
    return repair_shifted_magento_rows(df_magento)
