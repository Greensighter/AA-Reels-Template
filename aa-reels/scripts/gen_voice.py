#!/usr/bin/env python3
"""Voiceover for the PrayScripture reel, made locally with Kokoro (no API key).

Reads <project>/pray.json, speaks each phrase, and writes to <project>/public/audio/pray/:
  voice.wav     all phrases on one timeline, with lead-in, gaps and tail
  timing.json   per phrase and per word start/end times (seconds)

Word times are spread across each phrase's audio by phoneme count, so a long
word gets more time than a short one. Commas and full stops add a small pause.

Setup (once):
  pip install kokoro-onnx soundfile numpy
  Download kokoro-v1.0.onnx and voices-v1.0.bin from
  https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
  into ~/models/kokoro (or set KOKORO_DIR).

Usage:
  python3 gen_voice.py --project <remotion project> [--voice af_heart] [--speed 0.76]

Voices that suit prayer: af_heart, af_bella, bf_emma (female); am_michael,
bm_george, am_onyx (male).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

SR = 24000


def find_models() -> tuple[str, str]:
    d = Path(os.environ.get("KOKORO_DIR", Path.home() / "models" / "kokoro"))
    onnx, voices = d / "kokoro-v1.0.onnx", d / "voices-v1.0.bin"
    if not onnx.exists() or not voices.exists():
        raise SystemExit(f"Kokoro model files not found in {d} (see the setup note at the top of this file).")
    return str(onnx), str(voices)


def trim_silence(audio: np.ndarray, thresh: float = 0.01, pad: int = int(0.04 * SR)) -> np.ndarray:
    idx = np.where(np.abs(audio) > thresh)[0]
    if len(idx) == 0:
        return audio
    return audio[max(0, idx[0] - pad) : min(len(audio), idx[-1] + pad)]


def parse_phrase(phrase: str) -> list[tuple[str, bool]]:
    """Words of a phrase with accent flags; *stars* mark accent words.

    "Lord, *revive* us" -> [("Lord,", False), ("revive", True), ("us", False)].
    Must match parsePhrase() in project/src/pray/timing.ts.
    """
    out, inside = [], False
    for token in phrase.split():
        starts = token.startswith("*")
        ends = re.sub(r"[,.;:!?\"')\]]+$", "", token).endswith("*") and not (starts and len(token) == 1)
        clean = token.replace("*", "")
        if clean:
            out.append((clean, inside or starts))
        if starts:
            inside = True
        if ends:
            inside = False
    return out


def word_weights(k: Kokoro, words: list[str], lang: str) -> list[float]:
    weights = []
    for w in words:
        clean = re.sub(r"[^\w']", "", w)
        try:
            ph = k.tokenizer.phonemize(clean, lang) if clean else ""
            n = max(1, len(ph.replace(" ", "")))
        except Exception:
            n = max(1, len(clean))
        # punctuation after a word means a short pause before the next one
        if re.search(r"[,;:]$", w):
            n += 3
        elif re.search(r"[.!?]$", w):
            n += 5
        weights.append(float(n))
    return weights


def normalize_loudness(path: Path, target_lufs: float = -16.0) -> None:
    """Bring the voice to -16 LUFS (true peak -1.5 dB) with ffmpeg's loudnorm.

    Speech at -16 LUFS plus the quiet music bed lands the finished reel near the
    -14 LUFS that TikTok, Reels and Shorts play at. Length and timing are unchanged.
    """
    ffmpeg = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found: voice left un-normalised (the reel will be quieter than usual)")
        return
    tmp = path.with_suffix(".norm.wav")
    subprocess.run(
        [*ffmpeg.split(), "-y", "-loglevel", "error", "-i", str(path),
         "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11", "-ar", str(SR), str(tmp)],
        check=True,
    )
    tmp.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Remotion project folder (holds pray.json and public/)")
    ap.add_argument("--config", help="defaults to <project>/pray.json")
    ap.add_argument("--voice")
    ap.add_argument("--speed", type=float)
    ap.add_argument("--lang", default="en-us")
    args = ap.parse_args()

    project = Path(args.project)
    OUT = project / "public" / "audio" / "pray"
    cfg = json.loads(Path(args.config or project / "pray.json").read_text())
    vcfg = cfg.get("voice", {})
    voice = args.voice or vcfg.get("name", "af_heart")
    speed = args.speed or vcfg.get("speed", 0.76)
    lead, gap, tail = vcfg.get("leadInSeconds", 0.8), vcfg.get("gapSeconds", 1.2), vcfg.get("tailSeconds", 2.0)
    lang = "en-gb" if voice[:1] == "b" else args.lang

    k = Kokoro(*find_models())
    OUT.mkdir(parents=True, exist_ok=True)

    timeline = [np.zeros(int(lead * SR), dtype=np.float32)]
    t = lead
    phrases = []
    for text in cfg["phrases"]:
        spoken = text.replace("*", "")  # accent markers are for the screen, not the voice
        audio, sr = k.create(spoken, voice=voice, speed=speed, lang=lang)
        assert sr == SR, sr
        audio = trim_silence(audio.astype(np.float32))
        dur = len(audio) / SR

        words = parse_phrase(text)
        weights = word_weights(k, [w for w, _ in words], lang)
        total = sum(weights)
        word_times, acc = [], 0.0
        for (w, accent), wt in zip(words, weights):
            start = t + dur * acc / total
            acc += wt
            word_times.append(
                {"text": w, "start": round(start, 3), "end": round(t + dur * acc / total, 3), "accent": accent}
            )

        phrases.append({"text": text, "start": round(t, 3), "end": round(t + dur, 3), "words": word_times})
        timeline += [audio, np.zeros(int(gap * SR), dtype=np.float32)]
        t += dur + gap
        print(f"{dur:5.2f}s  {text}")

    timeline[-1] = np.zeros(int(tail * SR), dtype=np.float32)  # replace the last gap with the tail
    voice_audio = np.concatenate(timeline)
    peak = np.max(np.abs(voice_audio)) or 1.0
    voice_audio = voice_audio / peak * 0.89  # about -1 dBFS peak
    sf.write(OUT / "voice.wav", voice_audio, SR)
    normalize_loudness(OUT / "voice.wav")

    total_s = len(voice_audio) / SR
    (OUT / "timing.json").write_text(
        json.dumps({"voice": voice, "speed": speed, "durationSeconds": round(total_s, 3), "phrases": phrases}, indent=2)
    )
    print(f"\nvoice.wav  {total_s:.2f}s  ({voice}, speed {speed}) -> {OUT}")


if __name__ == "__main__":
    main()
