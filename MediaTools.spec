# MediaTools.spec – Phiên bản hoàn thiện cho PyInstaller

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('ffmpeg/ffmpeg.exe', 'ffmpeg'),
        ('ffmpeg/ffprobe.exe', 'ffmpeg'),
        ('icon.ico', '.')
    ],
    hiddenimports=[
        # Thư viện cần cho tính năng cập nhật
        'pefile',
        'packaging',
        'packaging.version',
        'packaging.specifiers',
        'packaging.requirements',
        
        # Thư viện mạng và logic nền của Recording
        'requests',
        'psutil',
        'tenacity',

        # Thư viện cho phương án fallback lấy RoomID
        'TikTokLive',
        'nest_asyncio'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MediaTools',
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='icon.ico',
    # Sử dụng file version.txt để nhúng thông tin vào metadata của exe
    version='version.txt'
)