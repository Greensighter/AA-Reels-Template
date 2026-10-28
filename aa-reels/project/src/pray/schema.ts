import { z } from 'zod';

/**
 * Props for the prayer reel (Figma "Universal Video Template", variants 1-3).
 * Written to pray.json by scripts/make_reel.py.
 */
export const praySchema = z.object({
  /** Layout: 1 = verse on top, icon below; 2 = big text, no tag; 3 = icon on top, verse below. */
  template: z.number().int().min(1).max(3),
  /** Verse reference as the user typed it, e.g. "Psalm 85:6". */
  reference: z.string(),
  /** Small line paired with the reference. */
  label: z.string(),
  /**
   * One phrase per screen. Words wrapped in *stars* are accent words: a red tag
   * in templates 1 and 3, red text in template 2.
   */
  phrases: z.array(z.string()).min(1),
  /** Background photo or video in public/. Videos loop, muted, cropped to 9:16. */
  background: z.string(),
  /** Dark overlay on the background, 0-1. Figma uses 0.48. */
  overlay: z.number().min(0).max(1),
  /** Image backgrounds only: peak of the slow zoom in/out (reached mid-reel). 1 = still image. */
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
