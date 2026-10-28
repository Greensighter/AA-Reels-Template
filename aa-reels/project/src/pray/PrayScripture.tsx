import React, { useEffect, useMemo, useState } from 'react';
import {
  AbsoluteFill,
  Audio,
  continueRender,
  delayRender,
  Easing,
  getStaticFiles,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { Backgrounds, planCuts, type BackgroundItem } from './Backgrounds';
import { BODY_FONT, prayFontsReady } from './fonts';
import { TextBlock, useFit } from './PhraseText';
import { TEMPLATES, type TemplateSpec } from './templates';
import { CHROME_IN, CHROME_OUT, PHRASE_OUT, WORD_BLUR, WORD_IN } from './timing';
import { VOICE_FILE, type PhraseTiming, type PrayProps, type VoiceTiming } from './schema';

export type PrayInternalProps = PrayProps & {
  timing?: VoiceTiming;
  hasVoice?: boolean;
  /** Length in frames of each video background (same order as `backgrounds`). */
  videoFrames?: (number | null)[];
};

const hasFile = (p?: string) => !!p && getStaticFiles().some((f) => f.name === p);
export const isVideo = (p: string) => /\.(mp4|mov|m4v|webm|mkv)$/i.test(p);

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

/**
 * Words as shown on screen: full stops are removed ("WEAK." -> "WEAK"). The
 * voice still reads the original text, so sentence endings keep their pause.
 */
const forScreen = (words: PhraseTiming['words']) =>
  words.map((w) => ({ ...w, text: w.text.replace(/\./g, '') })).filter((w) => w.text.length > 0);
const easeOut = Easing.out(Easing.cubic);
const CHROME_START = 0.1;

/** Header + icon: blur in at the start, blur out at the end. Returns 0..1 visibility. */
function chromeVisibility(t: number, total: number): number {
  const inP = easeOut(interpolate(t, [CHROME_START, CHROME_START + CHROME_IN], [0, 1], clamp));
  const outP = easeOut(interpolate(t, [total - CHROME_OUT - 0.15, total - 0.15], [0, 1], clamp));
  return inP * (1 - outP);
}

export const PrayScripture: React.FC<PrayInternalProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  const total = durationInFrames / fps;
  const spec = TEMPLATES[props.template] ?? TEMPLATES[1];

  // Text layout measures the real font, so wait for it before the first frame.
  const [handle] = useState(() => delayRender('Loading fonts'));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    prayFontsReady.then(() => {
      setReady(true);
      continueRender(handle);
    });
  }, [handle]);

  const phrases = props.timing?.phrases ?? [];

  // Backgrounds: every attached file, switching during pauses between lines where possible.
  const items: BackgroundItem[] = props.backgrounds
    .map((src, i) => ({ src, video: isVideo(src), frames: props.videoFrames?.[i] ?? undefined }))
    .filter((it) => hasFile(it.src));
  const cuts = useMemo(() => {
    const pauses =
      spec.mode === 'phrases'
        ? phrases.slice(0, -1).map((p, i) => Math.round(((p.end + phrases[i + 1].start) / 2) * fps))
        : [];
    return planCuts(items.length, durationInFrames, pauses);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length, durationInFrames, spec.mode, props.timing]);

  // Template 2 is fully still: header and icon are on screen from the first frame.
  const v = spec.mode === 'static' ? 1 : chromeVisibility(t, total);
  const chrome: React.CSSProperties = { opacity: v, filter: v < 1 ? `blur(${WORD_BLUR * 0.75 * (1 - v)}px)` : undefined };

  return (
    <AbsoluteFill style={{ backgroundColor: '#1b2128' }}>
      <Backgrounds items={items} cuts={cuts} durationInFrames={durationInFrames} zoom={props.zoom} />
      <AbsoluteFill style={{ backgroundColor: `rgba(22,22,22,${props.overlay})` }} />

      <Header spec={spec} reference={props.reference} label={props.label} style={chrome} />
      <Img src={staticFile(spec.icon.src)} style={{ position: 'absolute', left: 505, top: spec.icon.top, width: 70, height: 100, ...chrome }} />

      {ready ? (
        spec.mode === 'static' ? (
          <StaticPrayer phrases={phrases} spec={spec} t={t} total={total} />
        ) : (
          <PhrasePrayer phrases={phrases} spec={spec} t={t} total={total} />
        )
      ) : null}

      {props.hasVoice ? <Audio src={staticFile(VOICE_FILE)} /> : null}
      {hasFile(props.music) ? (
        <Audio
          src={staticFile(props.music!)}
          volume={(f) => props.musicVolume * interpolate(f, [durationInFrames - fps * 2, durationInFrames], [1, 0], clamp)}
        />
      ) : null}
    </AbsoluteFill>
  );
};

/** Template 1: one line per screen; words blur in as spoken; each line blurs out before the next. */
const PhrasePrayer: React.FC<{ phrases: PhraseTiming[]; spec: TemplateSpec; t: number; total: number }> = ({
  phrases,
  spec,
  t,
  total,
}) => {
  const idx = phrases.reduce((found, p, i) => (t >= p.start - 0.05 ? i : found), -1);
  const current = idx >= 0 ? phrases[idx] : null;
  const words = useMemo(() => forScreen(current?.words ?? []), [current]);
  const layout = useFit(words, { max: spec.fontSize, min: 90, tags: spec.accent === 'tag', maxLines: 4 });
  if (!current) return null;

  const lastWordStart = current.words[current.words.length - 1]?.start ?? current.start;
  const next = phrases[idx + 1];
  const outEnd = next ? next.start - 0.08 : total - 0.15;
  const outLen = next ? PHRASE_OUT : CHROME_OUT;
  const outStart = Math.max(outEnd - outLen, lastWordStart + WORD_IN);
  const out = interpolate(t, [outStart, Math.max(outEnd, outStart + 0.01)], [0, 1], clamp);

  return <TextBlock key={idx} words={words} layout={layout} centerY={spec.textCenterY} accent={spec.accent} t={t} out={out} />;
};

/**
 * Template 2: the whole prayer on one screen, completely still. No appearing or
 * leaving animation, and no highlighted words (any *stars* are shown as plain text).
 * The size is the largest (up to the template's max) that fits between the
 * header and the icon.
 */
const StaticPrayer: React.FC<{ phrases: PhraseTiming[]; spec: TemplateSpec; t: number; total: number }> = ({
  phrases,
  spec,
  t,
}) => {
  const words = useMemo(
    () => forScreen(phrases.flatMap((p) => p.words)).map((w) => ({ ...w, accent: false, start: -10 })),
    [phrases],
  );
  const box = spec.textBox;
  const layout = useFit(words, { max: spec.fontSize, min: 40, tags: false, maxHeightPx: box.bottom - box.top });
  return (
    <TextBlock
      words={words}
      layout={layout}
      centerY={(box.top + box.bottom) / 2}
      accent={spec.accent}
      t={t}
      out={0}
      inDuration={0.01}
    />
  );
};

const Header: React.FC<{ spec: TemplateSpec; reference: string; label: string; style: React.CSSProperties }> = ({
  spec,
  reference,
  label,
  style,
}) => {
  const h = spec.header;
  const base: React.CSSProperties = {
    position: 'absolute',
    top: h.top,
    left: '50%',
    transform: 'translateX(-50%)',
    fontFamily: BODY_FONT,
    textAlign: 'center',
    whiteSpace: 'nowrap',
    color: '#eff3fd',
    ...style,
  };
  if (h.kind === 'caps') {
    return (
      <div style={{ ...base, fontWeight: 600, fontSize: h.size, lineHeight: `${h.lineHeight}px`, textTransform: 'uppercase' }}>
        <div>{label}</div>
        {reference ? <div>{reference}</div> : null}
      </div>
    );
  }
  return (
    <div style={{ ...base, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontWeight: 400, fontSize: 24, lineHeight: '36px' }}>{label}</div>
      {reference ? <div style={{ fontWeight: 600, fontSize: 32, lineHeight: '44px', color: 'rgba(255,255,255,0.92)' }}>{reference}</div> : null}
    </div>
  );
};
