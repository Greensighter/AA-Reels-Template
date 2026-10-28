import type { PhraseTiming, PrayProps, VoiceTiming } from './schema';

// ---- Motion (seconds). Shared by every template.
export const WORD_IN = 0.45; // each word blurs in as it is spoken
export const WORD_BLUR = 16; // px of blur at the start of a word's entrance
export const PHRASE_OUT = 0.45; // a phrase blurs out before the next one
export const CHROME_IN = 0.8; // header + icon at the start
export const CHROME_OUT = 0.7; // header + icon + last phrase at the end

/**
 * Splits a phrase into words and marks accent words. Accent words are wrapped
 * in *stars*: "Lord, *revive* us again" or "*new life*". Must match
 * parse_phrase() in scripts/gen_voice.py.
 */
export function parsePhrase(phrase: string): { text: string; accent: boolean }[] {
  const out: { text: string; accent: boolean }[] = [];
  let inside = false;
  for (const token of phrase.split(/\s+/).filter(Boolean)) {
    const starts = token.startsWith('*');
    const ends = token.replace(/[,.;:!?"')\]]+$/, '').endsWith('*') && !(starts && token.length === 1);
    const clean = token.replace(/\*/g, '');
    if (clean) out.push({ text: clean, accent: inside || starts });
    if (starts) inside = true;
    if (ends) inside = false;
  }
  return out;
}

/** The text that is spoken: the phrase without accent markers. */
export const spokenText = (phrase: string) => phrase.replace(/\*/g, '');

/**
 * Without a voiceover, words follow a calm reading pace and each phrase stays
 * up long enough to read (about 2.5 words per second, at least 2.4 seconds).
 */
export function timingWithoutVoice(props: PrayProps): VoiceTiming {
  const { leadInSeconds, tailSeconds } = props.voice;
  const step = 0.22;
  const gap = 0.7;
  let t = leadInSeconds;
  const phrases: PhraseTiming[] = props.phrases.map((text) => {
    const words = parsePhrase(text);
    const hold = Math.max(2.4, words.length * 0.42 + 0.8);
    const p: PhraseTiming = {
      text,
      start: t,
      end: t + hold,
      words: words.map((w, i) => ({ ...w, start: t + i * step, end: t + (i + 1) * step })),
    };
    t += hold + gap;
    return p;
  });
  return { durationSeconds: t - gap + tailSeconds, phrases };
}

/** The voice timing only applies if it was generated from these exact phrases. */
export function timingMatches(timing: VoiceTiming, props: PrayProps): boolean {
  return (
    timing.phrases.length === props.phrases.length &&
    timing.phrases.every((p, i) => p.text.trim() === props.phrases[i].trim())
  );
}
