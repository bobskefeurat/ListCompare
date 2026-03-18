# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


PROJECT_ROOT = Path(SPECPATH).resolve()
APP_DATA_FILES = [
    ("app.py", "."),
    ("brand_index.txt", "."),
    ("supplier_index.txt", "."),
    ("ui_settings.json", "."),
    ("supplier_transform_profiles.json", "."),
]


def _collect_package(package_name):
    try:
        return collect_all(package_name)
    except Exception:
        return [], [], []


def _unique_items(items):
    unique = []
    seen = set()
    for item in items:
        item_key = tuple(item) if isinstance(item, (list, tuple)) else item
        if item_key in seen:
            continue
        seen.add(item_key)
        unique.append(item)
    return unique


datas = [(str(PROJECT_ROOT / source), target) for source, target in APP_DATA_FILES]
binaries = []
hiddenimports = []

for package_name in (
    "streamlit",
    "pandas",
    "openpyxl",
    "altair",
    "pydeck",
    "tornado",
):
    package_datas, package_binaries, package_hiddenimports = _collect_package(package_name)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

datas = _unique_items(datas)
binaries = _unique_items(binaries)
hiddenimports = _unique_items(hiddenimports)


a = Analysis(
    ["listcompare_launcher.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ListCompare",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ListCompare",
)
