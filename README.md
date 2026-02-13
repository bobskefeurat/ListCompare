# ListCompare

Projektet ar uppdelat i ett tydligt paket:

- `listcompare/core`: domanlogik (produkter, diff, use cases, leverantorslogik)
- `listcompare/interfaces`: Streamlit UI

## Korning

- UI: `python -m streamlit run app.py`

Root-filen `app.py` ar en entrypoint som vidarekopplar till `listcompare/interfaces/ui_app.py`.

## Tester

- Kor alla tester: `python -m unittest discover -s tests -p "test_*.py"`
