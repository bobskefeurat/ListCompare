# ListCompare

The project is organized into a clear package structure:

- `listcompare/core`: domain logic (products, diff, use cases, supplier logic)
- `listcompare/interfaces`: Streamlit UI
  - `ui_app.py`: app router (menu/page flow)
  - `ui_services.py`: compatibility facade that re-exports UI helper APIs
  - `ui_supplier_compare.py`: supplier compare tab rendering
  - `ui_supplier_profiles.py`: supplier profile editor/overview rendering
  - `ui/`: internal UI service modules
    - `common.py`: shared constants and UI result dataclasses
    - `state.py`: session state/persistence helpers
    - `data_io.py`: CSV/Excel/index IO and table conversion helpers
    - `compute.py`: compare/supplier compute orchestration

## Installation

- Install dependencies: `pip install -r requirements.txt`

## Running

- UI: `py -m streamlit run app.py`

The root file `app.py` is an entrypoint that forwards to `listcompare/interfaces/ui_app.py`.

## Tests

- Run all tests: `python -m unittest discover -s tests -p "test_*.py"`
