#!/usr/bin/env python3
"""Make an Awake America prayer reel (AA Reels) in one command.

    python3 make_reel.py --spec prayer.json --background photo-or-video [more files...] [--out reel.mp4]

prayer.json holds the intake answers:
    {
      "template": 1,                 # 1 = line by line, 2 = whole prayer at once
      "voiceover": true,             # false = no voice
      "music": true,                 # false = no music
      "voice": "female",             # "female" / "male" (or a Kokoro voice id)
      "reference": "Psalm 85:6",     # as the user typed it
      "phrases": ["Your faith may feel weak,", "Lord, *revive* us again,", "Amen."]
    }
One phrase per screen in template 1; *stars* mark accent words (the red tag).
Several --background files take turns with a crossfade (photos and videos can be mixed).
Optional keys: "label" (default "Pray the scriptures"), "speed" (0.6-1.0), "seed" (music
variation), "overlay", "zoom", "musicVolume", "autoHighlight" (false = never add a highlight).
Full stops are hidden on screen automatically (the voice still pauses at them).

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
# Template number -> how the prayer appears (must match project/src/pray/templates.ts).
TEMPLATES = {1: "phrases", 2: "static"}

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


def available_memory_gb() -> float:
    """Memory free for the render, from /proc/meminfo or the container limit (whichever is lower)."""
    avail = 64.0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                avail = int(line.split()[1]) / 1024 / 1024
    except OSError:
        pass
    for f in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            v = Path(f).read_text().strip()
            if v.isdigit() and int(v) < 1 << 50:
                avail = min(avail, int(v) / 1024 ** 3)
        except OSError:
            pass
    return avail


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


MAX_BACKGROUNDS = 10


def place_backgrounds(sources: list[Path], ff: str = "ffmpeg") -> list[str]:
    """Copies the user's photos/videos into the project, in order. Returns their public/ paths."""
    media = PROJECT / "public" / "media"
    shutil.rmtree(media, ignore_errors=True)
    media.mkdir(parents=True)
    if len(sources) > MAX_BACKGROUNDS:
        log(f"Note: using the first {MAX_BACKGROUNDS} of {len(sources)} files.")
        sources = sources[:MAX_BACKGROUNDS]
    return [place_one(src, media, i + 1, ff) for i, src in enumerate(sources)]


def video_info(ff: str, src: Path) -> tuple[int, str]:
    """(width, codec) of a video's first stream, read from ffmpeg's banner. (0, "") if unknown."""
    res = subprocess.run([*ff.split(), "-hide_banner", "-i", str(src)], cwd=PROJECT, text=True, capture_output=True)
    m = re.search(r"Video: (\w+).*?, (\d{2,5})x(\d{2,5})", res.stderr)
    return (int(m.group(2)), m.group(1)) if m else (0, "")


def place_one(src: Path, media: Path, n: int, ff: str = "ffmpeg") -> str:
    if not src.exists():
        raise SetupError(f"Background file not found: {src}")
    ext = src.suffix.lower()
    if ext in VIDEO_EXT:
        width, codec = video_info(ff, src)
        if width > 1200 or codec not in ("h264", ""):
            # Phone/4K clips: shrink to 1080 wide H.264 (sharp enough for 1080x1920, much faster to
            # render, and it also covers HEVC/ProRes files). Sound is dropped: backgrounds are muted.
            dest = media / f"bg-{n}.mp4"
            log(f"Preparing video {src.name} ({width}px {codec or '?'} -> 1080px H.264)...")
            run([*ff.split(), "-y", "-loglevel", "error", "-i", str(src), "-an",
                 "-vf", "scale='min(1080,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest)], cwd=PROJECT, quiet=True)
        else:
            dest = media / f"bg-{n}{ext}"
            shutil.copy(src, dest)
        return f"media/{dest.name}"
    # Images: normalise anything (HEIC, huge PNGs, odd colour modes) to a 2160px-tall JPEG.
    from PIL import Image, ImageOps

    try:
        if ext in (".heic", ".heif"):
            try:
                import pillow_heif  # type: ignore
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
        log(f"Note: {src.name} is only {im.width}px wide; it will look soft at 1080px. A larger image looks sharper.")
    dest = media / f"bg-{n}.jpg"
    im.save(dest, quality=92)
    return f"media/{dest.name}"


def ensure_pip(pkg: str) -> None:
    base = [sys.executable, "-m", "pip", "install", "-q", pkg]
    try:
        run(base + ["--break-system-packages"], quiet=True)
    except SetupError:
        run(base, quiet=True)


def build_props(spec: dict, backgrounds: list[str], voice_override: str | None) -> dict:
    """Turns the intake answers (spec) into the video's props.

    spec keys: template (1-2), reference, phrases, voiceover (bool), voice ("male"/"female"
    or a Kokoro id). Optional: label, speed, seed, overlay, zoom, musicVolume.
    """
    phrases = [p.strip() for p in spec["phrases"] if p and p.strip()]
    if not phrases:
        raise SetupError("The spec has no phrases.")
    try:
        template = int(spec.get("template", 1))
    except (TypeError, ValueError):
        raise SetupError(f"template must be one of: {', '.join(map(str, TEMPLATES))}.")
    if template not in TEMPLATES:
        raise SetupError(f"template must be one of: {', '.join(map(str, TEMPLATES))}.")
    if TEMPLATES[template] == "static":
        # Template 2 has no highlights: drop any *stars* so the voice and text are plain.
        if any("*" in p for p in phrases):
            log("Template 2 has no highlighted words; showing them as plain text.")
        phrases = [p.replace("*", "") for p in phrases]
    elif spec.get("autoHighlight", True) is not False:
        phrases, picked = auto_highlight(phrases)
        if picked:
            log(f"No highlighted word given; highlighting \"{picked}\".")
    voice = dict(DEFAULTS["voice"])
    name = str(voice_override or spec.get("voice") or "female").strip()
    voice["name"] = VOICES.get(name.lower(), name)
    if spec.get("speed"):
        voice["speed"] = float(spec["speed"])
    if TEMPLATES[template] == "static":
        voice["gapSeconds"] = 0.55  # the whole prayer is read in one go
    else:
        split = split_for_screens(phrases)
        if split != phrases:
            log(f"Long lines split into {len(split)} screens (words unchanged):")
            for i, line in enumerate(split, 1):
                print(f"    {i}. {line}", flush=True)
            phrases = split
    return {
        "template": template,
        "reference": str(spec.get("reference", "")).strip(),
        "label": spec.get("label", DEFAULTS["label"]),
        "phrases": phrases,
        "backgrounds": backgrounds,
        "overlay": float(spec.get("overlay", DEFAULTS["overlay"])),
        "zoom": float(spec.get("zoom", DEFAULTS["zoom"])),
        "voice": voice,
        "music": "audio/pray/music.wav",
        "musicVolume": float(spec.get("musicVolume", DEFAULTS["musicVolume"])),
    }


# Safety net for highlights: Claude normally picks the accent word(s) itself (see SKILL.md).
# If a prayer arrives with no *stars* at all, one word is highlighted automatically.
KEY_WORDS = [
    "prayer", "pray", "faith", "grace", "hope", "peace", "mercy", "love", "strength", "revive",
    "revival", "healing", "heal", "joy", "light", "truth", "freedom", "rest", "trust", "glory",
    "power", "victory", "courage", "salvation", "forgiven", "forgive", "blessing", "promise",
    "jesus", "christ", "spirit",
]


def auto_highlight(phrases: list[str]) -> tuple[list[str], str | None]:
    """Wraps one meaningful word in *stars* when none are marked. Returns (phrases, word)."""
    if any("*" in p for p in phrases):
        return phrases, None
    tokens = [(i, j, tok) for i, p in enumerate(phrases) for j, tok in enumerate(p.split())]

    def core(tok: str) -> str:
        return re.sub(r"[^\w'’]", "", tok).lower()

    pick = None
    for key in KEY_WORDS:  # most meaningful first
        hits = [t for t in tokens if core(t[2]) == key]
        if hits:
            pick = hits[-1]  # the later mention is usually the point of the prayer
            break
    if pick is None:  # otherwise the longest word (5+ letters) of the last real line
        lines = [i for i, p in enumerate(phrases) if core(p) not in ("amen", "")]
        last = lines[-1] if lines else len(phrases) - 1
        cands = [t for t in tokens if t[0] == last and len(core(t[2])) >= 5]
        pick = max(cands, key=lambda t: len(core(t[2]))) if cands else None
    if pick is None:
        return phrases, None
    i, j, tok = pick
    m = re.match(r"^([\"'“‘(]*)(.*?)([,.;:!?\"'”’)]*)$", tok)
    lead, word, trail = m.groups() if m else ("", tok, "")
    words = phrases[i].split()
    words[j] = f"{lead}*{word}*{trail}"
    out = list(phrases)
    out[i] = " ".join(words)
    return out, word


MAX_WORDS_PER_SCREEN = 9


def _tokens_safe_breaks(tokens: list[str]) -> list[bool]:
    """breakable[i] is True if a screen may end after token i (never inside *stars*)."""
    out, inside = [], False
    for tok in tokens:
        if tok.startswith("*"):
            inside = True
        if re.sub(r"[,.;:!?\"')\]]+$", "", tok).endswith("*"):
            inside = False
        out.append(not inside)
    return out


def _split_at(tokens: list[str], pattern: str) -> list[list[str]]:
    """Splits after tokens matching `pattern` (punctuation at the end of a word)."""
    safe = _tokens_safe_breaks(tokens)
    parts, cur = [], []
    for i, tok in enumerate(tokens):
        cur.append(tok)
        if safe[i] and re.search(pattern, tok.replace("*", "")) and i < len(tokens) - 1:
            parts.append(cur)
            cur = []
    if cur:
        parts.append(cur)
    return parts


def _balanced(tokens: list[str], limit: int) -> list[list[str]]:
    """Evenly sized chunks of at most `limit` words, moving cuts out of *star* groups."""
    k = -(-len(tokens) // limit)
    size = -(-len(tokens) // k)
    safe = _tokens_safe_breaks(tokens)
    chunks, start = [], 0
    joiners = {"and", "but", "or", "so", "that", "for", "when", "because", "who", "with", "in", "to", "as", "if"}
    while start < len(tokens):
        end = min(len(tokens), start + size)
        if end < len(tokens):
            # Prefer to start the next screen with a joining word ("... / and I shall"), within 2 words.
            for d in (0, -1, 1, -2, 2):
                e = end + d
                if start + 2 <= e < len(tokens) and e - start <= limit and safe[e - 1] \
                        and tokens[e].strip("*\"'(").lower() in joiners:
                    end = e
                    break
        while end < len(tokens) and not safe[end - 1]:
            end += 1
        chunks.append(tokens[start:end])
        start = end
    return chunks


def _pack(pieces: list[list[str]], limit: int) -> list[list[str]]:
    """Joins neighbouring pieces while they fit on one screen."""
    out: list[list[str]] = []
    for piece in pieces:
        if out and len(out[-1]) + len(piece) <= limit and not re.search(r"[.!?][\"')\]]*$", out[-1][-1].replace("*", "")):
            out[-1] = out[-1] + piece
        else:
            out.append(piece)
    return out


def split_for_screens(lines: list[str], limit: int = MAX_WORDS_PER_SCREEN) -> list[str]:
    """Template 1 shows one line per screen. Long lines (e.g. a whole prayer pasted on
    one line) are split, without changing any words: first at sentence ends, then at
    commas/semicolons/colons/dashes, and only then evenly. *Star* groups stay whole."""
    screens: list[str] = []
    for line in lines:
        tokens = line.split()
        if len(tokens) <= limit:
            screens.append(line)
            continue
        for sentence in _split_at(tokens, r"[.!?][\"')\]]*$"):
            if len(sentence) <= limit:
                screens.append(" ".join(sentence))
                continue
            pieces = _split_at(sentence, r"([,;:]|—|–)[\"')\]]*$")
            for chunk in _pack(pieces, limit):
                parts = _balanced(chunk, limit) if len(chunk) > limit else [chunk]
                screens.extend(" ".join(p) for p in parts)
    return screens


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
    ap.add_argument("--background", nargs="+", default=[], metavar="FILE",
                    help="one or more photos/videos the user uploaded, in order")
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

    backgrounds = place_backgrounds([Path(b) for b in args.background], ff)
    props = build_props(spec, backgrounds, args.voice)
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
        if TEMPLATES[props["template"]] == "static":
            voice_len = max(6.0, v["leadInSeconds"] + sum(counts) * 0.4 + v["tailSeconds"])
        else:
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
    flags = []
    if any(Path(b).suffix.lower() in VIDEO_EXT for b in props["backgrounds"]):
        # Video backgrounds: cap the decoded-frame cache (by default it can grow to half the RAM
        # and get the renderer killed), and use one worker when memory is tight.
        flags.append(f"--offthreadvideo-cache-size-in-bytes={256 * 1024 * 1024}")
        if available_memory_gb() < 5:
            cores = 1
    common = ["--props=pray.json", f"--concurrency={cores}", *flags] + (
        [f"--browser-executable={browser}", *browser_flags] if browser else [])
    out = Path(args.out) if args.out else default_out(props)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.still:
        still = out.with_suffix(".png")
        # First phrase, fully revealed and not yet leaving (static: the whole prayer, shown from the start).
        if TEMPLATES[props["template"]] == "static":
            frame = int(2.0 * 30)
        elif no_voice:
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
