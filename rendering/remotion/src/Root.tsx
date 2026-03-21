import { Composition } from "remotion";
import { DevotionalReel } from "./DevotionalReel";
import type { ReelProps } from "./types";

const FPS = 30;

const defaultProps: ReelProps = {
  imageSrc: "placeholder.jpg",
  audioSrc: "placeholder.mp3",
  words: [],
  verseReference: "Psalm 46:10 NIV",
  durationInSeconds: 15,
};

export const RemotionRoot = () => {
  return (
    <Composition
      id="DevotionalReel"
      component={DevotionalReel}
      durationInFrames={defaultProps.durationInSeconds * FPS}
      fps={FPS}
      width={1080}
      height={1920}
      defaultProps={defaultProps}
      calculateMetadata={({ props }) => ({
        durationInFrames: Math.ceil(props.durationInSeconds * FPS),
      })}
    />
  );
};
