import React, { useEffect, useState } from 'react';
import {
  AbsoluteFill,
  Audio,
  continueRender,
  delayRender,
  Easing,
  getStaticFiles,
  Img,
  interpolate,
  Loop,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { BODY_FONT, prayFontsReady } from './fonts';
import { PhraseText } from './PhraseText';
import { TEMPLATES, type TemplateSpec } from './templates';
import { CHROME_IN, CHROME_OUT, PHRASE_OUT, WORD_BLUR, WORD_IN } from './timing';
import { VOICE_FILE, type PrayProps, type VoiceTiming } from './schema';

export type PrayInternalProps = PrayProps & { timing?: VoiceTiming; hasVoice?: boolean; videoFrames?: number };

const hasFile = (p?: string) => !!p && getStaticFiles().some((f) => f.name === p);
export const isVideo = (p: string) => /\.(mp4|mov|m4v|webm|mkv)$/i.test(p);

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const easeOut = Easing.out(Easing.cubic);

/** Blur + fade style for header/icon: in at the start, out at the end. */
function chromeStyle(t: number, total: number): React.CSSProperties {
  const inP = easeOut(interpolate(t, [0.1, 0.1 + CHROME_IN], [0, 1], clamp));
  const outP = easeOut(interpolate(t, [total - CHROME_OUT - 0.15, total - 0.15], [0, 1], clamp));
  const v = inP * (1 - outP);
  return { opacity: v, filter: v < 1 ? `blur(${(WORD_BLUR * 0.75) * (1 - v)}px)` : undefined };
}

export const PrayScripture: React.FC<PrayInternalProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  const total = durationInFrames / fps;
  const spec = TEMPLATES[(props.template as 1 | 2 | 3) ?? 1] ?? TEMPLATES[1];

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
  const idx = phrases.reduce((found, p, i) => (t >= p.start - 0.05 ? i : found), -1);
  const current = idx >= 0 ? phrases[idx] : null;

  // Each phrase blurs out just before the next starts; the last one goes out with the header and icon.
  let out = 0;
  if (current) {
    const lastWordStart = current.words[current.words.length - 1]?.start ?? current.start;
    const next = phrases[idx + 1];
    const outEnd = next ? next.start - 0.08 : total - 0.15;
    const outLen = next ? PHRASE_OUT : CHROME_OUT;
    const outStart = Math.max(outEnd - outLen, lastWordStart + WORD_IN);
    out = interpolate(t, [outStart, Math.max(outEnd, outStart + 0.01)], [0, 1], clamp);
  }

  // Images breathe: a very slow zoom in to `zoom` at the middle of the reel, then back out.
  // (1 - cos) starts and ends with zero speed, so there is no jolt at either end.
  // Videos already move, so they stay at 100%.
  const breathe = (1 - Math.cos((2 * Math.PI * frame) / Math.max(1, durationInFrames - 1))) / 2;
  const zoom = 1 + (props.zoom - 1) * breathe;
  const bg = hasFile(props.background) ? props.background : null;
  const chrome = chromeStyle(t, total);

  return (
    <AbsoluteFill style={{ backgroundColor: '#1b2128' }}>
      {bg && isVideo(bg) ? (
        // Uploaded clips loop silently for the whole reel, cropped to fill 9:16.
        <Loop durationInFrames={Math.max(1, props.videoFrames ?? durationInFrames)}>
          <OffthreadVideo src={staticFile(bg)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </Loop>
      ) : bg ? (
        <Img src={staticFile(bg)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${zoom})` }} />
      ) : (
        // Placeholder in the Figma photo's misty blue-grey when no background is set.
        <AbsoluteFill style={{ background: 'linear-gradient(#8f9a9a 0%, #5d6a72 35%, #2a3640 60%, #1a222a 100%)' }} />
      )}
      <AbsoluteFill style={{ backgroundColor: `rgba(22,22,22,${props.overlay})` }} />

      <Header spec={spec} reference={props.reference} label={props.label} style={chrome} />
      <Img
        src={staticFile(spec.icon.src)}
        style={{ position: 'absolute', left: 505, top: spec.icon.top, width: 70, height: 100, ...chrome }}
      />

      {ready && current ? <PhraseText key={idx} phrase={current} spec={spec} t={t} out={out} /> : null}

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
      {reference ? (
        <div style={{ fontWeight: 600, fontSize: 32, lineHeight: '44px', color: 'rgba(255,255,255,0.92)' }}>{reference}</div>
      ) : null}
    </div>
  );
};
