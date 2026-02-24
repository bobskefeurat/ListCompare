# ListCompare

The project is organized into a clear package structure:

- `listcompare/core`: domain logic (products, diff, use cases, supplier logic)
- `listcompare/interfaces`: Streamlit UI

## Running

- UI: `python -m streamlit run app.py`

The root file `app.py` is an entrypoint that forwards to `listcompare/interfaces/ui_app.py`.

## Tests

- Run all tests: `python -m unittest discover -s tests -p "test_*.py"`
