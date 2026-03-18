# ListCompare

The project is organized into a clear package structure:

- `listcompare/core`: domain logic grouped by subdomain
  - `products/`: product schema, normalization, mapping, diff and related helpers
  - `suppliers/`: supplier parsing, selection and product map helpers
    - `profile/`: profile schema/normalization, validation, transformation and payload helpers
    - `prepare/`: prepare signature, duplicate/conflict analysis and finalize logic
  - `comparison/`: comparison use cases and result composition
  - `orders/`: web order compare logic
- `listcompare/interfaces`: Streamlit UI
  - `ui/`: internal UI modules
    - `app.py`: app bootstrap/router
    - `common.py`: shared constants and UI result dataclasses
    - `compute_shared.py`: shared compute helpers
    - `pages/compare.py`: compare page rendering
    - `pages/supplier.py`: supplier page rendering
    - `pages/settings.py`: settings page rendering
    - `services/compare_compute.py`: compare + web order orchestration
    - `services/supplier_compute.py`: supplier compare orchestration
    - `services/index_sync.py`: HiCore-driven supplier/brand index sync
    - `session/file_inputs.py`: file upload state + input rendering helpers
    - `session/bootstrap.py`: session default initialization
    - `session/navigation.py`: rerun/navigation helpers
    - `session/supplier_selection.py`: selection normalization/sync
    - `session/profile_state.py`: supplier profile persistence orchestration
    - `io/*`: focused upload/index/filter/table/export adapters
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

## App Data

- Persistent app data is stored in `%LOCALAPPDATA%\\ListCompare` on Windows.
- Override the storage directory with `LISTCOMPARE_DATA_DIR` when testing packaging or isolated runs locally.

## Windows Build

- Install build dependencies: `python -m pip install -r requirements.txt -r requirements-build.txt`
- Build the onedir executable: `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`
- Output: `dist\ListCompare\ListCompare.exe`
- Distributable archive: `dist\ListCompare-windows.zip`
- The packaged app must be distributed as the full `dist\ListCompare` folder or the generated zip archive, not as the `.exe` file alone
- By default, the packaged app shuts itself down shortly after the last browser tab/window is closed; override with `LISTCOMPARE_AUTO_SHUTDOWN_SECONDS=0` if you explicitly want it to stay running
- Optional: pass `-InstallBuildDeps` and/or `-PythonExe <full path to python.exe>` to `build_exe.ps1`
- Optional: set `LISTCOMPARE_OPEN_BROWSER=0` before launch if you want the packaged app to stay headless

## Tests

- Run all tests: `python -m unittest discover -s tests -p "test_*.py"`
