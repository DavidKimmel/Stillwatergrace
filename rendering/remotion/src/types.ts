export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

export interface ReelProps {
  imageSrc: string;
  audioSrc: string;
  words: WordTimestamp[];
  verseReference: string;
  durationInSeconds: number;
}
