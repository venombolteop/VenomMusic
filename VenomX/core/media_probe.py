"""Validate inputs using the command builder from the pinned PyTgCalls release."""
from VenomX.utils.media_process import run_media_process
import json

from ntgcalls import FFmpegError
from pytgcalls import ffmpeg
from pytgcalls.exceptions import (
    ImageSourceFound, InvalidVideoProportion, LiveStreamFound,
    NoAudioSourceFound, NoVideoSourceFound,
)
from pytgcalls.types.raw import VideoParameters


async def check_stream(ffmpeg_parameters, path, stream_parameters, before_commands=None, headers=None):
    command = ffmpeg.build_command(
        "ffprobe", ffmpeg_parameters, path, stream_parameters, before_commands, headers, False,
    )
    status, output, _ = await run_media_process(await ffmpeg.cleanup_commands(command), 20)
    if status:
        raise FFmpegError(f"ffprobe exited with status {status}")
    result = json.loads(output)
    tracks = result.get("streams", [])
    if isinstance(stream_parameters, VideoParameters):
        video = [track for track in tracks if track.get("codec_type") == "video"]
        if not video:
            raise NoVideoSourceFound(path)
        width = video[-1].get("width", 0)
        height = video[-1].get("height", 0)
        if not width or not height:
            raise InvalidVideoProportion("Video dimensions missing")
        scale = min(1, stream_parameters.width / width)
        if stream_parameters.adjust_by_height:
            scale = min(scale, stream_parameters.height / height)
        stream_parameters.width = int(width * scale) // 2 * 2
        stream_parameters.height = int(height * scale) // 2 * 2
        if all(track.get("codec_name") in {"png", "jpeg", "jpg", "mjpeg"} for track in video):
            stream_parameters.frame_rate = 10
            raise ImageSourceFound(path)
    elif not any(track.get("codec_type") == "audio" for track in tracks):
        raise NoAudioSourceFound(path)
    if "duration" not in result.get("format", {}):
        raise LiveStreamFound(path)
