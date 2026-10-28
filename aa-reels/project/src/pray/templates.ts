/**
 * Video templates. Both use the layout of Figma "Universal Template - Variant 1"
 * (AA Mobile App, node 9355:57378): verse on top, prayer in the middle, white
 * "A" icon below. Positions are on the 1080x1920 canvas.
 *
 * To add a template: add an entry here, add its number to the schema's max,
 * and describe it in SKILL.md and assets/templates.png.
 */
export type TemplateSpec = {
  /**
   * How the prayer appears:
   * - 'phrases': one line per screen, each word blurs in as it is spoken
   * - 'static': the whole prayer on one screen, still, sized to fit
   */
  mode: 'phrases' | 'static';
  /** Largest text size in px (the size is reduced to fit). */
  fontSize: number;
  /** 'phrases': vertical centre of the text. */
  textCenterY: number;
  /** 'static': the box the whole prayer must fit in (between header and icon). */
  textBox: { top: number; bottom: number };
  /** Accent words: red rotated tag, or red text. */
  accent: 'tag' | 'color';
  icon: { src: string; top: number };
  header:
    | { kind: 'caps'; top: number; size: number; lineHeight: number }
    | { kind: 'split'; top: number };
};

export const TEXT_WIDTH = 781;
export const TAG_RED = '#bf0d3d';
export const ACCENT_RED = '#e6184a';

const VARIANT_1 = {
  fontSize: 164,
  textCenterY: 866,
  // Header ends at 294 + 88 = 382; icon starts at 1454. 60 px breathing room each side.
  textBox: { top: 442, bottom: 1394 },
  accent: 'tag' as const,
  icon: { src: 'brand/icon-white.png', top: 1454 },
  header: { kind: 'caps' as const, top: 294, size: 32, lineHeight: 44 },
};

export const TEMPLATES: Record<number, TemplateSpec> = {
  // Template 1: one line per screen, word by word, synced to the voice.
  1: { mode: 'phrases', ...VARIANT_1 },
  // Template 2: the whole prayer at once, still, as large as fits (max = template 1 size).
  2: { mode: 'static', ...VARIANT_1 },
};

export const TEMPLATE_COUNT = Object.keys(TEMPLATES).length;
