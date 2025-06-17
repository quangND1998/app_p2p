# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

def resource_path(relative_path):
    """Lấy đường dẫn tuyệt đối đến resource, dùng được cả khi chạy .py và .exe"""
    if hasattr(sys, '_MEIPASS'):
        # Khi chạy bằng PyInstaller
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Đường dẫn resources
json_path = resource_path('bank_list.json')
env_path = resource_path('.env')
chromedriver_path = resource_path('chromedriver_win32/chromedriver.exe')

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (json_path, '.'),
        (chromedriver_path, 'chromedriver_win32'),
        (env_path, '.'),
    ],
    hiddenimports=[
        'PyQt5',
        'selenium',
        'pandas',
        'dotenv',
        'module.selenium_get_info',
        'module.binance_p2p',
        'module.generate_qrcode',
        'module.transaction_storage',
        'transaction_viewer'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'scipy', 'PIL',  # Loại bỏ các module không cần thiết
        'numpy.random._examples',  # Loại bỏ các module có thể gây nghi ngờ
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Tối ưu hóa binary
a.binaries = [x for x in a.binaries if not x[0].startswith('api-ms-win')]  # Loại bỏ các DLL không cần thiết

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Binance P2P Trading',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Không strip trên Windows
    upx=False,  # Tắt UPX để tránh false positive
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Tạm thời bật console để xem lỗi
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='file_version_info.txt',
    # icon='app_icon.ico',  # Temporarily comment out icon
    uac_admin=False,
    icon=None,  # Tạm thời bỏ icon
    # Thêm các tùy chọn bảo mật
    uac_uiaccess=False,
    win_private_assemblies=False,
    win_no_prefer_redirects=False,
    win_restrict_imports=True,
    manifest='app.manifest',  # Thêm manifest file
) 