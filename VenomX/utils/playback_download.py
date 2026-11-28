"""Bounded local fallback for YouTube voice-chat playback."""
import json
import os
import re
import tempfile
import time
from pathlib import Path

from VenomX.utils.exceptions import AssistantErr
from VenomX.utils.media_process import run_media_process


# Reserve time to probe the finished file and join the call. Transfer speed is
# a planning estimate; the subprocess deadline also covers stalls and merging.
_JOIN_RESERVE = 15
_BYTES_PER_SECOND = 4 * 1024 * 1024
_MEDIA_EXTENSIONS = {".mp4", ".mkv", ".webm", ".m4a", ".opus", ".ogg", ".mp3"}


async def cached_playback(video_id, video):
    if not re.fullmatch(r"[\w-]+", video_id, re.ASCII):
        return None
    stems = [f"{video_id}.vc-{'video' if video else 'audio'}", video_id]
    if not video:
        stems.append(f"{video_id}.vc-video")
    for stem in stems:
        for path in Path("downloads").glob(f"{stem}.*"):
            if path.stem != stem or path.suffix not in _MEDIA_EXTENSIONS or not path.is_file():
                continue
            try:
                code, out, _ = await run_media_process([
                    "ffprobe", "-v", "error", "-show_entries",
                    "format=duration:stream=codec_type:stream_disposition=attached_pic",
                    "-of", "json", str(path),
                ], 3)
                if code:
                    continue
                info = json.loads(out)
                kinds = {s.get("codec_type") for s in info.get("streams", [])
                         if not s.get("disposition", {}).get("attached_pic")}
                if (float(info.get("format", {}).get("duration", 0)) > 0
                        and "audio" in kinds and (not video or "video" in kinds)):
                    return str(path)
            except (OSError, ValueError, TimeoutError):
                continue
    return None


def _format_for_budget(info, video, height, budget):
    duration = info.get("duration") or 0
    candidates = []
    for f in info.get("formats") or []:  # yt-dlp sorts from worst to best
        if f.get("has_drm") or not f.get("url") or not f.get("format_id"):
            continue
        size = f.get("filesize") or f.get("filesize_approx") or duration * (f.get("tbr") or 0) * 125
        if 0 < size <= budget:
            candidates.append((f, size))

    audio = [(f, size) for f, size in reversed(candidates) if f.get("acodec") not in (None, "none")]
    if not video:
        for f, _ in audio:
            if f.get("vcodec") == "none":
                return f["format_id"]
        return audio[0][0]["format_id"] if audio else None

    for f, size in reversed(candidates):
        if f.get("vcodec") in (None, "none") or not 0 < (f.get("height") or 0) <= height:
            continue
        if f.get("acodec") not in (None, "none"):
            return f["format_id"]
        for a, audio_size in audio:
            if a.get("vcodec") == "none" and size + audio_size <= budget:
                return f"{f['format_id']}+{a['format_id']}"
    return None


async def download_playback(command, url, video_id, video, height, deadline):
    if not re.fullmatch(r"[\w-]+", video_id, re.ASCII):
        raise AssistantErr("Invalid YouTube video ID.")
    kind = "video" if video else "audio"
    stop_at = deadline - _JOIN_RESERVE

    async def run(args):
        remaining = stop_at - time.monotonic()
        if remaining > 0:
            try:
                return await run_media_process([*command, *args], remaining)
            except TimeoutError:
                pass
        raise AssistantErr(f"The {kind} source did not finish preparing in time. Try a shorter track.")

    # Metadata can contain signed URLs. Keep it and every partial file private
    # to this attempt, including when two chats request the same track.
    with tempfile.TemporaryDirectory(dir="downloads", prefix=".vc-") as directory:
        work = Path(directory)
        code, out, _ = await run(["-J", "-f", "best*", "--", url])
        if code:
            raise AssistantErr(f"Could not read YouTube's {kind} formats for this track.")
        info = json.loads(out)
        budget = max(0, stop_at - time.monotonic()) * _BYTES_PER_SECOND
        selector = _format_for_budget(info, video, height, budget)
        if not selector:
            minutes = (info.get("duration") or 0) / 60
            length = f" ({minutes:.0f} min)" if minutes else ""
            raise AssistantErr(
                f"No {kind} format for this track{length} fits the estimated "
                f"{budget / (1024 * 1024):.0f} MiB playback download budget. Try a shorter track."
            )
        metadata = work / "info.json"
        metadata.write_bytes(out)
        code, out, _ = await run([
            "--load-info-json", str(metadata), "-f", selector, "--no-simulate",
            "--no-progress", "-o", str(work / "media.%(ext)s"), "--print", "after_move:filepath",
        ])
        if code or not out.strip():
            raise AssistantErr(f"YouTube could not download the selected {kind} format.")
        path = Path(os.fsdecode(out.splitlines()[-1]))
        if (path.resolve().parent != work.resolve() or path.stem != "media"
                or path.suffix not in _MEDIA_EXTENSIONS or not path.is_file() or not path.stat().st_size):
            raise AssistantErr(f"The {kind} download did not produce a playable file.")
        target = Path("downloads") / f"{video_id}.vc-{kind}{path.suffix}"
        path.replace(target)
        return str(target)
