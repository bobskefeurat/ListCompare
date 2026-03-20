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
    - `services/compare_pipeline.py`: compare parsing + domain orchestration
    - `services/compare_compute.py`: compare/web order UI shaping + exports
    - `services/index_sync.py`: HiCore-driven supplier/brand index sync
    - `services/supplier_pipeline.py`: supplier parsing + domain orchestration
    - `services/supplier_compute.py`: supplier compare UI shaping + exports
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
- `requirements.txt` and `requirements-build.txt` are pinned to the current known-good toolchain used by the audited Windows build/test environment; update them intentionally when refreshing the supported baseline

## Refreshing Dependency Pins

When updating pinned versions in `requirements.txt` or `requirements-build.txt`,
use the same verification path that was used to establish the current baseline:

1. Update the pinned versions intentionally instead of using broad specifiers.
2. Install the refreshed runtime/build requirements into a clean environment.
3. Rerun the Python baseline:
   `python -m unittest discover -s tests -p "test_*.py"`
4. Rerun the tracked-source syntax smoke:
   `python compile_python_sources.py`
5. If build-related dependencies changed, rerun:
   `powershell -ExecutionPolicy Bypass -File .\build_api_docs.ps1`
   `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`
6. Only keep the new pins if the refreshed baseline stays green end-to-end.

## Running

- UI: `py -m streamlit run app.py`

The root file `app.py` is an entrypoint that forwards to `listcompare/interfaces/ui/app.py`.

## App Data

- Persistent app data is stored in `%LOCALAPPDATA%\\ListCompare` on Windows.
- Override the storage directory with `LISTCOMPARE_DATA_DIR` when testing packaging or isolated runs locally.
- First-launch seed files are loaded from the tracked `runtime_seed/` directory so packaged builds do not inherit ignored local repo state.

## Windows Build

- Install build dependencies: `python -m pip install -r requirements.txt -r requirements-build.txt`
- Build the onedir executable: `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`
- Output: `dist\ListCompare\ListCompare.exe`
- Distributable archive: `dist\ListCompare-windows.zip`
- The packaged app must be distributed as the full `dist\ListCompare` folder or the generated zip archive, not as the `.exe` file alone
- By default, the packaged app shuts itself down shortly after the last browser tab/window is closed; override with `LISTCOMPARE_AUTO_SHUTDOWN_SECONDS=0` if you explicitly want it to stay running
- Optional: pass `-InstallBuildDeps` and/or `-PythonExe <full path to python.exe>` to `build_exe.ps1`
- Optional: set `LISTCOMPARE_OPEN_BROWSER=0` before launch if you want the packaged app to stay headless

## Shared Release Launcher

- `ListCompare.cmd` starts `ListCompare Updater.ps1`, which checks for a newer packaged app release before launching the local runtime copy
- The launcher looks for a shared Drive release folder named `ListCompareShared\releases`
- A valid release folder must contain:
  - `latest.json`
  - one or more release archives such as `ListCompare-windows-1.0.5.zip`
- `latest.json` format:

```json
{
  "version": "1.0.5",
  "zip": "ListCompare-windows-1.0.5.zip"
}
```

- The launcher installs updates into `%LOCALAPPDATA%\ListCompareRuntime\current`
- Local installed-version metadata is stored in `%LOCALAPPDATA%\ListCompareRuntime\installed.json`
- If the shared release folder is unavailable, the launcher falls back to the most recently installed local version
- When publishing a new release, copy the new zip archive into `releases` first and update `latest.json` last
- `Publish-SharedRelease.ps1 -Version 1.0.5` copies `dist\ListCompare-windows.zip` into the shared `releases` folder as `ListCompare-windows-1.0.5.zip` and updates `latest.json`
- Optional: pass `-ReleaseRoot <path>` to publish to a specific shared release folder
- Optional: pass `-ZipPath <path>` to publish from a different built archive
- Optional: override release discovery for testing with `LISTCOMPARE_RELEASE_DIR`
- Optional: override the local runtime directory for testing with `LISTCOMPARE_RUNTIME_DIR`

## API Docs

- Install build dependencies: `python -m pip install -r requirements.txt -r requirements-build.txt`
- Generate static API docs: `powershell -ExecutionPolicy Bypass -File .\build_api_docs.ps1`
- Output: `build\api-docs\index.html`
- The generated pages are driven by package/module docstrings plus public symbols re-exported from package `__init__.py` files
- Optional: pass `-InstallBuildDeps` and/or `-PythonExe <full path to python.exe>` to `build_api_docs.ps1`

## Tests

- Run all tests: `python -m unittest discover -s tests -p "test_*.py"`
- Run the tracked-source syntax smoke check: `python compile_python_sources.py`
