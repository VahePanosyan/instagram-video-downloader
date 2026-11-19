# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Instagram & YouTube Video Downloader Pro."""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect yt_dlp lazy extractors, dependencies, and metadata
ydl_datas, ydl_binaries, ydl_hidden = collect_all("yt_dlp")

datas = [
    ("assets", "assets"),
    ("bin/ffmpeg.exe", "bin"),
    ("bin/ffprobe.exe", "bin"),
] + ydl_datas

binaries = [] + ydl_binaries

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "src",
    "src.cli",
    "src.domain",
    "src.domain.models",
    "src.domain.url_parser",
    "src.domain.exceptions",
    "src.adapters",
    "src.adapters.ffmpeg_adapter",
    "src.adapters.yt_dlp_adapter",
    "src.adapters.direct_scraper",
    "src.adapters.json_repository",
    "src.adapters.engine_updater",
    "src.ports",
    "src.ports.downloader",
    "src.ports.extractor",
    "src.ports.notifier",
    "src.ports.repository",
    "src.ports.updater",
    "src.use_cases",
    "src.use_cases.download_media",
    "src.use_cases.extract_metadata",
    "src.use_cases.batch_downloader",
    "src.use_cases.manage_settings",
    "src.use_cases.manage_history",
    "src.use_cases.update_engine",
    "src.gui",
    "src.gui.app",
    "src.gui.workers",
    "src.gui.design_system",
    "src.gui.components",
    "src.gui.components.batch_tab",
    "src.gui.components.header",
    "src.gui.components.history_tab",
    "src.gui.components.log_panel",
    "src.gui.components.queue_table",
    "src.gui.components.settings_tab",
    "src.gui.components.url_input",
    "src.gui.components.media_player_dialog",
] + ydl_hidden

excludes = [
    "torch",
    "torchvision",
    "torchaudio",
    "scipy",
    "scikit-learn",
    "sklearn",
    "matplotlib",
    "transformers",
    "IPython",
    "notebook",
    "tkinter",
    "curses",
    "sympy",
    "faiss",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="InstagramVideoDownloader",
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
    icon=["assets/app_icon.ico"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="InstagramVideoDownloader",
)
