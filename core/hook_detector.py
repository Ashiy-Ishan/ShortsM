"""core/hook_detector.py — detect viral hooks and short candidates from transcript."""
from __future__ import annotations
import re

HOOK_KEYWORDS = {
    "why", "how", "what", "secret", "secretly", "never", "always", "look", "listen",
    "wait", "crazy", "shocking", "insane", "amazing", "mistake", "truth", "stop",
    "believe", "actually", "hidden", "best", "worst", "reason", "hack", "trick"
}

def detect_hooks(segments: list[dict], min_duration: float = 15.0, max_duration: float = 55.0) -> list[dict]:
    """Find candidate hook clips from transcription segments."""
    if not segments:
        return []

    candidates = []
    n = len(segments)

    for i in range(n):
        start_seg = segments[i]
        try:
            start_time = float(start_seg["start"])
            first_text = str(start_seg["text"]).strip().lower()
        except (KeyError, TypeError, ValueError):
            continue
        if start_time < 0 or not first_text:
            continue

        # Check if first sentence sounds like a hook
        hook_score = 1.0
        words = re.findall(r"\b\w+\b", first_text)
        if words and words[0] in {"why", "how", "what", "did", "can", "if", "this", "here", "stop", "never"}:
            hook_score += 2.5
        if "?" in start_seg["text"]:
            hook_score += 2.0
        if "!" in start_seg["text"]:
            hook_score += 1.5

        matched_keywords = set(words).intersection(HOOK_KEYWORDS)
        hook_score += len(matched_keywords) * 0.8

        # Accumulate segments until reaching optimal short duration
        clip_texts = []
        end_time = start_time
        for j in range(i, n):
            current_seg = segments[j]
            try:
                current_end = float(current_seg["end"])
                current_text = str(current_seg["text"]).strip()
            except (KeyError, TypeError, ValueError):
                continue
            if current_end <= start_time:
                continue
            candidate_duration = current_end - start_time
            if candidate_duration > max_duration and clip_texts:
                break

            clip_texts.append(current_text)
            end_time = current_end

            if candidate_duration >= min_duration:
                # Potential candidate window found
                preview = " ".join(clip_texts)
                duration = round(end_time - start_time, 1)

                # Duration score sweet spot (25s - 45s)
                dur_bonus = 2.0 if 25.0 <= duration <= 45.0 else 1.0

                clean_title = start_seg["text"].strip()
                if len(clean_title) > 60:
                    clean_title = clean_title[:57] + "..."

                candidates.append({
                    "start": round(start_time, 2),
                    "end": round(end_time, 2),
                    "duration": duration,
                    "title": clean_title,
                    "preview": preview,
                    "score": round(hook_score * dur_bonus, 2),
                })
                # Skip forward slightly to avoid near-duplicate windows
                break

    # Sort descending by score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate overlapping candidates (keep highest score)
    filtered = []
    for c in candidates:
        overlap = False
        for chosen in filtered:
            # Overlap check
            if max(c["start"], chosen["start"]) < min(c["end"], chosen["end"]):
                overlap = True
                break
        if not overlap:
            c["id"] = f"hook_{len(filtered) + 1}"
            filtered.append(c)
        if len(filtered) >= 8:  # Cap at top 8 candidates
            break

    # Fallback if no hook met threshold: chunk whole video into 30s segments
    if not filtered and segments:
        total_duration = segments[-1]["end"]
        t = 0.0
        idx = 1
        while t < total_duration:
            clip_end = min(t + 35.0, total_duration)
            if clip_end - t < 10.0:
                break
            matched_text = " ".join(s["text"] for s in segments if s["start"] >= t and s["end"] <= clip_end)
            filtered.append({
                "id": f"clip_{idx}",
                "start": round(t, 2),
                "end": round(clip_end, 2),
                "duration": round(clip_end - t, 1),
                "title": f"Clip {idx} ({round(t, 0):.0f}s - {round(clip_end, 0):.0f}s)",
                "preview": matched_text or f"Segment from {t:.0f}s to {clip_end:.0f}s",
                "score": 1.0,
            })
            t += 35.0
            idx += 1

    return filtered
