/**
 * The three layouts from Figma "Universal Video Template" (AA Mobile App,
 * section 9355:57450). Positions are on the 1080x1920 canvas.
 */
export type TemplateSpec = {
  /** Prayer text: size in px, and the vertical centre of the text block. */
  fontSize: number;
  textCenterY: number;
  /** Accent words: red rotated tag (1, 3) or red text (2). */
  accent: 'tag' | 'color';
  icon: { src: string; top: number };
  header:
    | { kind: 'caps'; top: number; size: number; lineHeight: number }
    | { kind: 'split'; top: number };
};

export const TEXT_WIDTH = 781;
export const TAG_RED = '#bf0d3d';
export const ACCENT_RED = '#e6184a'; // the red of the icon in template 2

export const TEMPLATES: Record<1 | 2 | 3, TemplateSpec> = {
  // Variant 1 (9355:57378): verse on top, text, white icon below.
  1: {
    fontSize: 164,
    textCenterY: 866,
    accent: 'tag',
    icon: { src: 'brand/icon-white.png', top: 1454 },
    header: { kind: 'caps', top: 294, size: 32, lineHeight: 44 },
  },
  // Variant 2 (9355:57451): red icon on top, larger text, small verse below.
  2: {
    fontSize: 200,
    textCenterY: 960,
    accent: 'color',
    icon: { src: 'brand/icon-red.png', top: 294 },
    header: { kind: 'caps', top: 1482, size: 24, lineHeight: 36 },
  },
  // Variant 3 (9355:57463): white icon on top, text, "Pray the scriptures" + verse below.
  3: {
    fontSize: 164,
    textCenterY: 960,
    accent: 'tag',
    icon: { src: 'brand/icon-white.png', top: 294 },
    header: { kind: 'split', top: 1478 },
  },
};
