# ListCompare

The project is organized into a clear package structure:

- `listcompare/core`: domain logic (products, diff, use cases, supplier logic)
  - `product_schema.py`: product dataclass and source column schemas
  - `product_normalization.py`: stock/price/string normalization
  - `product_mapping.py`: product map building and source preparation
- `listcompare/interfaces`: Streamlit UI
  - `ui/`: internal UI modules
    - `app.py`: app router (menu/page flow)
    - `common.py`: shared constants and UI result dataclasses
    - `state.py`: session state helpers
    - `data_io.py`: CSV/Excel/index IO and table conversion helpers
    - `compute_compare.py`: compare + web order compute flows
    - `compute_supplier.py`: supplier compare compute flow
    - `compute_shared.py`: shared compute helpers
    - `persistence/index_store.py`: supplier/brand index persistence
    - `persistence/settings_store.py`: UI settings persistence
    - `persistence/profile_store.py`: supplier profile persistence
    - `shared/presentation.py`: shared UI presentation helpers
    - `features/supplier_compare/page.py`: supplier compare page entrypoint
    - `features/supplier_compare/prepare.py`: supplier prepare helpers/workflow pieces
    - `features/supplier_compare/results.py`: supplier compare result rendering
    - `features/supplier_profiles/page.py`: supplier profiles page entrypoint
    - `features/supplier_profiles/editor.py`: supplier profile editor rendering
    - `features/supplier_profiles/overview.py`: supplier profile overview rendering

## Installation

- Install dependencies: `pip install -r requirements.txt`

## Running

- UI: `py -m streamlit run app.py`

The root file `app.py` is an entrypoint that forwards to `listcompare/interfaces/ui/app.py`.

## Tests

- Run all tests: `python -m unittest discover -s tests -p "test_*.py"`
