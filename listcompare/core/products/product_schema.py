from __future__ import annotations

from dataclasses import dataclass

HICORE_COLUMNS = {
    "sku": "Art.m\u00e4rkning",
    "name": "Artikelnamn",
    "stock": "I lager",
    "price": "UtprisInklMoms",
    "total_stock": "Totalt lager",
    "reserved": "Reserverade",
    "supplier": "Leverant\u00f6r",
    "brand": "Varum\u00e4rke",
    "show_on_web": "VisaPåWebb",
}

MAGENTO_COLUMNS = {
    "sku": "sku",
    "name": "name",
    "stock": "qty",
    "price": None,
    "supplier": None,
}


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    stock: str
    supplier: str
    source: str
    price: str = ""
