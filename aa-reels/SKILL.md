---
name: aa-reels
description: Makes Awake America prayer reels (9:16 videos for TikTok, Reels, Shorts) from the user's own prayer text and photos or videos, in templates 1-2, with optional voiceover and music.
---

# AA Reels

Makes a finished 1080×1920 MP4 in the Awake America "Pray the Scriptures"
style, from the user's answers to a short form. Both templates share the same
look: the verse at the top, the prayer in big uppercase letters in the middle,
and the white "A" icon below, over the user's photos or videos with a dark
overlay. The picture `assets/templates.png` shows both.

- **Template 1, line by line:** one line of the prayer per screen. Each word
  blurs in as it is spoken, and each line blurs out before the next.
- **Template 2, whole prayer at once:** the full prayer stays on screen, still,
  while it is read. The text size adjusts automatically to fit: up to the same
  size as Template 1 for a short prayer, smaller for a long one.
- Words the user wraps in `*stars*` get the red accent tag. If they mark none,
  you choose the key word(s).
- Full stops are hidden on screen (other punctuation stays).
- The verse and the "A" icon blur in at the start and out at the end.
- **Backgrounds:** every attached photo and video is used, in order, taking
  turns with a soft dissolve. In Template 1 the change happens in a pause
  between lines. Photos zoom in and out very slowly; videos play muted and loop
  if needed.
- Optional calm voiceover (male or female) and optional soft piano-and-strings
  music, both made on the spot, with no API keys and nothing to license.

The user writes everything themselves. **Never write, reword, shorten, correct
or add to their prayer or verse**, and never add "Amen" or a verse they didn't
give. The person using this is not technical: keep replies short and friendly,
and never ask them to run commands or install anything.

## 1. Start with the form

When the user asks for a reel or prayer video, or starts a chat about this
skill, show the template picture and the form before doing anything else:

1. Copy `assets/templates.png` (in this skill's folder) to
   `/mnt/user-data/outputs/aa-reels-templates.png` and share it with the
   file-sharing tool.
2. Send this message as it is:

```
Let's make your prayer video! Copy this, fill it in, and attach your photos or videos:

Template: 1 / 2
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
   - Template 1 shows the prayer line by line; Template 2 shows it all at once.
   - Text: put the verse on the first line, then the prayer. In Template 1,
     **each line is one screen** (3 to 8 words looks best); long lines are split
     automatically.
   - Put `*stars*` around a word to highlight it in red, like `*revive*`.
   - You can attach **several photos or videos**: they'll take turns in the
     video. Vertical (portrait) ones look best.

If their first message already answers some of these, ask only for what's missing.

## 2. Read the answers

| Field | How to read it | If missing |
|---|---|---|
| Template | 1 or 2 ("first", "T2" and so on are fine). If they ask for 3 or more: only 1 and 2 exist for now | ask |
| Music | On / Off | On |
| Voiceover | Yes / No | Yes |
| Voice | Male / Female (ignored when Voiceover is No) | Female |
| Text | see below | ask |
| Media Assets | every attached photo/video, in the order attached | ask them to attach at least one |

**Text:**
- **First line = the verse reference** when it looks like one ("Psalm 85:6",
  "John 3:16-17", "1 Peter 5:7"). Use it exactly as typed. If there is no
  reference, ask once; if they don't want one, leave it empty.
- **A reference elsewhere in the text** (for example "— Matthew 19:14" under a
  quote, or "(John 3:16)" at the end) is the verse reference: use it for the
  top and drop that line from `phrases`, so it isn't shown or read aloud as a
  screen. Tell the user in one line. If there are several, use the first and
  leave the others in the text.
- **Every other line goes into `phrases`** word for word, keeping their
  spelling, capitals, punctuation and `*stars*`. One entry per line they typed;
  a prayer written on a single line is one entry.
- Remove only things that aren't the prayer: hint text copied from the form
  (anything in brackets such as "(the verse, on the first line)"), empty lines,
  and bullet or number markers.
- **Don't split lines yourself.** In Template 1 the script splits any line
  longer than 9 words into screens, at sentence ends first, then at commas,
  then evenly. It never changes words and never cuts a `*starred*` phrase. It
  prints the split, so show it to the user in a short list after the video.
- A `*` without its partner: ask which word they meant to highlight.
- **Full stops:** leave them in `phrases`. The video hides every "." on screen
  automatically, and the voice uses them to pause naturally between sentences.
- **If there are no `*stars*` anywhere, choose the highlights yourself**: the
  word (or two-word phrase) that carries the message, the one a preacher would
  stress. Use one highlight for a short prayer (up to about 5 screens) and 2–3
  for a longer one, never more than one per screen, spread out, with the
  strongest near the end. Prefer meaningful nouns and verbs ("*prayer*",
  "*revive*", "*upside down*", "*peace*"). Avoid names of address ("Lord",
  "God", "Jesus" at the start of a line), small words, and "Amen". Add the stars
  around the existing word, without changing it, and tell the user in one line
  which words you highlighted. (If none get through, the script highlights one
  word as a safety net; your choice is better.)

**Media:** uploaded files are in `/mnt/user-data/uploads/`; list that folder
to find them. Pass **all** of them to `--background`, in the order the user
attached them, or the order they asked for. Photos (jpg, png, webp, heic) and
videos (mp4, mov, webm) can be mixed; up to 10 are used. Mention it in one
line, without stopping, when:
- a file is landscape: it will be cropped to the middle, so the edges are cut
  off and it looks softer;
- a photo is under about 1000 px wide: it will look a little soft;
- there are many files for a short prayer: each gets only a few seconds.

Then confirm in one line ("Template 1, music on, female voice, 2 photos,
highlighting *prayer* and *upside down*: making it now") and go straight to
step 3. Don't wait for approval.

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
  "voice": "female",
  "reference": "Psalm 85:6",
  "phrases": [
    "Your faith may feel weak,",
    "Lord, will You not *revive* us again",
    "Amen."
  ]
}
EOF
python3 <this skill's folder>/scripts/make_reel.py --spec /tmp/reel.json \
  --background "/mnt/user-data/uploads/<file 1>" "/mnt/user-data/uploads/<file 2>"
```

The video is saved to `/mnt/user-data/outputs/aa-reel-<verse>-t<template>.mp4`.
Share it with the file-sharing tool and one line, such as "Here's your prayer
reel (Template 1, 18 s)". If the script split long lines, list the screens
briefly. Then offer changes in one short line.

## 4. Changes

Change the spec and run the script again (about 1–2 minutes):

| They ask | Change |
|---|---|
| The other template | `"template"`: 1 or 2 |
| Music / voice on or off, male or female | `"music"`, `"voiceover"`, `"voice"` |
| Edit a line, or highlight a different word | `"phrases"`: use their wording exactly |
| No highlights at all | remove the stars and add `"autoHighlight": false` |
| Different screen breaks (Template 1) | put each screen as its own entry in `"phrases"`, as they want it |
| Slower or faster voice | `"speed"`: default 0.76; 0.68 is slower, 0.85 is faster |
| Different music | `"seed"`: any other number gives a new melody in the same calm style |
| Music louder or softer | `"musicVolume"`: default 0.22 (0.1–0.35) |
| Darker or lighter background | `"overlay"`: default 0.48 (0.3–0.7) |
| More or less photo movement | `"zoom"`: default 1.08; 1 means no movement |
| Different backgrounds or order | run with the new `--background` files, in the new order |

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
  right file names.

Work files live in `~/aa-reels-work` (project, voice model, browser). Deleting
it is safe; the next run sets it up again.

## What's inside

- `scripts/make_reel.py`: the one command. It handles setup, line splitting,
  voice, music, render and loudness (−14 LUFS, the level TikTok and Reels
  expect).
- `scripts/gen_voice.py`: the Kokoro voiceover and the timing of each word.
- `scripts/gen_music.py`: the calm music, made from scratch.
- `project/`: the Remotion video project. The templates are in
  `project/src/pray/templates.ts` (layout from Figma "Universal Template -
  Variant 1", AA Mobile App).
- `assets/templates.png`: the picture of Templates 1 and 2 shown to the user.
