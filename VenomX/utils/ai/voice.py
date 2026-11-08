# All rights reserved.
#
# Voice engine: local Whisper STT + Edge TTS.
#
# Both engines are LAZY: importing this module never loads a model. If the
# libraries are missing, the transcribe/speech functions return a friendly
# error string the plugin shows - the bot keeps running without voice skills.
#
# Safety notes:
# - audio never leaves the box except to the local whisper model
# - TTS input is length-capped and secret-redacted before synthesis

import logging

_LOG = logging.getLogger("[VenomAI-voice]")

_stt_model = None
_stt_failed = False


def stt_available() -> bool:
    global _stt_failed
    if _stt_failed:
        return False
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        _stt_failed = True
        return False
    return True


def _load_model():
    global _stt_model
    if _stt_model is not None or not stt_available():
        return _stt_model
    from faster_whisper import WhisperModel

    _LOG.info("loading local whisper model (base, int8, cpu) ...")
    _stt_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _stt_model


async def transcribe(path: str):
    """(text, language) or a string error message starting '!\u26a0'."""
    import asyncio

    def _run():
        model = _load_model()
        if model is None:
            return None
        segs, info = model.transcribe(path)
        text = "".join(s.text for s in segs).strip()
        return text, (info.language or "en")

    try:
        result = await asyncio.to_thread(_run)
    except Exception as e:
        _LOG.error(f"transcribe failed: {type(e).__name__}: {e}")
        return "!engine"
    if result is None:
        return "!engine"
    text, lang = result
    if not text:
        return "!silent"
    return text[:1500], lang


MODEL = "hi-IN-MadhurNeural"


async def speak(text: str, out_path: str):
    """Render text to an mp3 at out_path; returns True/False."""
    from .safety import cap_input

    text = cap_input(text).strip()
    if len(text) > 600:
        text = text[:600]
    try:
        import edge_tts
    except ImportError:
        _LOG.warning("edge-tts not installed, voice reply skipped")
        return False
    try:
        tts = edge_tts.Communicate(text, MODEL)
        await tts.save(out_path)
        return True
    except Exception as e:
        _LOG.error(f"tts failed: {type(e).__name__}: {e}")
        return False
