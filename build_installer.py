"""Complete build and packaging script for Instagram & YouTube Video Downloader Pro.

Automates:
1. Binary dependency verification (FFmpeg / FFprobe)
2. Icon generation (ICO and PNG)
3. PyInstaller compilation with windowed GUI subsystem (no CMD window)
4. Headless execution verification of the compiled binary (--test-mode)
5. Inno Setup installer compilation (InstagramDownloader_Setup.exe)
6. Portable ZIP distribution packaging
7. Integrity checksum generation (SHA-256)
"""

import os
import sys
import shutil
import hashlib
import zipfile
import subprocess
from typing import Optional
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
BIN_DIR = ROOT_DIR / "bin"
ASSETS_DIR = ROOT_DIR / "assets"
SPEC_FILE = ROOT_DIR / "InstagramDownloader.spec"
ISS_FILE = ROOT_DIR / "installer.iss"


def log(msg: str):
    print(f"[BUILD] {msg}")


def check_and_prepare_binaries():
    """Ensures FFmpeg and FFprobe binaries are present in bin/ directory."""
    log("Checking external binary dependencies (FFmpeg & FFprobe)...")
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    ffmpeg_target = BIN_DIR / "ffmpeg.exe"
    ffprobe_target = BIN_DIR / "ffprobe.exe"

    if ffmpeg_target.is_file() and ffprobe_target.is_file():
        log(f"  Binaries already in {BIN_DIR}")
        return

    from src.adapters.ffmpeg_adapter import locate_ffmpeg_bin
    found_ffmpeg = locate_ffmpeg_bin()
    if found_ffmpeg and Path(found_ffmpeg).is_file():
        src_ffmpeg = Path(found_ffmpeg)
        src_ffprobe = src_ffmpeg.parent / "ffprobe.exe"
        if not ffmpeg_target.is_file():
            log(f"  Copying ffmpeg: {src_ffmpeg} -> {ffmpeg_target}")
            shutil.copy2(src_ffmpeg, ffmpeg_target)
        if src_ffprobe.is_file() and not ffprobe_target.is_file():
            log(f"  Copying ffprobe: {src_ffprobe} -> {ffprobe_target}")
            shutil.copy2(src_ffprobe, ffprobe_target)
    else:
        raise RuntimeError("FFmpeg binary not found on system. Please install ffmpeg or place ffmpeg.exe in bin/.")


def generate_icons():
    """Generates application icons if not present."""
    ico_path = ASSETS_DIR / "app_icon.ico"
    png_path = ASSETS_DIR / "app_icon.png"
    if not ico_path.is_file() or not png_path.is_file():
        log("Generating application icons...")
        from scripts.generate_icon import generate_all_icons
        generate_all_icons()
    else:
        log("Icons verified in assets/.")


def clean_previous_builds():
    """Cleans temporary build output before compiling."""
    log("Cleaning previous build directories and release artifacts...")
    app_dist = DIST_DIR / "InstagramVideoDownloader"
    if app_dist.exists():
        shutil.rmtree(app_dist, ignore_errors=True)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    # Clean previous release artifacts to avoid shipping stale builds
    for artifact in [
        DIST_DIR / "InstagramDownloader_Setup.exe",
        DIST_DIR / "InstagramVideoDownloader-v1.0.0-Portable.zip",
        DIST_DIR / "SHA256SUMS.txt",
        ROOT_DIR / "installed.dat",
    ]:
        if artifact.exists():
            try:
                artifact.unlink()
            except Exception:
                pass


def prepare_staging_distribution():
    """Prepares distribution assets and configuration markers in the compiled bundle."""
    log("Preparing distribution staging assets and markers...")
    app_dist = DIST_DIR / "InstagramVideoDownloader"

    # Copy assets directly next to executable for standalone icon resolution
    dist_assets = app_dist / "assets"
    if not dist_assets.exists():
        shutil.copytree(ASSETS_DIR, dist_assets)
        log("  Copied assets/ to distribution root")

    # Clean any developer or test config directory leaked by PyInstaller
    internal_config = app_dist / "_internal" / "config"
    if internal_config.exists():
        shutil.rmtree(internal_config, ignore_errors=True)
        log("  Cleaned internal config cache from distribution")

    # Create installed marker for Inno Setup installer packaging
    installed_marker = ROOT_DIR / "installed.dat"
    with open(installed_marker, "w", encoding="utf-8") as f:
        f.write("installed_mode=true\nversion=1.0.0\n")
    log("  Generated installed.dat marker for Inno Setup")


def run_pyinstaller():
    """Executes PyInstaller to bundle the application into dist/InstagramVideoDownloader."""
    log("Running PyInstaller...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_FILE),
    ]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller failed with return code {res.returncode}")

    exe_path = DIST_DIR / "InstagramVideoDownloader" / "InstagramVideoDownloader.exe"
    if not exe_path.is_file():
        raise RuntimeError(f"PyInstaller finished but expected executable not found: {exe_path}")
    log(f"PyInstaller bundle created successfully: {exe_path}")


def verify_executable():
    """Runs the compiled binary in headless test mode to ensure no crash on startup."""
    log("Verifying compiled executable in headless mode (--test-mode)...")
    exe_path = DIST_DIR / "InstagramVideoDownloader" / "InstagramVideoDownloader.exe"

    # In windowed mode, run with CREATE_NO_WINDOW
    no_window = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    res = subprocess.run(
        [str(exe_path), "--test-mode"],
        cwd=str(exe_path.parent),
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=no_window,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"Executable self-test failed (exit code {res.returncode}):\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        )
    log("  Executable verified: launches, boots Qt and hexagonal services, and exits cleanly with code 0!")


def find_iscc_compiler() -> Optional[str]:
    """Finds Inno Setup Compiler (ISCC.exe)."""
    candidates = [
        shutil.which("iscc"),
        shutil.which("iscc.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Inno Setup 6" / "ISCC.exe",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return str(c)
    return None


def run_inno_setup():
    """Compiles the Inno Setup installer."""
    iscc_path = find_iscc_compiler()
    if not iscc_path:
        log("WARNING: Inno Setup compiler (ISCC.exe) not found. Skipping installer .exe creation.")
        return None

    log(f"Compiling Inno Setup installer using {iscc_path}...")
    cmd = [iscc_path, str(ISS_FILE)]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        raise RuntimeError(f"Inno Setup compilation failed with code {res.returncode}")

    installer_exe = DIST_DIR / "InstagramDownloader_Setup.exe"
    if not installer_exe.is_file():
        raise RuntimeError(f"Inno Setup completed but installer file not found: {installer_exe}")
    log(f"Installer built successfully: {installer_exe} ({installer_exe.stat().st_size / (1024 * 1024):.1f} MB)")
    return installer_exe


def package_portable_zip():
    """Packages dist/InstagramVideoDownloader into a standalone portable ZIP."""
    log("Creating standalone portable ZIP distribution...")
    src_folder = DIST_DIR / "InstagramVideoDownloader"
    zip_path = DIST_DIR / "InstagramVideoDownloader-v1.0.0-Portable.zip"

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_folder):
            for file in files:
                abs_path = Path(root) / file
                rel_path = abs_path.relative_to(src_folder)
                archive_name = Path("InstagramVideoDownloader") / rel_path
                zf.write(abs_path, str(archive_name))

        # Add portable marker file so app runs in true portable mode
        zf.writestr(
            "InstagramVideoDownloader/portable.dat",
            "portable_mode=true\nversion=1.0.0\n",
        )

        # Add empty config directory entry for local persistence
        config_zip_info = zipfile.ZipInfo("InstagramVideoDownloader/config/")
        zf.writestr(config_zip_info, "")

        # Add portable usage instructions
        readme_content = (
            "Instagram & YouTube Video Downloader Pro - Portable Edition\n"
            "===========================================================\n"
            "This portable edition is fully self-contained:\n"
            "- No installation, administrative privileges, Python, or FFmpeg required.\n"
            "- Double-click 'InstagramVideoDownloader.exe' to run.\n"
            "- Configuration and download history are saved locally in the 'config' folder.\n"
            "- Bundled high-performance FFmpeg and yt-dlp run silently with zero terminal windows.\n"
        )
        zf.writestr("InstagramVideoDownloader/README_PORTABLE.txt", readme_content)

    log(f"Portable ZIP created: {zip_path} ({zip_path.stat().st_size / (1024 * 1024):.1f} MB)")
    return zip_path


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def generate_checksums():
    """Generates SHA-256 checksums file for distribution artifacts."""
    log("Computing SHA-256 distribution checksums...")
    checksum_lines = []
    for item in [
        DIST_DIR / "InstagramDownloader_Setup.exe",
        DIST_DIR / "InstagramVideoDownloader-v1.0.0-Portable.zip",
    ]:
        if item.is_file():
            digest = compute_sha256(item)
            size_mb = item.stat().st_size / (1024 * 1024)
            line = f"{digest}  {item.name}  ({size_mb:.1f} MB)"
            checksum_lines.append(line)
            log(f"  {line}")

    checksum_file = DIST_DIR / "SHA256SUMS.txt"
    with open(checksum_file, "w", encoding="utf-8") as f:
        f.write("\n".join(checksum_lines) + "\n")
    log(f"Checksums saved to {checksum_file}")


def main():
    print("=" * 70)
    print(" Instagram & YouTube Video Downloader Pro - Release Build System")
    print("=" * 70)
    try:
        check_and_prepare_binaries()
        generate_icons()
        clean_previous_builds()
        run_pyinstaller()
        prepare_staging_distribution()
        verify_executable()
        installer_exe = run_inno_setup()
        portable_zip = package_portable_zip()
        generate_checksums()
        print("\n" + "=" * 70)
        print(" BUILD COMPLETE AND VERIFIED SUCCESSFULLY!")
        if installer_exe:
            print(f" -> Installer Executable: {installer_exe}")
        if portable_zip:
            print(f" -> Portable ZIP Package: {portable_zip}")
        print("=" * 70)
    except Exception as e:
        print(f"\n[BUILD ERROR] {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        installed_marker = ROOT_DIR / "installed.dat"
        if installed_marker.exists():
            try:
                installed_marker.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
