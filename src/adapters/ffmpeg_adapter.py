import os
import sys
import shutil
import subprocess
from typing import Optional
from pathlib import Path
from ..domain.exceptions import PostProcessingException


def locate_ffmpeg_bin() -> Optional[str]:
    """
    Locates the ffmpeg executable across multiple potential environments:
    1. FFMPEG_PATH or FFMPEG_BINARY environment variable.
    2. Bundled in frozen PyInstaller distribution:
       - <sys.executable_dir>/bin/ffmpeg.exe
       - <sys.executable_dir>/ffmpeg.exe
       - <sys._MEIPASS>/bin/ffmpeg.exe
       - <sys._MEIPASS>/ffmpeg.exe
    3. Bundled in local workspace or project root:
       - <repo_root>/bin/ffmpeg.exe
       - Path.cwd() / "bin" / "ffmpeg.exe"
    4. System PATH: shutil.which("ffmpeg")
    5. Standard Windows installation directories (WinGet Gyan, Chocolatey, Scoop, Program Files).
    """
    # 1. Environment variable
    env_bin = os.environ.get("FFMPEG_PATH") or os.environ.get("FFMPEG_BINARY")
    if env_bin:
        p = Path(env_bin)
        if p.is_file():
            return str(p)
        if p.is_dir():
            candidate = p / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
            if candidate.is_file():
                return str(candidate)

    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    # 2. PyInstaller frozen application
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates = [
            exe_dir / "bin" / exe_name,
            exe_dir / exe_name,
            exe_dir / "_internal" / "bin" / exe_name,
            exe_dir / "_internal" / exe_name,
        ]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.extend([
                Path(meipass) / "bin" / exe_name,
                Path(meipass) / exe_name,
            ])
        for c in candidates:
            if c.is_file():
                return str(c)

    # 3. Bundled in project workspace
    repo_root = Path(__file__).resolve().parent.parent.parent
    workspace_candidates = [
        repo_root / "bin" / exe_name,
        Path.cwd() / "bin" / exe_name,
    ]
    for c in workspace_candidates:
        if c.is_file():
            return str(c)

    # 4. System PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 5. Standard Windows installation locations
    if sys.platform == "win32":
        standard_dirs = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "ffmpeg" / "bin",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "ffmpeg" / "bin",
            Path("C:\\ffmpeg\\bin"),
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "chocolatey" / "bin",
        ]
        for s_dir in standard_dirs:
            if not s_dir.exists():
                continue
            direct_candidate = s_dir / exe_name
            if direct_candidate.is_file():
                return str(direct_candidate)
            if "WinGet" in str(s_dir):
                for match in s_dir.glob("**/ffmpeg.exe"):
                    if match.is_file():
                        return str(match)

    return None


def locate_ffmpeg_dir() -> Optional[str]:
    """Returns the directory containing ffmpeg and ffprobe binaries."""
    bin_path = locate_ffmpeg_bin()
    if bin_path:
        return str(Path(bin_path).parent)
    return None


def locate_ffprobe_bin() -> Optional[str]:
    """Locates the ffprobe binary in the ffmpeg directory, frozen bundle, or system PATH."""
    ffmpeg_dir = locate_ffmpeg_dir()
    exe_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    if ffmpeg_dir:
        candidate = Path(ffmpeg_dir) / exe_name
        if candidate.is_file():
            return str(candidate)
    return shutil.which(exe_name)


def ensure_ffmpeg_in_path() -> Optional[str]:
    """Finds ffmpeg and ensures its directory is at the front of os.environ['PATH']."""
    ffmpeg_dir = locate_ffmpeg_dir()
    if ffmpeg_dir:
        current_path = os.environ.get("PATH", "")
        path_entries = current_path.split(os.pathsep)
        normalized_dir = os.path.normcase(os.path.abspath(ffmpeg_dir))
        for p in path_entries:
            if os.path.normcase(os.path.abspath(p)) == normalized_dir:
                return ffmpeg_dir
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
        return ffmpeg_dir
    return None


class FFmpegAdapter:
    """Provides FFmpeg utility operations like audio extraction and thumbnail generation."""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self._ffmpeg_path = ffmpeg_path or locate_ffmpeg_bin()

    @property
    def is_available(self) -> bool:
        return self._ffmpeg_path is not None

    def get_ffmpeg_path(self) -> Optional[str]:
        return self._ffmpeg_path

    def extract_audio(self, input_path: str, output_path: str, format_type: str = "mp3") -> str:
        """
        Extracts audio stream from video using FFmpeg.
        format_type can be 'mp3' (320kbps), 'm4a' (aac / 192k), 'wav' (pcm_s16le), or 'flac'.
        """
        if not self._ffmpeg_path:
            raise PostProcessingException("FFmpeg not found in system PATH.")
        ffmpeg_bin = self._ffmpeg_path

        in_file = Path(input_path)
        if not in_file.exists():
            raise PostProcessingException(f"Input file not found: {input_path}")

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        cmd = [ffmpeg_bin, "-y", "-i", str(in_file), "-vn"]

        fmt_lower = format_type.lower()
        if fmt_lower == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
        elif fmt_lower == "m4a":
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        elif fmt_lower == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif fmt_lower == "flac":
            cmd.extend(["-c:a", "flac"])
        else:
            cmd.extend(["-c:a", "copy"])

        cmd.append(str(out_file))

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                check=True,
            )
            return str(out_file)
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode("utf-8", errors="ignore")
            raise PostProcessingException(f"FFmpeg audio extraction failed: {err_msg}")
        except Exception as e:
            raise PostProcessingException(f"FFmpeg execution error: {str(e)}")

    def slice_media(
        self,
        input_path: str,
        output_path: str,
        start_time: str,
        end_time: Optional[str] = None,
    ) -> str:
        """Slices a media file between start_time and end_time using fast stream copying."""
        if not self._ffmpeg_path:
            raise PostProcessingException("FFmpeg not found in system PATH.")
        ffmpeg_bin = self._ffmpeg_path

        cmd = [ffmpeg_bin, "-y", "-ss", str(start_time), "-i", str(input_path)]
        if end_time:
            cmd.extend(["-to", str(end_time)])
        cmd.extend(["-c", "copy", str(output_path)])

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                check=True,
            )
            return output_path
        except Exception as e:
            # Fallback without -c copy in case of non-keyframe alignment
            try:
                cmd_fallback = [ffmpeg_bin, "-y", "-ss", str(start_time), "-i", str(input_path)]
                if end_time:
                    cmd_fallback.extend(["-to", str(end_time)])
                cmd_fallback.append(str(output_path))
                subprocess.run(
                    cmd_fallback,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                    check=True,
                )
                return output_path
            except Exception as e2:
                raise PostProcessingException(f"Failed to slice media: {str(e2)}")

    def extract_thumbnail(self, video_path: str, thumbnail_path: str, timestamp_sec: float = 1.0) -> str:
        """Extracts a frame snapshot from the video as a thumbnail image."""
        if not self._ffmpeg_path:
            raise PostProcessingException("FFmpeg not found in system PATH.")
        ffmpeg_bin = self._ffmpeg_path

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", str(timestamp_sec),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(thumbnail_path),
        ]

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                check=True,
            )
            return thumbnail_path
        except Exception as e:
            raise PostProcessingException(f"Failed to generate thumbnail: {str(e)}")
