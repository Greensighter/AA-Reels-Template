import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, Loop, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from 'remotion';

export type BackgroundItem = { src: string; video: boolean; frames?: number };

const CROSSFADE = 24; // frames (0.8 s) of soft dissolve between backgrounds
const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const easeInOut = Easing.inOut(Easing.sin);
const fill: React.CSSProperties = { width: '100%', height: '100%', objectFit: 'cover' };

/**
 * One or more backgrounds across the reel. `cuts` are the frames where the next
 * one takes over (length = items - 1). Each new background dissolves in over the
 * previous one.
 *
 * Image movement:
 * - a single image zooms in very slowly until the middle of the reel, then back out
 * - several images alternate: the first zooms in, the next zooms out, and so on
 * Videos play from their start in their slot and loop if the slot is longer.
 */
export const Backgrounds: React.FC<{
  items: BackgroundItem[];
  cuts: number[];
  durationInFrames: number;
  zoom: number;
}> = ({ items, cuts, durationInFrames, zoom }) => {
  if (!items.length) {
    // Placeholder in the Figma photo's misty blue-grey when no background is set.
    return <AbsoluteFill style={{ background: 'linear-gradient(#8f9a9a 0%, #5d6a72 35%, #2a3640 60%, #1a222a 100%)' }} />;
  }
  const bounds = [0, ...cuts, durationInFrames];
  return (
    <AbsoluteFill>
      {items.map((item, i) => {
        // Each slot starts half a crossfade early (except the first) and ends half a crossfade late.
        const from = i === 0 ? 0 : Math.max(0, bounds[i] - CROSSFADE / 2);
        const to = i === items.length - 1 ? durationInFrames : Math.min(durationInFrames, bounds[i + 1] + CROSSFADE / 2);
        return (
          <Sequence key={i} from={from} durationInFrames={Math.max(1, to - from)} layout="none">
            <Slot item={item} index={i} count={items.length} length={to - from} fadeIn={i > 0} zoom={zoom} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const Slot: React.FC<{ item: BackgroundItem; index: number; count: number; length: number; fadeIn: boolean; zoom: number }> = ({
  item,
  index,
  count,
  length,
  fadeIn,
  zoom,
}) => {
  const f = useCurrentFrame(); // relative to the slot's start
  const opacity = fadeIn ? easeInOut(interpolate(f, [0, CROSSFADE], [0, 1], clamp)) : 1;

  let content: React.ReactNode;
  if (item.video) {
    content = (
      <Loop durationInFrames={Math.max(1, item.frames ?? length)}>
        <OffthreadVideo src={staticFile(item.src)} muted style={fill} />
      </Loop>
    );
  } else {
    const x = f / Math.max(1, length - 1);
    // single: in then out (1 - cos); several: alternate in / out, eased at both ends.
    const amount = count === 1 ? (1 - Math.cos(2 * Math.PI * x)) / 2 : index % 2 === 0 ? easeInOut(x) : 1 - easeInOut(x);
    content = <Img src={staticFile(item.src)} style={{ ...fill, transform: `scale(${1 + (zoom - 1) * amount})` }} />;
  }
  return <AbsoluteFill style={{ opacity }}>{content}</AbsoluteFill>;
};

/**
 * Where to switch backgrounds. Splits the reel evenly, then moves each cut to
 * the nearest pause between lines (if one is close), so the picture changes
 * while no text is on screen.
 */
export function planCuts(count: number, durationInFrames: number, pauses: number[]): number[] {
  const cuts: number[] = [];
  const free = [...pauses];
  for (let k = 1; k < count; k++) {
    const ideal = (k * durationInFrames) / count;
    const slot = durationInFrames / count;
    let best = -1;
    free.forEach((p, i) => {
      if (Math.abs(p - ideal) <= slot * 0.45 && (best < 0 || Math.abs(p - ideal) < Math.abs(free[best] - ideal))) best = i;
    });
    const prev = cuts[cuts.length - 1] ?? 0;
    let cut = best >= 0 ? free.splice(best, 1)[0] : ideal;
    if (cut <= prev + 30) cut = Math.max(ideal, prev + 30); // keep slots at least 1 s apart
    cuts.push(Math.round(Math.min(cut, durationInFrames - 30)));
  }
  return cuts;
}
