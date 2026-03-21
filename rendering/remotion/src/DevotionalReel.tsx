import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { ReelProps } from "./types";

/** Static full verse text display with fade in/out */
function VerseTextDisplay({
  verseText,
  durationInSeconds,
}: {
  verseText: string;
  durationInSeconds: number;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Fade in over the first 1.5 seconds
  const fadeIn = interpolate(
    currentTime,
    [0.5, 2.0],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Fade out during the last 1.5 seconds
  const fadeOut = interpolate(
    currentTime,
    [durationInSeconds - 1.5, durationInSeconds],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: 60,
        right: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: fadeIn * fadeOut,
      }}
    >
      <div
        style={{
          fontFamily: "'Georgia', 'Times New Roman', serif",
          fontSize: 48,
          fontWeight: 400,
          color: "#FFF8F0",
          textAlign: "center",
          lineHeight: 1.5,
          textShadow:
            "0 2px 12px rgba(0,0,0,0.7), 0 1px 4px rgba(0,0,0,0.5)",
          letterSpacing: 0.5,
        }}
      >
        {verseText}
      </div>
    </div>
  );
}

function VerseReference({
  reference,
  durationInSeconds,
}: {
  reference: string;
  durationInSeconds: number;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  const fadeIn = interpolate(
    currentTime,
    [durationInSeconds * 0.6, durationInSeconds * 0.65],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        bottom: 260,
        left: 80,
        right: 80,
        textAlign: "center",
        opacity: fadeIn,
        fontFamily: "'Georgia', serif",
        fontSize: 32,
        color: "rgba(255, 248, 240, 0.8)",
        fontStyle: "italic",
        textShadow: "0 1px 8px rgba(0,0,0,0.5)",
      }}
    >
      {reference}
    </div>
  );
}

function FilmGrainOverlay() {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity: 0.04,
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' seed='${frame % 30}' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        backgroundSize: "256px 256px",
        mixBlendMode: "overlay",
        pointerEvents: "none",
      }}
    />
  );
}

function WarmColorGrade() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "linear-gradient(180deg, rgba(180,120,60,0.08) 0%, rgba(0,0,0,0.15) 100%)",
        mixBlendMode: "multiply",
        pointerEvents: "none",
      }}
    />
  );
}

function Branding() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fadeIn = interpolate(frame, [fps * 1, fps * 1.5], [0, 0.5], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 60,
        right: 50,
        opacity: fadeIn,
        fontFamily: "'Georgia', serif",
        fontSize: 22,
        color: "rgba(255, 248, 240, 0.45)",
        letterSpacing: 1,
      }}
    >
      @stillwatergrace
    </div>
  );
}

export const DevotionalReel: React.FC<ReelProps> = ({
  imageSrc,
  audioSrc,
  verseText,
  verseReference,
  durationInSeconds,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const totalFrames = durationInSeconds * fps;

  // Ken Burns: subtle slow zoom from 1.0 to 1.08 over full duration
  const scale = interpolate(frame, [0, totalFrames], [1.0, 1.08], {
    extrapolateRight: "clamp",
  });

  // Slight upward drift
  const translateY = interpolate(frame, [0, totalFrames], [0, -15], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Background image with Ken Burns */}
      <div
        style={{
          position: "absolute",
          inset: -40,
          transform: `scale(${scale}) translateY(${translateY}px)`,
          transformOrigin: "center center",
        }}
      >
        <Img
          src={staticFile(imageSrc)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      </div>

      {/* Cinematic color grade */}
      <WarmColorGrade />

      {/* Film grain */}
      <FilmGrainOverlay />

      {/* Dark gradient for text readability */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(180deg, rgba(0,0,0,0.05) 0%, rgba(0,0,0,0.1) 40%, rgba(0,0,0,0.55) 100%)",
        }}
      />

      {/* Static full verse text */}
      <VerseTextDisplay
        verseText={verseText}
        durationInSeconds={durationInSeconds}
      />

      {/* Verse reference */}
      <VerseReference
        reference={verseReference}
        durationInSeconds={durationInSeconds}
      />

      {/* Branding */}
      <Branding />

      {/* Audio */}
      <Audio src={staticFile(audioSrc)} />
    </AbsoluteFill>
  );
};
