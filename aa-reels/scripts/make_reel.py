#!/usr/bin/env python3
"""Make an Awake America prayer reel (AA Reels) in one command.

    python3 make_reel.py --spec prayer.json --background /path/to/photo-or-video [--out reel.mp4]

prayer.json holds the intake answers:
    {
      "template": 1,                 # 1, 2 or 3
      "voiceover": true,             # false = no voice
      "music": true,                 # false = no music
      "voice": "female",             # "female" / "male" (or a Kokoro voice id)
      "reference": "Psalm 85:6",     # as the user typed it
      "phrases": ["Your faith may feel weak,", "Lord, *revive* us again,", "Amen."]
    }
One phrase per screen; *stars* mark accent words (red tag in templates 1 and 3).
Optional keys: "label" (default "Pray the scriptures"), "speed" (0.6-1.0), "seed" (music
variation), "overlay", "zoom", "musicVolume".

First run sets everything up (about 1-2 minutes): Node packages, Python packages,
the Kokoro voice model (~350 MB) and a headless browser. Later runs reuse them.
Steps: setup -> voice -> music -> render -> loudness (-14 LUFS) -> out file.

Flags:
    --no-voice   skip the voiceover (same as "voiceover": false)
    --still      also save a PNG of the first phrase fully revealed (for a quick check)
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / "project"
WORK = Path(os.environ.get("AA_REELS_WORK", Path.home() / "aa-reels-work"))
PROJECT = WORK / "project"
MODELS = Path(os.environ.get("KOKORO_DIR", WORK / "models" / "kokoro"))
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}

DEFAULTS = {
    "label": "Pray the scriptures",
    "overlay": 0.48,
    "zoom": 1.08,
    "musicVolume": 0.22,
    "voice": {"name": "af_heart", "speed": 0.76, "leadInSeconds": 1.0, "gapSeconds": 1.2, "tailSeconds": 2.2},
}
# "Voice: Male/Female" from the intake -> Kokoro voices (any Kokoro voice id also works).
VOICES = {"female": "af_heart", "male": "am_michael"}


class SetupError(SystemExit):
    pass


def log(msg: str) -> None:
    print(f"[aa-reels] {msg}", flush=True)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, quiet: bool = False) -> str:
    res = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, text=True, capture_output=True)
    if res.returncode != 0:
        tail = "\n".join((res.stdout + res.stderr).strip().splitlines()[-25:])
        raise SetupError(f"Command failed: {' '.join(cmd)}\n{tail}")
    if not quiet and res.stdout.strip():
        print(res.stdout.strip())
    return res.stdout


# ---------------------------------------------------------------- setup


def template_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(TEMPLATE.rglob("*")):
        if p.is_file() and "node_modules" not in p.parts:
            h.update(str(p.relative_to(TEMPLATE)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def ensure_project() -> None:
    """Copy the bundled Remotion project to a writable folder and install packages."""
    stamp = PROJECT / ".skill-version"
    want = template_hash()
    if not (stamp.exists() and stamp.read_text() == want):
        log("Preparing the video project...")
        keep_modules = PROJECT / "node_modules"
        tmp_modules = WORK / "node_modules.keep"
        if keep_modules.exists():
            shutil.rmtree(tmp_modules, ignore_errors=True)
            keep_modules.rename(tmp_modules)
        shutil.rmtree(PROJECT, ignore_errors=True)
        shutil.copytree(TEMPLATE, PROJECT, ignore=shutil.ignore_patterns("node_modules"))
        if tmp_modules.exists():
            tmp_modules.rename(keep_modules)
        stamp.write_text(want)
    if not (PROJECT / "node_modules" / "@remotion" / "cli").exists():
        if not shutil.which("npm"):
            raise SetupError("Node.js/npm is not available in this environment, so the video can't be rendered.")
        log("Installing video packages from npm (first run only, ~40 s)...")
        cmd = ["npm", "ci" if (PROJECT / "package-lock.json").exists() else "install", "--no-audit", "--no-fund"]
        run(cmd, cwd=PROJECT, quiet=True)


def ensure_python_packages(need_voice: bool) -> None:
    mods = {"numpy": "numpy", "soundfile": "soundfile", "PIL": "pillow"}
    if need_voice:
        mods["kokoro_onnx"] = "kokoro-onnx"
    missing = []
    for mod, pkg in mods.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        log(f"Installing Python packages: {', '.join(missing)}")
        base = [sys.executable, "-m", "pip", "install", "-q", *missing]
        try:
            run(base + ["--break-system-packages"], quiet=True)
        except SetupError:
            run(base, quiet=True)


def ensure_voice_model() -> None:
    MODELS.mkdir(parents=True, exist_ok=True)
    for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        dest = MODELS / name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            continue
        log(f"Downloading voice model {name} from GitHub (first run only)...")
        part = dest.with_suffix(dest.suffix + ".part")
        try:
            import urllib.request

            urllib.request.urlretrieve(KOKORO_URL + name, part)
            part.rename(dest)
        except Exception as e:  # noqa: BLE001
            part.unlink(missing_ok=True)
            raise SetupError(
                "VOICE_MODEL_BLOCKED: couldn't download the voice model from github.com "
                f"({e}).\nFix: allow github.com under Settings > Capabilities (network access), "
                "or run again with --no-voice for a silent reel with music."
            )


def find_browser() -> str | None:
    """A headless Chromium already on this machine. Checks known locations first."""
    if os.environ.get("AA_REELS_FORCE_NPM_BROWSER"):  # for testing the npm fallback
        return None
    env = os.environ.get("REMOTION_BROWSER_EXECUTABLE")
    if env and Path(env).exists():
        return env
    patterns = [
        "/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
        str(Path.home() / ".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"),
        str(PROJECT / "node_modules/.remotion/chrome-headless-shell/*/chrome-headless-shell-linux64/chrome-headless-shell"),
        "/opt/pw-browsers/chromium-*/chrome-linux*/chrome",
        str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux*/chrome"),
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome-headless-shell"):
        if shutil.which(name):
            return shutil.which(name)
    return None


def npm_browser() -> str | None:
    """Chromium packaged on npm (@sparticuz/chromium). npm is reachable on every plan,
    so this works even where browser download sites are blocked."""
    folder = WORK / "chromium"
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / "node_modules" / "@sparticuz" / "chromium").exists():
        log("Installing a headless browser from npm (first run only, ~20 s)...")
        if not (folder / "package.json").exists():
            (folder / "package.json").write_text('{"private": true}')
        run(["npm", "install", "--no-audit", "--no-fund", "@sparticuz/chromium@153.0.0"], cwd=folder, quiet=True)
    out = run(["node", "-e", "require('@sparticuz/chromium').default.executablePath().then(p=>console.log(p))"],
              cwd=folder, quiet=True).strip().splitlines()
    path = out[-1] if out else ""
    return path if path and Path(path).exists() else None


def ensure_browser() -> tuple[str | None, list[str]]:
    """Returns (browser path, extra Remotion flags)."""
    found = find_browser()
    if found:
        return found, []
    try:
        path = npm_browser()
        if path:
            # This build has no GPU and runs in headless-shell mode.
            return path, ["--gl=swiftshader", "--chrome-mode=headless-shell"]
    except SetupError as e:
        log(f"npm browser unavailable ({str(e).splitlines()[0]}); trying Remotion's download...")
    try:
        run(["npx", "remotion", "browser", "ensure"], cwd=PROJECT, quiet=True)
        return find_browser(), []
    except SetupError as e:
        raise SetupError(
            "BROWSER_BLOCKED: no headless browser is available and none could be installed.\n"
            "Fix: allow registry.npmjs.org (or remotion.media) under Settings > Capabilities, then try again.\n"
            + str(e)
        )


def ffmpeg_cmd() -> str:
    """System ffmpeg if present, else the one bundled with Remotion (always installed)."""
    return shutil.which("ffmpeg") or "npx remotion ffmpeg"


def loudnorm_filter(ff: str, media: Path) -> str:
    """Two-pass loudnorm: measure first, then a linear gain that respects the peak limit.

    One-pass loudnorm can overshoot the true-peak limit once AAC-encoded, so we
    measure and aim 1 dB lower on peaks. Falls back to one pass if measuring fails.
    """
    target = "I=-14:TP=-2.5:LRA=11"
    res = subprocess.run(
        [*ff.split(), "-hide_banner", "-i", str(media), "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"],
        cwd=PROJECT, text=True, capture_output=True,
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr)
    if res.returncode != 0 or not m:
        return f"loudnorm={target}"
    s = json.loads(m.group(0))
    return (
        f"loudnorm={target}:measured_I={s['input_i']}:measured_TP={s['input_tp']}:"
        f"measured_LRA={s['input_lra']}:measured_thresh={s['input_thresh']}:offset={s['target_offset']}:linear=true"
    )


# ---------------------------------------------------------------- media + config


def place_background(src: Path | None) -> str:
    media = PROJECT / "public" / "media"
    shutil.rmtree(media, ignore_errors=True)
    media.mkdir(parents=True)
    if not src:
        return "media/none"
    if not src.exists():
        raise SetupError(f"Background file not found: {src}")
    ext = src.suffix.lower()
    if ext in VIDEO_EXT:
        dest = media / f"background{ext}"
        shutil.copy(src, dest)
        return f"media/{dest.name}"
    # Images: normalise anything (HEIC, huge PNGs, odd colour modes) to a 2160px-tall JPEG.
    from PIL import Image, ImageOps

    try:
        if ext in (".heic", ".heif"):
            try:
                import pillow_heif  # type: ignore

                pillow_heif.register_heif_opener()
            except ImportError:
                ensure_pip("pillow-heif")
                import pillow_heif  # type: ignore

                pillow_heif.register_heif_opener()
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    except Exception as e:  # noqa: BLE001
        raise SetupError(f"Couldn't open the background image {src.name}: {e}")
    if im.height > 2160:
        im = im.resize((round(im.width * 2160 / im.height), 2160), Image.LANCZOS)
    if im.width < 700:
        log(f"Note: the image is only {im.width}px wide; it will look soft at 1080px. A larger image looks sharper.")
    dest = media / "background.jpg"
    im.save(dest, quality=92)
    return "media/background.jpg"


def ensure_pip(pkg: str) -> None:
    base = [sys.executable, "-m", "pip", "install", "-q", pkg]
    try:
        run(base + ["--break-system-packages"], quiet=True)
    except SetupError:
        run(base, quiet=True)


def build_props(spec: dict, background: str, voice_override: str | None) -> dict:
    """Turns the intake answers (spec) into the video's props.

    spec keys: template (1-3), reference, phrases, voiceover (bool), voice ("male"/"female"
    or a Kokoro id). Optional: label, speed, seed, overlay, zoom, musicVolume.
    """
    phrases = [p.strip() for p in spec["phrases"] if p and p.strip()]
    if not phrases:
        raise SetupError("The spec has no phrases.")
    try:
        template = int(spec.get("template", 1))
    except (TypeError, ValueError):
        raise SetupError("template must be 1, 2 or 3.")
    if template not in (1, 2, 3):
        raise SetupError("template must be 1, 2 or 3.")
    voice = dict(DEFAULTS["voice"])
    name = str(voice_override or spec.get("voice") or "female").strip()
    voice["name"] = VOICES.get(name.lower(), name)
    if spec.get("speed"):
        voice["speed"] = float(spec["speed"])
    return {
        "template": template,
        "reference": str(spec.get("reference", "")).strip(),
        "label": spec.get("label", DEFAULTS["label"]),
        "phrases": phrases,
        "background": background,
        "overlay": float(spec.get("overlay", DEFAULTS["overlay"])),
        "zoom": float(spec.get("zoom", DEFAULTS["zoom"])),
        "voice": voice,
        "music": "audio/pray/music.wav",
        "musicVolume": float(spec.get("musicVolume", DEFAULTS["musicVolume"])),
    }


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "prayer"


def default_out(props: dict) -> Path:
    outputs = Path("/mnt/user-data/outputs")
    base = outputs if outputs.exists() else WORK / "out"
    base.mkdir(parents=True, exist_ok=True)
    name = slug(props["reference"] or props["phrases"][0])
    return base / f"aa-reel-{name}-t{props['template']}.mp4"


# ---------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="JSON with the intake answers (see top of file)")
    ap.add_argument("--background", help="photo or video the user uploaded")
    ap.add_argument("--out", help="output .mp4 (default: /mnt/user-data/outputs/prayer-reel-<ref>.mp4)")
    ap.add_argument("--voice", help="male, female, or a Kokoro voice id (overrides the spec)")
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--still", action="store_true", help="also save a PNG preview of the first phrase")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        raise SetupError(f"Spec file not found: {spec_path}")
    try:
        spec = json.loads(spec_path.read_text())
    except json.JSONDecodeError as e:
        raise SetupError(f"The spec isn't valid JSON ({e}).")
    if not isinstance(spec.get("phrases"), list):
        raise SetupError('The spec needs a "phrases" list.')
    # "Voiceover: No" in the intake, or --no-voice
    vo = spec.get("voiceover", True)
    no_voice = args.no_voice or vo is False or str(vo).strip().lower() in ("no", "false", "0", "off")
    # "Music: On/Off" in the intake (on by default)
    mu = spec.get("music", True)
    no_music = mu is False or str(mu).strip().lower() in ("no", "false", "0", "off")
    WORK.mkdir(parents=True, exist_ok=True)

    ensure_project()
    ensure_python_packages(need_voice=not no_voice)
    if not no_voice:
        ensure_voice_model()
    browser, browser_flags = ensure_browser()
    ff = ffmpeg_cmd()
    scripts = SKILL / "scripts"

    background = place_background(Path(args.background) if args.background else None)
    props = build_props(spec, background, args.voice)
    (PROJECT / "pray.json").write_text(json.dumps(props, indent=2))

    audio = PROJECT / "public" / "audio" / "pray"
    shutil.rmtree(audio, ignore_errors=True)
    audio.mkdir(parents=True)

    if not no_voice:
        log(f"Recording the voiceover ({props['voice']['name']})...")
        run([sys.executable, str(scripts / "gen_voice.py"), "--project", str(PROJECT)],
            cwd=PROJECT, env={"KOKORO_DIR": str(MODELS), "FFMPEG": ff})
        voice_len = json.loads((audio / "timing.json").read_text())["durationSeconds"]
    else:
        # Same pace as timingWithoutVoice() in project/src/pray/timing.ts
        counts = [len(p.replace("*", "").split()) for p in props["phrases"]]
        v = props["voice"]
        voice_len = v["leadInSeconds"] + sum(max(2.4, n * 0.42 + 0.8) for n in counts) + 0.7 * (len(counts) - 1) + v["tailSeconds"]
        log(f"No voiceover: {len(counts)} phrases, {sum(counts)} words.")

    if no_music:
        props.pop("music", None)
        (PROJECT / "pray.json").write_text(json.dumps(props, indent=2))
        log("Music: off.")
    else:
        seed = int(spec.get("seed", int(hashlib.md5(" ".join(props["phrases"]).encode()).hexdigest(), 16) % 1000))
        log(f"Composing the music (seed {seed})...")
        run([sys.executable, str(scripts / "gen_music.py"), "--project", str(PROJECT),
             "--seconds", f"{voice_len + 1:.2f}", "--seed", str(seed)], cwd=PROJECT)

    cores = max(1, min(4, os.cpu_count() or 1))
    common = ["--props=pray.json", f"--concurrency={cores}"] + (
        [f"--browser-executable={browser}", *browser_flags] if browser else [])
    out = Path(args.out) if args.out else default_out(props)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.still:
        still = out.with_suffix(".png")
        # First phrase, fully revealed and not yet leaving.
        if no_voice:
            n = len(props["phrases"][0].replace("*", "").split())
            frame = int((props["voice"]["leadInSeconds"] + 0.22 * n + 0.7) * 30)
        else:
            t = json.loads((audio / "timing.json").read_text())["phrases"][0]["end"]
            frame = int((t + 0.35) * 30)
        run(["npx", "remotion", "still", "PrayScripture", str(still), f"--frame={frame}", *common[:1],
             *common[2:]], cwd=PROJECT, quiet=True)
        log(f"Preview still: {still}")

    log("Rendering the video (about 1-3 minutes)...")
    raw = PROJECT / "out" / "raw.mp4"
    run(["npx", "remotion", "render", "PrayScripture", str(raw), *common], cwd=PROJECT, quiet=True)

    if no_voice and no_music:
        log("No voice and no music: the video is silent.")
        run([*ff.split(), "-y", "-loglevel", "error", "-i", str(raw), "-c", "copy", "-movflags", "+faststart", str(out)],
            cwd=PROJECT, quiet=True)
    else:
        log("Setting loudness for TikTok/Reels (-14 LUFS)...")
        run([*ff.split(), "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "copy",
             "-af", loudnorm_filter(ff, raw), "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", str(out)], cwd=PROJECT, quiet=True)

    size = out.stat().st_size / 1e6
    log(f"DONE: {out}  ({voice_len:.1f}s, {size:.1f} MB)")


if __name__ == "__main__":
    try:
        main()
    except SetupError as e:
        print(f"[aa-reels] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
