import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';

// Families used in the Figma "Universal Video Template", bundled in public/fonts (OFL).
export const DISPLAY_FONT = 'Barlow Condensed';
export const BODY_FONT = 'Inter';

export const prayFontsReady = Promise.all([
  loadFont({ family: DISPLAY_FONT, url: staticFile('fonts/BarlowCondensed-SemiBold.woff2'), weight: '600' }),
  loadFont({ family: BODY_FONT, url: staticFile('fonts/Inter-Regular.woff2'), weight: '400' }),
  loadFont({ family: BODY_FONT, url: staticFile('fonts/Inter-SemiBold.woff2'), weight: '600' }),
]);
