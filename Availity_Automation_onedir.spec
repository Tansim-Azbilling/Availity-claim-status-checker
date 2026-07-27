# -*- mode: python ; coding: utf-8 -*-
# PyInstaller --onedir: dist/Availity Automation_onedir/

a = Analysis(
    ['Availity_Automation.py'],
    pathex=[],
    binaries=[],
    datas=[('azbilling-new-logo.png', '.')],
    hiddenimports=[
        'availity_app',
        'availity_app.automation',
        'availity_app.constants',
        'availity_app.driver',
        'availity_app.logging_gui',
        'availity_app.resources',
        'availity_app.state',
        'availity_app.tk_ui',
        'availity_app.ui_control',
        'availity_app.utils',
        'availity_app.async_save',
        'availity_app.discovery_cache',
        'availity_app.resilience',
        'availity_app.search_grouping',
        'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Availity Automation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='azbilling-new-logo.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Availity Automation_onedir',
)
