# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['voicerefine.py'],
    pathex=[],
    binaries=[],
    datas=[('branding\\app-icon.ico', 'branding')],
    hiddenimports=['voicerefine_mcp', 'voicerefine_vault', 'voicerefine_local_whisper', 'voicerefine_update', 'voicerefine_ui', 'voicerefine_wizard', 'voicerefine_settings'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'sklearn', 'transformers', 'scipy', 'matplotlib', 'pandas', 'pytest', 'setuptools', 'faster_whisper', 'ctranslate2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VoiceRefine',
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
    icon='branding\\app-icon.ico',
)
