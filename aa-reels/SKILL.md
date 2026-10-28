---
name: aa-reels
description: Makes Awake America prayer reels (9:16 videos for TikTok, Reels, Shorts) from the user's own prayer text and photo or video, in templates 1-3, with optional voiceover and music.
---

# AA Reels

Makes a finished 1080×1920 MP4 in the Awake America "Pray the Scriptures"
style, from the user's answers to a short form:

- **Template 1, 2 or 3**: three layouts from the AA design (`assets/templates.png`)
- the user's photo or video as the background, under a dark overlay. Photos
  zoom in and out very slowly; videos loop silently.
- the prayer in big uppercase letters, one line per screen. Each word blurs in
  as it is spoken, and each line blurs out before the next.
- words the user wraps in `*stars*` get the red accent tag (red text in Template 2)
- the verse reference and the "A" icon blur in at the start and out at the end
- optional calm voiceover (male or female) and optional soft piano-and-strings
  music, both made on the spot, with no API keys and nothing to license

The user writes everything themselves. **Never write, reword, shorten, correct
or add to their prayer or verse**, and never add "Amen" or a verse they didn't
give. The person using this is not technical: keep replies short and friendly,
and never ask them to run commands or install anything.

## 1. Start with the form

When the user asks for a reel or prayer video, or starts a chat about this
skill, show the template picture and the form before doing anything else:

1. Copy `assets/templates.png` (in this skill's folder) to
   `/mnt/user-data/outputs/aa-reels-templates.png` and share it with the
   file-sharing tool, so they can see Templates 1, 2 and 3.
2. Send this message as it is:

```
Let's make your prayer video! Copy this, fill it in, and attach your photo or video:

Template: 1 / 2 / 3
Music: On / Off
Voiceover: Yes / No
Voice: Male / Female
Text:
Psalm 85:6
Your faith may feel weak,
Lord, will You not *revive* us again
Amen.
Media Assets: Image / Video
```

3. Below it, add these tips in a short list:
   - Text: put the verse on the first line, then the prayer, **one line per screen**
     (about 3 to 8 words each).
   - Put `*stars*` around a word to highlight it in red, like `*revive*`.
   - A vertical (portrait) photo or video looks best.

If their first message already answers some of these, ask only for what's missing.

## 2. Read the answers

| Field | How to read it | If missing |
|---|---|---|
| Template | 1, 2 or 3 ("first", "T2" and so on are fine) | ask |
| Music | On / Off | On |
| Voiceover | Yes / No | Yes |
| Voice | Male / Female (ignored when Voiceover is No) | Female |
| Text | see below | ask |
| Media Assets | the attached file decides image or video | ask them to attach it |

**Text:**
- **First line = the verse reference** when it looks like one ("Psalm 85:6",
  "John 3:16-17", "1 Peter 5:7"). Use it exactly as typed. If there is no
  reference, ask once; if they don't want one, leave it empty.
- **Every other line is one screen**, word for word, keeping their spelling,
  capitals, punctuation and `*stars*`.
- Remove only things that aren't the prayer: hint text copied from the form
  (anything in brackets such as "(the verse, on the first line)" or "(one line
  per screen ...)"), empty lines, and bullet or number markers.
- If a line is longer than about 10 words, split it into two screens at a
  natural pause (comma, "and", "but"), without changing any words. If they
  pasted one paragraph, split it into screens the same way (sentences, then
  commas, about 4 to 9 words each). In both cases, show them the split.
- A `*` without its partner: ask which word they meant to highlight.

**Media:** the uploaded file is in `/mnt/user-data/uploads/`; list that folder
to find it. Pictures (jpg, png, webp, heic) and videos (mp4, mov, webm) both
work. Mention it in one line, without stopping, when:
- it's landscape: it will be cropped to the middle, so the edges are cut off
  and it looks softer;
- an image is under about 1000 px wide: it will look a little soft.

Then confirm in one line ("Template 1, music off, male voice, 3 screens, your
fog video: making it now") and go straight to step 3. Don't wait for approval.

## 3. Make the video

Write the answers to a spec file and run the script. Run it with a timeout of
at least 10 minutes, or in the background. The first video in a chat takes
about 2–3 minutes because of setup; later ones take about 1–2 minutes.

```bash
cat > /tmp/reel.json <<'EOF'
{
  "template": 1,
  "music": true,
  "voiceover": true,
  "voice": "male",
  "reference": "Psalm 85:6",
  "phrases": [
    "Your faith may feel weak,",
    "Lord, will You not *revive* us again",
    "Amen."
  ]
}
EOF
python3 <this skill's folder>/scripts/make_reel.py --spec /tmp/reel.json \
  --background "/mnt/user-data/uploads/<their file>"
```

The video is saved to `/mnt/user-data/outputs/aa-reel-<verse>-t<template>.mp4`.
Share it with the file-sharing tool and one line, such as "Here's your prayer
reel (Template 1, 18 s)". Then offer changes in one short line.

## 4. Changes

Change the spec and run the script again (about 1–2 minutes):

| They ask | Change |
|---|---|
| Another template | `"template"` |
| Music / voice on or off, male or female | `"music"`, `"voiceover"`, `"voice"` |
| Edit a line, or highlight a different word | `"phrases"`: use their wording exactly |
| Slower or faster voice | `"speed"`: default 0.76; 0.68 is slower, 0.85 is faster |
| Different music | `"seed"`: any other number gives a new melody in the same calm style |
| Music louder or softer | `"musicVolume"`: default 0.22 (0.1–0.35) |
| Darker or lighter background | `"overlay"`: default 0.48 (0.3–0.7) |
| More or less photo movement | `"zoom"`: default 1.08; 1 means no movement |
| Different background | run with the new `--background` file |

## If something fails

The script prints `[aa-reels] ERROR: ...` with the reason. Explain it plainly,
with the fix:

- **`VOICE_MODEL_BLOCKED`**: the voice model is downloaded from github.com, and
  that's blocked. Ask them to allow **github.com** under **Settings >
  Capabilities**, then start a new chat. Meanwhile, offer the video with
  Voiceover: No.
- **`BROWSER_BLOCKED`**: the video renderer couldn't be installed. Ask them to
  allow **registry.npmjs.org** under **Settings > Capabilities**, then start a
  new chat.
- **Node.js/npm missing**: the video can't be made in this environment. Say so
  plainly.
- **"Background file not found"**: list `/mnt/user-data/uploads/` and use the
  right file name.

Work files live in `~/aa-reels-work` (project, voice model, browser). Deleting
it is safe; the next run sets it up again.

## What's inside

- `scripts/make_reel.py`: the one command. It handles setup, voice, music,
  render and loudness (−14 LUFS, the level TikTok and Reels expect).
- `scripts/gen_voice.py`: the Kokoro voiceover and the timing of each word.
- `scripts/gen_music.py`: the calm music, made from scratch.
- `project/`: the Remotion video project. The layouts come from Figma "Universal
  Video Template" (AA Mobile App), in `project/src/pray/templates.ts`.
- `assets/templates.png`: the picture of Templates 1, 2 and 3 shown to the user.
