from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from ..products.product_diff import (
    ProductMap,
    build_normalized_map,
    find_field_mismatches_by_sku,
    find_missing_skus,
    normalize_sku,
)
from ..products.product_schema import Product

MismatchMap = dict[str, dict[str, list[Product]]]


@dataclass(frozen=True)
class ComparisonResults:
    only_in_hicore: ProductMap
    only_in_magento: ProductMap
    stock_mismatches: MismatchMap
    internal_only_candidates: Optional[ProductMap]


@dataclass(frozen=True)
class SupplierComparisonResults:
    outgoing: ProductMap
    new_products: ProductMap
    price_updates_out_of_stock: MismatchMap
    price_updates_in_stock: MismatchMap
    article_number_review_matches: tuple["SupplierArticleNumberReviewMatch", ...]


@dataclass(frozen=True)
class SupplierArticleNumberReviewMatch:
    normalized_article_number: str
    article_number: str
    hicore_rows: tuple[Product, ...]
    supplier_rows: tuple[Product, ...]


def _build_normalized_article_number_map(product_map: ProductMap) -> dict[str, list[Product]]:
    out: dict[str, list[Product]] = {}
    for rows in product_map.values():
        for product in rows:
            key = normalize_sku(str(product.article_number).strip())
            if key == "":
                continue
            out.setdefault(key, []).append(product)
    return out


def _display_article_number(*groups: list[Product]) -> str:
    for group in groups:
        for product in group:
            article_number = str(product.article_number).strip()
            if article_number != "":
                return article_number
    return ""


def _build_article_number_review_matches(
    outgoing: ProductMap,
    new_products: ProductMap,
) -> tuple[tuple[SupplierArticleNumberReviewMatch, ...], set[str], set[str]]:
    outgoing_article_map = _build_normalized_article_number_map(outgoing)
    new_article_map = _build_normalized_article_number_map(new_products)
    shared_article_numbers = set(outgoing_article_map.keys()) & set(new_article_map.keys())

    review_matches: list[SupplierArticleNumberReviewMatch] = []
    matched_outgoing_skus: set[str] = set()
    matched_new_product_skus: set[str] = set()

    for normalized_article_number in sorted(
        shared_article_numbers,
        key=lambda value: (normalize_sku(str(value)), str(value)),
    ):
        hicore_rows = list(outgoing_article_map[normalized_article_number])
        supplier_rows = list(new_article_map[normalized_article_number])
        review_matches.append(
            SupplierArticleNumberReviewMatch(
                normalized_article_number=normalized_article_number,
                article_number=_display_article_number(hicore_rows, supplier_rows),
                hicore_rows=tuple(hicore_rows),
                supplier_rows=tuple(supplier_rows),
            )
        )
        matched_outgoing_skus.update(
            normalize_sku(str(product.sku).strip())
            for product in hicore_rows
            if normalize_sku(str(product.sku).strip()) != ""
        )
        matched_new_product_skus.update(
            normalize_sku(str(product.sku).strip())
            for product in supplier_rows
            if normalize_sku(str(product.sku).strip()) != ""
        )

    return tuple(review_matches), matched_outgoing_skus, matched_new_product_skus


def filter_products_by_supplier_with_sku(
    hicore_map: ProductMap,
    supplier_name: str,
) -> ProductMap:
    target = supplier_name.casefold()
    comparable: ProductMap = {}
    for sku, rows in hicore_map.items():
        filtered_rows = [p for p in rows if (p.supplier or "").casefold() == target]
        if not filtered_rows:
            continue
        if sku.strip() == "":
            continue
        comparable[sku] = filtered_rows
    return comparable


def filter_product_map_by_excluded_normalized_skus(
    product_map: ProductMap,
    excluded_normalized_skus: set[str],
) -> ProductMap:
    if not excluded_normalized_skus:
        return product_map

    filtered: ProductMap = {}
    for sku, rows in product_map.items():
        if normalize_sku(sku) in excluded_normalized_skus:
            continue
        filtered[sku] = rows
    return filtered


def build_comparison_results(
    hicore_map: ProductMap,
    magento_map: ProductMap,
    *,
    supplier_map: Optional[ProductMap] = None,
    supplier_internal_name: str = "EM Nordic",
    excluded_normalized_skus: Optional[set[str]] = None,
) -> ComparisonResults:
    excluded_set = {sku for sku in (excluded_normalized_skus or set()) if sku != ""}
    if excluded_set:
        hicore_map = filter_product_map_by_excluded_normalized_skus(hicore_map, excluded_set)
        magento_map = filter_product_map_by_excluded_normalized_skus(magento_map, excluded_set)
        if supplier_map is not None:
            supplier_map = filter_product_map_by_excluded_normalized_skus(supplier_map, excluded_set)

    only_in_hicore, only_in_magento = find_missing_skus(hicore_map, magento_map)
    stock_mismatches = find_field_mismatches_by_sku(hicore_map, magento_map, field="stock")

    internal_only_candidates: Optional[ProductMap] = None
    if supplier_map is not None:
        hicore_comparable = filter_products_by_supplier_with_sku(
            hicore_map,
            supplier_internal_name,
        )
        _, internal_only_candidates = find_missing_skus(supplier_map, hicore_comparable)

    return ComparisonResults(
        only_in_hicore=only_in_hicore,
        only_in_magento=only_in_magento,
        stock_mismatches=stock_mismatches,
        internal_only_candidates=internal_only_candidates,
    )


def _parse_decimal(value: str) -> Optional[Decimal]:
    text = str(value).strip()
    if text == "":
        return None
    normalized = text.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def build_supplier_comparison_results(
    hicore_map: ProductMap,
    supplier_map: ProductMap,
    *,
    supplier_internal_name: str,
    excluded_normalized_skus: Optional[set[str]] = None,
) -> SupplierComparisonResults:
    excluded_set = {sku for sku in (excluded_normalized_skus or set()) if sku != ""}
    if excluded_set:
        hicore_map = filter_product_map_by_excluded_normalized_skus(hicore_map, excluded_set)
        supplier_map = filter_product_map_by_excluded_normalized_skus(supplier_map, excluded_set)

    hicore_comparable = filter_products_by_supplier_with_sku(hicore_map, supplier_internal_name)
    outgoing, new_products = find_missing_skus(hicore_comparable, supplier_map)
    article_number_review_matches, matched_outgoing_skus, matched_new_product_skus = (
        _build_article_number_review_matches(outgoing, new_products)
    )
    if matched_outgoing_skus:
        outgoing = filter_product_map_by_excluded_normalized_skus(outgoing, matched_outgoing_skus)
    if matched_new_product_skus:
        new_products = filter_product_map_by_excluded_normalized_skus(
            new_products,
            matched_new_product_skus,
        )

    hicore_norm = build_normalized_map(hicore_comparable)
    supplier_norm = build_normalized_map(supplier_map)
    shared_keys = set(hicore_norm.keys()) & set(supplier_norm.keys())

    price_updates_out_of_stock: MismatchMap = {}
    price_updates_in_stock: MismatchMap = {}
    for normalized_sku in shared_keys:
        hicore_rows = hicore_norm.get(normalized_sku, [])
        supplier_rows = supplier_norm.get(normalized_sku, [])
        hicore_prices = {str(p.price).strip() for p in hicore_rows if str(p.price).strip() != ""}
        supplier_prices = {str(p.price).strip() for p in supplier_rows if str(p.price).strip() != ""}
        if hicore_prices == supplier_prices:
            continue

        has_positive_stock = False
        for product in hicore_rows:
            parsed_stock = _parse_decimal(product.stock)
            if parsed_stock is not None and parsed_stock > 0:
                has_positive_stock = True
                break

        mismatch_entry = {"hicore": hicore_rows, "supplier": supplier_rows}
        if has_positive_stock:
            price_updates_in_stock[normalized_sku] = mismatch_entry
        else:
            price_updates_out_of_stock[normalized_sku] = mismatch_entry

    return SupplierComparisonResults(
        outgoing=outgoing,
        new_products=new_products,
        price_updates_out_of_stock=price_updates_out_of_stock,
        price_updates_in_stock=price_updates_in_stock,
        article_number_review_matches=article_number_review_matches,
    )


def unique_sorted_skus_from_product_map(product_map: ProductMap) -> list[str]:
    skus: list[str] = []
    for rows in product_map.values():
        skus.extend(p.sku for p in rows if (p.sku or "").strip() != "")
    return sorted(set(skus))


def unique_sorted_skus_from_mismatch_side(
    mismatch_map: MismatchMap,
    side: str,
) -> list[str]:
    skus: list[str] = []
    for sides in mismatch_map.values():
        skus.extend(p.sku for p in sides.get(side, []) if (p.sku or "").strip() != "")
    return sorted(set(skus))
