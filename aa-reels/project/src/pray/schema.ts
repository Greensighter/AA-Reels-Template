import { z } from 'zod';

/**
 * Props for the prayer reel (templates in templates.ts).
 * Written to pray.json by scripts/make_reel.py.
 */
export const praySchema = z.object({
  /** 1 = one line per screen, word by word; 2 = the whole prayer at once, still. */
  template: z.number().int().min(1).max(2),
  /** Verse reference as the user typed it, e.g. "Psalm 85:6". */
  reference: z.string(),
  /** Small line paired with the reference. */
  label: z.string(),
  /**
   * The prayer, one line per screen in template 1. Words wrapped in *stars*
   * are accent words (the red tag).
   */
  phrases: z.array(z.string()).min(1),
  /**
   * Photos and/or videos in public/, used in this order. Several files take turns
   * with a soft crossfade. Videos are muted and loop within their turn.
   */
  backgrounds: z.array(z.string()),
  /** Dark overlay on the background, 0-1. Figma uses 0.48. */
  overlay: z.number().min(0).max(1),
  /** Photos only: how far the slow zoom goes (1.08 = 108%). 1 = still photo. */
  zoom: z.number().min(1).max(1.3),
  /** Voice settings, read by scripts/gen_voice.py. */
  voice: z.object({
    name: z.string(),
    speed: z.number(),
    leadInSeconds: z.number(),
    gapSeconds: z.number(),
    tailSeconds: z.number(),
  }),
  /** Music bed in public/. */
  music: z.string().optional(),
  musicVolume: z.number().min(0).max(1),
});

export type PrayProps = z.infer<typeof praySchema>;

export type WordTiming = { text: string; start: number; end: number; accent?: boolean };
export type PhraseTiming = { text: string; start: number; end: number; words: WordTiming[] };
export type VoiceTiming = { durationSeconds: number; phrases: PhraseTiming[] };

export const TIMING_FILE = 'audio/pray/timing.json';
export const VOICE_FILE = 'audio/pray/voice.wav';
