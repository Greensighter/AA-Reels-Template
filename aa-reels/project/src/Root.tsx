import React from 'react';
import { CalculateMetadataFunction, Composition, getStaticFiles, staticFile } from 'remotion';
import { getVideoMetadata } from '@remotion/media-utils';
import { isVideo, PrayScripture, PrayInternalProps } from './pray/PrayScripture';
import { praySchema, TIMING_FILE, VOICE_FILE, type PrayProps, type VoiceTiming } from './pray/schema';
import { timingMatches, timingWithoutVoice } from './pray/timing';

const FPS = 30;

// Only used when the project is opened without --props (e.g. in Remotion Studio).
const sample: PrayProps = {
  template: 1,
  reference: 'Psalm 85:6',
  label: 'Pray the scriptures',
  phrases: ['Your faith may feel weak,', 'Lord, *revive* us again,', 'Amen.'],
  background: 'media/background.jpg',
  overlay: 0.48,
  zoom: 1.08,
  voice: { name: 'af_heart', speed: 0.76, leadInSeconds: 1.0, gapSeconds: 1.2, tailSeconds: 2.2 },
  music: 'audio/pray/music.wav',
  musicVolume: 0.22,
};

/**
 * Uses the voiceover's word timings when they were generated from these exact
 * phrases; otherwise words follow a calm reading pace with no voice.
 */
const calculatePrayMetadata: CalculateMetadataFunction<PrayInternalProps> = async ({ props }) => {
  const files = getStaticFiles().map((f) => f.name);
  let timing: VoiceTiming | undefined;
  if (files.includes(TIMING_FILE) && files.includes(VOICE_FILE)) {
    const loaded: VoiceTiming = await fetch(staticFile(TIMING_FILE)).then((r) => r.json());
    if (timingMatches(loaded, props)) timing = loaded;
  }
  const hasVoice = !!timing;
  timing = timing ?? timingWithoutVoice(props);
  let videoFrames: number | undefined;
  if (files.includes(props.background) && isVideo(props.background)) {
    const meta = await getVideoMetadata(staticFile(props.background));
    videoFrames = Math.floor(meta.durationInSeconds * FPS);
  }
  return {
    durationInFrames: Math.ceil(timing.durationSeconds * FPS),
    props: { ...props, timing, hasVoice, videoFrames },
  };
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="PrayScripture"
    component={PrayScripture}
    schema={praySchema}
    defaultProps={sample as PrayInternalProps}
    calculateMetadata={calculatePrayMetadata}
    durationInFrames={FPS * 25}
    fps={FPS}
    width={1080}
    height={1920}
  />
);
