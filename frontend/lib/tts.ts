"use client";

import { apiBlob } from "@/lib/api";

let activeAudio: HTMLAudioElement | null = null;
let activeObjectUrl: string | null = null;
let activeFinish: (() => void) | null = null;
let requestSequence = 0;
const audioCache = new Map<string, Promise<Blob>>();

type PlayTtsOptions = {
  onPlaybackStart?: () => void;
};

function cleanupAudio(audio: HTMLAudioElement | null = activeAudio) {
  const shouldFinishActive = !audio || audio === activeAudio;
  if (audio && audio === activeAudio) {
    activeAudio = null;
  }
  if (shouldFinishActive) {
    activeFinish?.();
    activeFinish = null;
  }
  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
    activeObjectUrl = null;
  }
}

export function stopActiveSpeech() {
  requestSequence += 1;
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  if (activeAudio) {
    activeAudio.pause();
    activeAudio.currentTime = 0;
  }
  cleanupAudio();
}

function speechTextFromMarkdown(content: string): string {
  return content
    .replace(/!\[[^\]]*]\([^)]+\)/g, "")
    .replace(/\[([^\]]+)]\([^)]+\)/g, "$1")
    .replace(/^\s*#{1,6}\s+/gm, "")
    .replace(/^\s*(?:[-*]|\d+\.)\s+/gm, "")
    .replace(/[*_`>]/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function browserSpeechFallback(content: string, options: PlayTtsOptions = {}): Promise<boolean> {
  if (typeof window === "undefined" || !("speechSynthesis" in window))
    return Promise.resolve(false);
  const speechText = speechTextFromMarkdown(content);
  if (!speechText) return Promise.resolve(false);
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(speechText);
  utterance.lang = "tr-TR";
  return new Promise((resolve) => {
    const finish = () => {
      if (activeFinish === finish) activeFinish = null;
      resolve(true);
    };
    activeFinish = finish;
    const previousSequence = requestSequence;
    utterance.onstart = () => options.onPlaybackStart?.();
    utterance.onend = finish;
    utterance.onerror = finish;
    window.speechSynthesis.speak(utterance);
    if (requestSequence !== previousSequence) finish();
  });
}

function getCachedTtsBlob(content: string): Promise<Blob> {
  const cached = audioCache.get(content);
  if (cached) return cached;
  const request = apiBlob("/api/tts", {
    method: "POST",
    body: { text: content },
    silent: true,
  }).catch((error) => {
    audioCache.delete(content);
    throw error;
  });
  audioCache.set(content, request);
  return request;
}

export async function playTts(text: string, options: PlayTtsOptions = {}): Promise<void> {
  const content = text.trim();
  if (!content) return;

  const requestId = ++requestSequence;
  if (activeAudio) {
    activeAudio.pause();
    activeAudio.currentTime = 0;
  }
  cleanupAudio();

  let blob: Blob;
  try {
    blob = await getCachedTtsBlob(content);
  } catch (error) {
    if (await browserSpeechFallback(content, options)) return;
    throw error;
  }
  if (requestId !== requestSequence) return;

  const objectUrl = URL.createObjectURL(blob);
  const audio = new Audio(objectUrl);
  activeObjectUrl = objectUrl;
  activeAudio = audio;
  const finished = new Promise<void>((resolve) => {
    activeFinish = resolve;
    audio.addEventListener(
      "ended",
      () => {
        cleanupAudio(audio);
        resolve();
      },
      { once: true },
    );
    audio.addEventListener(
      "error",
      () => {
        cleanupAudio(audio);
        resolve();
      },
      { once: true },
    );
  });
  await audio.play();
  options.onPlaybackStart?.();
  await finished;
}
