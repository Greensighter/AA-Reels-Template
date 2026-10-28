#!/usr/bin/env python3
"""Calm worship-style music bed, synthesised locally (no API, no licensing).

Soft string pad + sparse felt-piano arpeggios over a slow I-V-vi-IV progression,
in a large reverb. Length follows the voiceover (<project>/public/audio/pray/timing.json)
unless --seconds is given. Output: <project>/public/audio/pray/music.wav (stereo, 44.1k).

  python3 gen_music.py --project <remotion project> [--seconds 30] [--key D] [--bpm 64] [--seed 7]

Change --seed for a different melody with the same mood.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
# Scale degrees (semitones from the tonic) for I, V, vi, IV, as triads plus a soft added 9th.
PROGRESSION = [[0, 4, 7, 14], [7, 11, 14, 21], [9, 12, 16, 23], [5, 9, 12, 19]]


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def adsr(n: int, a: float, r: float) -> np.ndarray:
    env = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    env[:na] = np.linspace(0, 1, na) ** 2
    if nr:
        env[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return env


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    # two passes of a one-pole filter = gentle 12 dB/oct roll-off
    a = np.exp(-2 * np.pi * cutoff / SR)
    for _ in range(2):
        y = np.empty_like(x)
        acc = 0.0
        for i in range(0, len(x), 4096):  # chunked to keep it reasonably quick
            seg = x[i : i + 4096]
            out = np.empty_like(seg)
            for j, v in enumerate(seg):
                acc = (1 - a) * v + a * acc
                out[j] = acc
            y[i : i + 4096] = out
        x = y
    return x


def pad_chord(midis: list[int], seconds: float, rng: np.random.Generator) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in midis:
        for detune in (-0.06, 0.0, 0.07):  # slightly detuned voices = string-section width
            f = hz(m + detune)
            ph = rng.uniform(0, 2 * np.pi)
            vib = 0.0015 * np.sin(2 * np.pi * 4.8 * t + ph)
            # saw-ish tone from a few harmonics, softened later by the low-pass
            tone = sum(np.sin(2 * np.pi * f * k * (t + vib) + ph * k) / k**1.3 for k in range(1, 6))
            out += tone
    return out / (len(midis) * 3)


def piano_note(midi: int, seconds: float, vel: float) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    out = np.zeros(n)
    for k, amp in enumerate([1.0, 0.45, 0.22, 0.12, 0.06], start=1):
        fk = f * k * np.sqrt(1 + 0.0004 * k * k)  # slight string inharmonicity
        out += amp * np.sin(2 * np.pi * fk * t) * np.exp(-t * (1.2 + 0.9 * k))
    attack = np.minimum(1, t / 0.006)
    return vel * out * attack


def reverb(x: np.ndarray, seconds: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t * 6.9 / seconds)  # -60 dB at `seconds`
    ir[: int(0.02 * SR)] = 0  # pre-delay
    ir /= np.sqrt(np.sum(ir**2))
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x) + n]
    return y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Remotion project folder")
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--key", default="D")
    ap.add_argument("--bpm", type=float, default=64)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    OUT = Path(args.project) / "public" / "audio" / "pray"
    seconds = args.seconds
    if seconds is None:
        timing = OUT / "timing.json"
        seconds = json.loads(timing.read_text())["durationSeconds"] + 1.0 if timing.exists() else 30.0

    rng = np.random.default_rng(args.seed)
    root = 50 + NOTE[args.key]  # around D3
    beat = 60 / args.bpm
    bar = beat * 4
    n = int(seconds * SR)
    pad = np.zeros(n + SR * 6)
    piano = np.zeros(n + SR * 6)

    bars = int(np.ceil(seconds / bar))
    for b in range(bars):
        chord = [root + d for d in PROGRESSION[b % 4]]
        start = int(b * bar * SR)
        # pad: chord held a little past the bar so changes overlap smoothly
        p = pad_chord(chord, bar + 1.5, rng) * adsr(int((bar + 1.5) * SR), 1.2, 1.6)
        pad[start : start + len(p)] += p
        # piano: gentle arpeggio up an octave, some notes left out so it breathes
        arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[3] + 12, chord[2] + 12, chord[1] + 24]
        for i in range(8):
            if rng.random() < 0.3 and i not in (0, 4):
                continue
            note = arp[i % len(arp)] + (12 if (b % 4 == 3 and i == 6) else 0)
            s = start + int(i * beat / 2 * SR) + int(rng.normal(0, 0.008) * SR)
            vel = (0.55 if i % 4 == 0 else 0.35) * rng.uniform(0.85, 1.0)
            pn = piano_note(note, 3.5, vel)
            piano[max(0, s) : max(0, s) + len(pn)] += pn[: len(piano) - max(0, s)]
        # bass: root note once per bar
        bn = piano_note(chord[0] - 12, bar + 1, 0.45)
        piano[start : start + len(bn)] += bn[: len(piano) - start]

    pad = lowpass(pad, 1400)
    mix = 0.55 * pad + 0.5 * piano
    mix = mix[:n]

    wet_l = reverb(mix, 3.2, args.seed)[:n]
    wet_r = reverb(mix, 3.4, args.seed + 1)[:n]
    left = 0.65 * mix + 0.6 * wet_l
    right = 0.65 * np.roll(mix, int(0.011 * SR)) + 0.6 * wet_r
    # high-pass at ~60 Hz: removes rumble that only muddies phone speakers
    left, right = left - lowpass(left, 60), right - lowpass(right, 60)
    stereo = np.stack([left, right], axis=1)

    fade_in, fade_out = int(1.5 * SR), int(3.0 * SR)
    stereo[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    stereo[-fade_out:] *= (np.linspace(1, 0, fade_out) ** 1.5)[:, None]
    stereo /= np.max(np.abs(stereo)) or 1.0
    stereo *= 0.8

    OUT.mkdir(parents=True, exist_ok=True)
    sf.write(OUT / "music.wav", stereo.astype(np.float32), SR)
    print(f"music.wav  {seconds:.1f}s  key {args.key}, {args.bpm:.0f} bpm, seed {args.seed} -> {OUT}")


if __name__ == "__main__":
    main()
