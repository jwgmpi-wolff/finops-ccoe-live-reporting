from PyInstaller.utils.hooks import collect_submodules


hidden_imports = (
    collect_submodules("uvicorn")
    + collect_submodules("pydantic")
    + collect_submodules("pydantic_settings")
    + collect_submodules("fastapi")
    + collect_submodules("starlette")
    + collect_submodules("fpdf")
    + collect_submodules("pptx")
)

a = Analysis(
    ["desktop_launcher.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("app/static", "app/static"),
        ("app/templates", "app/templates"),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name="FinOpsCCoE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    exclude_binaries=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FinOpsCCoE",
)