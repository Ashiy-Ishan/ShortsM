"""core/renderer.py — render 9:16 vertical shorts with blurred background and subtitles via ffmpeg."""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path
from core.security import safe_output_name, validate_data_file

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SHORTS_DIR = DATA_DIR / "shorts"
SHORTS_DIR.mkdir(parents=True, exist_ok=True)

def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS format H:MM:SS.cs"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{hrs}:{mins:02d}:{secs:02d}.{cs:02d}"

def create_ass_subtitles(segments: list[dict], clip_start: float, clip_end: float, ass_path: Path):
    """Generate styled ASS subtitle file aligned with clip start."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,1.5,2,40,40,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    duration = clip_end - clip_start

    for s in segments:
        seg_start = s.get("start", 0.0)
        seg_end = s.get("end", 0.0)
        text = s.get("text", "").strip().upper()
        text = text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
        text = text.replace("\r", " ").replace("\n", " ")

        if seg_end <= clip_start or seg_start >= clip_end or not text:
            continue

        rel_start = max(0.0, seg_start - clip_start)
        rel_end = min(duration, seg_end - clip_start)

        if rel_end - rel_start < 0.1:
            continue

        start_str = format_ass_time(rel_start)
        end_str = format_ass_time(rel_end)
        # Highlight with yellow accent on punchy words
        styled_text = text
        events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{styled_text}")

    content = header + "\n".join(events) + "\n"
    ass_path.write_text(content, encoding="utf-8")

def render_short(
    video_path: str,
    start_time: float,
    end_time: float,
    segments: list[dict] | None = None,
    output_name: str | None = None,
    with_subtitles: bool = True
) -> dict:
    """Render a vertical 9:16 Short (1080x1920) from input video segment."""
    try:
        inp = validate_data_file(video_path, allow_short=False)
        output_name = safe_output_name(output_name)
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}

    duration = round(end_time - start_time, 2)
    if start_time < 0 or duration <= 0 or duration > 300:
        return {"error": "Clip must be between 0 and 300 seconds with a valid start time."}

    stem = inp.stem
    short_slug = output_name or f"short_{stem}_{int(start_time)}_{int(end_time)}"
    out_file = SHORTS_DIR / f"{short_slug}.mp4"
    thumb_file = SHORTS_DIR / f"{short_slug}.jpg"

    # Temp dir for subtitle file
    with tempfile.TemporaryDirectory() as tmpdir:
        ass_filter_str = ""
        if with_subtitles and segments:
            ass_path = Path(tmpdir) / "subs.ass"
            create_ass_subtitles(segments, start_time, end_time, ass_path)
            # Escape path for ffmpeg filter graph
            clean_ass_path = str(ass_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            ass_filter_str = f",ass='{clean_ass_path}'"

        # FFmpeg filter:
        # 1. Background: scale to fill 1080x1920, crop, heavy boxblur
        # 2. Foreground: scale to width 1080 maintaining aspect ratio
        # 3. Overlay foreground centered onto background
        # 4. Burn ASS subtitles
        filter_complex = (
            f"[0:v]split=2[bg_in][fg_in];"
            f"[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            f"[fg_in]scale=1080:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2{ass_filter_str}[outv]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(inp),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-profile:v", "main",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-shortest",
            str(out_file)
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            return {"error": f"FFmpeg render error: {proc.stderr[-500:]}"}

    # Generate thumbnail frame
    thumb_cmd = [
        "ffmpeg", "-y",
        "-ss", "0.5",
        "-i", str(out_file),
        "-vframes", "1",
        "-q:v", "3",
        str(thumb_file)
    ]
    subprocess.run(thumb_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    filesize = out_file.stat().st_size if out_file.exists() else 0

    return {
        "id": short_slug,
        "filename": out_file.name,
        "filepath": str(out_file),
        "duration": duration,
        "size_mb": round(filesize / (1024 * 1024), 2),
        "video_url": f"/data/shorts/{out_file.name}",
        "thumbnail_url": f"/data/shorts/{thumb_file.name}" if thumb_file.exists() else "",
    }
