import React, { useMemo } from 'react';
import { Easing, interpolate } from 'remotion';
import { measureText } from '@remotion/layout-utils';
import { DISPLAY_FONT } from './fonts';
import { ACCENT_RED, TAG_RED, TEXT_WIDTH, type TemplateSpec } from './templates';
import { WORD_BLUR, WORD_IN } from './timing';
import type { PhraseTiming } from './schema';

// From Figma: Barlow Condensed SemiBold, uppercase, line-height 0.8, tracking -3%.
const LINE = 0.8;
const TRACKING_EM = -0.03;
const MAX_LINES = 4;
const MIN_SIZE = 90;
// Tag: red pill, 24 px radius, 24/16 px padding, rotated -7.48 deg, on its own line.
const TAG_ROTATE = -7.48;
const TAG_PAD_X = 24;
const TAG_PAD_Y = 16;
const TAG_SLOT = 0.99; // height of the tag's line, in em (Figma: tag top to text top = 163 px at 164 px)
const TAG_DROP = 0.14; // tag sits lower than its slot, overlapping the next line (Figma: ~46 px)

type Word = { text: string; index: number };
type Line = { accent: boolean; words: Word[] };

const easeOut = Easing.out(Easing.cubic);
const pop = Easing.bezier(0.34, 1.4, 0.64, 1);

function width(text: string, size: number): number {
  return measureText({
    text: text.toUpperCase(),
    fontFamily: DISPLAY_FONT,
    fontSize: size,
    fontWeight: '600',
    letterSpacing: `${TRACKING_EM * size}px`,
  }).width;
}

/** Wraps words into lines. With tags, each run of accent words gets a line of its own. */
function wrap(phrase: PhraseTiming, size: number, tags: boolean): Line[] | null {
  const space = width(' ', size);
  const lines: Line[] = [];
  let cur: Line | null = null;
  let curW = 0;
  phrase.words.forEach((w, index) => {
    const isTag = tags && !!w.accent;
    const ww = width(w.text, size) + (isTag ? TAG_PAD_X * 2 : 0);
    if (ww > TEXT_WIDTH) throw new Error('too wide');
    const sameKind = cur && cur.accent === isTag;
    const next = sameKind && cur!.words.length ? curW + space + ww : ww;
    if (!cur || !sameKind || next > TEXT_WIDTH) {
      cur = { accent: isTag, words: [] };
      lines.push(cur);
      curW = ww;
    } else {
      curW = next;
    }
    cur.words.push({ text: w.text, index });
  });
  return lines;
}

function fit(phrase: PhraseTiming, base: number, tags: boolean): { size: number; lines: Line[] } {
  for (let size = base; size >= MIN_SIZE; size -= 4) {
    try {
      const lines = wrap(phrase, size, tags);
      const height = lines!.reduce((h, l) => h + (l.accent ? TAG_SLOT : LINE), 0);
      if (lines && height <= MAX_LINES * LINE + 0.3) return { size, lines };
    } catch {
      /* a word is too wide at this size: try smaller */
    }
  }
  return { size: MIN_SIZE, lines: wrap(phrase, MIN_SIZE, false) ?? [] };
}

/** 0 -> 1 entrance progress for something that starts at `start`. */
const enter = (t: number, start: number, dur = WORD_IN) =>
  interpolate(t, [start, start + dur], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

export const PhraseText: React.FC<{
  phrase: PhraseTiming;
  spec: TemplateSpec;
  /** Current time in seconds. */
  t: number;
  /** 0 = fully shown, 1 = fully gone (the phrase's blur-out). */
  out: number;
}> = ({ phrase, spec, t, out }) => {
  const tags = spec.accent === 'tag';
  const { size, lines } = useMemo(() => fit(phrase, spec.fontSize, tags), [phrase, spec.fontSize, tags]);

  const outE = easeOut(out);
  return (
    <div
      style={{
        position: 'absolute',
        left: '50%',
        top: spec.textCenterY,
        width: TEXT_WIDTH,
        transform: `translate(-50%, -50%) translateY(${-14 * outE}px)`,
        opacity: 1 - outE,
        filter: outE > 0 ? `blur(${WORD_BLUR * outE}px)` : undefined,
        fontFamily: DISPLAY_FONT,
        fontWeight: 600,
        fontSize: size,
        letterSpacing: `${TRACKING_EM}em`,
        lineHeight: LINE,
        textTransform: 'uppercase',
        color: '#ffffff',
        textAlign: 'center',
      }}
    >
      {lines.map((line, li) =>
        line.accent ? (
          <Tag key={li} line={line} phrase={phrase} t={t} size={size} />
        ) : (
          <div key={li} style={{ whiteSpace: 'nowrap', height: size * LINE }}>
            {line.words.map(({ text, index }, wi) => {
              const p = easeOut(enter(t, phrase.words[index].start));
              const accent = !tags && phrase.words[index].accent;
              return (
                <React.Fragment key={index}>
                  {wi > 0 ? ' ' : null}
                  <span
                    style={{
                      display: 'inline-block',
                      opacity: p,
                      filter: p < 1 ? `blur(${WORD_BLUR * (1 - p)}px)` : undefined,
                      transform: `translateY(${(1 - p) * 18}px)`,
                      color: accent ? ACCENT_RED : undefined,
                    }}
                  >
                    {text}
                  </span>
                </React.Fragment>
              );
            })}
          </div>
        ),
      )}
    </div>
  );
};

/** Tag wording: the accent words without trailing punctuation (the tag never ends in a comma). */
const tagText = (line: Line) => line.words.map((w) => w.text).join(' ').replace(/[,.;:!?]+$/, '');

/** A run of accent words in the red rotated tag. It pops in with the first word. */
const Tag: React.FC<{ line: Line; phrase: PhraseTiming; t: number; size: number }> = ({ line, phrase, t, size }) => {
  const start = phrase.words[line.words[0].index].start;
  const p = enter(t, start, WORD_IN + 0.1);
  const e = easeOut(p);
  const scale = interpolate(pop(p), [0, 1], [0.82, 1]);
  const rotate = interpolate(e, [0, 1], [TAG_ROTATE + 6, TAG_ROTATE]);
  return (
    <div style={{ height: size * TAG_SLOT, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <div
        style={{
          display: 'inline-flex',
          background: TAG_RED,
          borderRadius: 24,
          padding: `${TAG_PAD_Y}px ${TAG_PAD_X}px`,
          whiteSpace: 'nowrap',
          opacity: e,
          filter: p < 1 ? `blur(${WORD_BLUR * (1 - e)}px)` : undefined,
          transform: `translateY(${size * TAG_DROP}px) rotate(${rotate}deg) scale(${scale})`,
          position: 'relative',
          zIndex: 1,
        }}
      >
        <span
          style={{
            // Trim the line box to the capitals, like Figma's "text-box-trim: cap".
            textBoxTrim: 'trim-both',
            textBoxEdge: 'cap alphabetic',
            lineHeight: LINE,
          } as React.CSSProperties}
        >
          {tagText(line)}
        </span>
      </div>
    </div>
  );
};
