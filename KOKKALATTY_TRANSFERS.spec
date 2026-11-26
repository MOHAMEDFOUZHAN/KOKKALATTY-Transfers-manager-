# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

added_files = [
    ('static', 'static'),
    ('branch1', 'branch1'),
    ('branch2', 'branch2'),
    ('login.html', '.'),
]

hidden_imports = [
    'waitress',
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'reportlab',
    'reportlab.platypus',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.lib.styles',
    'reportlab.lib.colors',
    'reportlab.pdfgen',
    'reportlab.graphics',
    'jinja2',
    'fpdf',
    'sqlite3',
    'smtplib',
    'email',
    'email.mime.text',
    'email.mime.multipart',
    'email.mime.application',
    'PIL',
]

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KOKKALATTY_Transfers',
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
    icon='static/images/logo.ico'
)
