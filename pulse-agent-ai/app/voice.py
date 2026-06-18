from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from .config import (
    ELEVENLABS_API_BASE_URL,
    ELEVENLABS_API_KEY,
    ELEVENLABS_STT_MODEL,
    ELEVENLABS_TTS_MODEL,
    ELEVENLABS_VOICE_ID,
)


LANGUAGE_TO_ISO = {
    "en-US": "en",
    "es-US": "es",
    "hi-IN": "hi",
    "zh-CN": "zh",
    "ar": "ar",
    "fr-FR": "fr",
}

@dataclass
class SpeechAudio:
    content: bytes
    media_type: str


class ElevenLabsVoiceService:
    def configured(self) -> bool:
        return bool(ELEVENLABS_API_KEY)

    def status(self) -> dict:
        return {
            "configured": self.configured(),
            "provider": "elevenlabs",
            "tts_model": ELEVENLABS_TTS_MODEL,
            "stt_model": ELEVENLABS_STT_MODEL,
            "voice_id": ELEVENLABS_VOICE_ID,
        }

    def speak(self, text: str, language: str = "en-US", voice_id: str | None = None) -> SpeechAudio:
        if not self.configured():
            raise RuntimeError("ElevenLabs is not configured.")

        clean_text = self._clean_for_speech(text)
        payload = {
            "text": clean_text[:4000],
            "model_id": ELEVENLABS_TTS_MODEL,
            "voice_settings": {
                "stability": 0.52,
                "similarity_boost": 0.8,
                "style": 0.12,
                "use_speaker_boost": True,
            },
        }
        language_code = LANGUAGE_TO_ISO.get(language)
        if language_code:
            payload["language_code"] = language_code

        selected_voice = voice_id or ELEVENLABS_VOICE_ID
        response = requests.post(
            f"{ELEVENLABS_API_BASE_URL}/text-to-speech/{selected_voice}",
            params={"output_format": "mp3_44100_128"},
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": ELEVENLABS_API_KEY,
            },
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        return SpeechAudio(
            content=response.content,
            media_type=response.headers.get("content-type", "audio/mpeg").split(";")[0],
        )

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: str = "en-US",
    ) -> dict:
        if not self.configured():
            raise RuntimeError("ElevenLabs is not configured.")

        data = {
            "model_id": ELEVENLABS_STT_MODEL,
            "tag_audio_events": "false",
            "timestamps_granularity": "none",
            "no_verbatim": "true",
        }
        language_code = LANGUAGE_TO_ISO.get(language)
        if language_code:
            data["language_code"] = language_code

        response = requests.post(
            f"{ELEVENLABS_API_BASE_URL}/speech-to-text",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            data=data,
            files={"file": (filename or "voice.webm", audio_bytes, content_type or "audio/webm")},
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        return {
            "text": result.get("text", "").strip(),
            "language_code": result.get("language_code"),
            "language_probability": result.get("language_probability"),
        }

    def _clean_for_speech(self, text: str) -> str:
        clean = text.strip()
        clean = re.sub(r"\*\*(.*?)\*\*", r"\1", clean)
        clean = re.sub(r"`([^`]*)`", r"\1", clean)
        clean = re.sub(r"^\s*[-*]\s+", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        return clean
