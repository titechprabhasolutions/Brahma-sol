# -*- mode: python ; coding: utf-8 -*-
import os
import sys

cwd = os.path.abspath(os.getcwd())
if not os.path.exists(os.path.join(cwd, 'main.py')):
    cwd = os.path.abspath(os.path.join(os.getcwd(), '..'))

try:
    import espeakng_loader
    espeak_pkg = os.path.dirname(espeakng_loader.__file__)
except Exception:
    site_packages = os.path.join(cwd, '.venv', 'Lib', 'site-packages')
    espeak_pkg = os.path.join(site_packages, 'espeakng_loader')

datas = [
    (os.path.join(cwd, 'assets'), 'assets'),
    (os.path.join(cwd, 'avatar'), 'avatar'),
    (os.path.join(cwd, 'config'), 'config'),
    (os.path.join(cwd, 'core'), 'core'),
    (os.path.join(cwd, 'brahma_connect'), 'brahma_connect'),
    (os.path.join(cwd, 'actions'), 'actions'),
    (os.path.join(cwd, 'dashboard', 'static'), os.path.join('dashboard', 'static')),
    (os.path.join(cwd, 'smart_home'), 'smart_home'),
    (os.path.join(cwd, 'memory'), 'memory'),
    (os.path.join(cwd, 'plugins'), 'plugins'),
    (os.path.join(cwd, 'features'), 'features'),
    (os.path.join(cwd, 'skills'), 'skills'),
    (os.path.join(cwd, 'workspace_store.py'), '.'),
    (os.path.join(cwd, 'README.md'), '.'),
    (os.path.join(cwd, 'requirements.txt'), '.'),
    (os.path.join(cwd, 'version_brahma_sol.txt'), '.'),
    (os.path.join(cwd, 'installer', 'uninstall.cmd'), '.')
]

if os.path.exists(espeak_pkg):
    datas.append((espeak_pkg, 'espeakng_loader'))

a = Analysis(
    [os.path.join(cwd, 'main.py')],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'mediapipe', 'cv2', 'instagrapi', 'google.genai', 'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui',
        'PyQt6.QtWidgets', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebChannel',
        'pyautogui', 'sounddevice', 'keyboard', 'docx', 'pptx', 'multipart', 'passlib', 'bcrypt',
        'aiohttp', 'websockets', 'uvicorn', 'fastapi', 'plyer', 'pydantic', 'typing_extensions',
        'requests', 'beautifulsoup4', 'pyaudio', 'numpy', 'kokoro_onnx', 'espeakng_loader', 'psutil',
        'win32com.client', 'winreg'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    noarchive=False,
    optimize=0,
)

# Exclude private credentials / cache and heavy on-demand cloud assets
excluded_files = [
    'kokoro-v1.0.onnx',
    'voices-v1.0.bin',
    'assets/models/robot.glb',
    'ig_browser_profile',
    'patch_backups',
    'patch_history.json',
    'api_keys.json',
    'ig_session.json',
    'email_credentials.json',
    'identity.json',
    'device_location_cache.json',
    'learned_rules.json',
    'organizer_history.json',
    'calendar_events.json',
    'long_term.json',
    'nutrition_log.json',
    'brahma_connect.json',
    'devices.json'
]

a.datas = [x for x in a.datas if not any(excl in x[0].replace('\\', '/') for excl in excluded_files)]

pyz = PYZ(a.pure)

ico_path = os.path.join(cwd, 'assets', 'brahma_sol_logo.ico')
ver_path = os.path.join(cwd, 'version_brahma_sol.txt')

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BrahmaSol',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ico_path if os.path.exists(ico_path) else None,
    version=ver_path if os.path.exists(ver_path) else None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='BrahmaSol'
)
