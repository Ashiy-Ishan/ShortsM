"""core/transcriber.py — transcribe audio/video using faster-whisper."""
from __future__ import annotations
import json
from pathlib import Path
from core.security import validate_data_file

_whisper_model = None

def get_whisper_model(model_size: str = "tiny"):
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        # CPU with int8 is fast, uses minimal memory, and runs on any modern CPU
        _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _whisper_model

def format_timestamp(seconds: float) -> str:
    """Format seconds to SRT timestamp HH:MM:SS,mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

def write_srt(segments: list[dict], srt_path: Path):
    """Write subtitle segments to standard SRT file."""
    lines = []
    for idx, seg in enumerate(segments, start=1):
        start_ts = format_timestamp(seg["start"])
        end_ts = format_timestamp(seg["end"])
        lines.append(f"{idx}\n{start_ts} --> {end_ts}\n{seg['text']}\n")
    srt_path.write_text("\n".join(lines), encoding="utf-8")

def transcribe_video(filepath: str, model_size: str = "tiny", *, save_files: bool = False) -> dict:
    """Transcribe a video file and return timestamped segments and full text."""
    try:
        p = validate_data_file(filepath)
        if model_size not in {"tiny", "base", "small", "medium", "large-v3"}:
            return {"error": "Unsupported transcription model."}
        model = get_whisper_model(model_size)
        segments_raw, info = model.transcribe(str(p), beam_size=2, vad_filter=True)

        segments = []
        full_text_parts = []
        for s in segments_raw:
            text = s.text.strip()
            if text:
                segments.append({
                    "start": round(s.start, 2),
                    "end": round(s.end, 2),
                    "text": text
                })
                full_text_parts.append(text)

        result = {
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
            "duration": round(info.duration, 2),
            "segments": segments,
            "full_text": " ".join(full_text_parts),
        }
        if save_files:
            srt_path = p.with_suffix(".srt")
            json_path = p.with_suffix(".transcript.json")
            write_srt(segments, srt_path)
            json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            result["srt_path"] = str(srt_path)
            result["json_path"] = str(json_path)
        return result
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}
    except Exception:
        return {"error": "Transcription failed. Check that the media file has a readable audio stream."}
