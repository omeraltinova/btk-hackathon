"use client";

import { apiBlob } from "@/lib/api";

let activeAudio: HTMLAudioElement | null = null;
let activeObjectUrl: string | null = null;
let requestSequence = 0;
const audioCache = new Map<string, Promise<Blob>>();

function cleanupAudio(audio: HTMLAudioElement | null = activeAudio) {
  if (audio && audio === activeAudio) {
    activeAudio = null;
  }
  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
    activeObjectUrl = null;
  }
}

export function stopActiveSpeech() {
  requestSequence += 1;
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

function browserSpeechFallback(content: string): boolean {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  const speechText = speechTextFromMarkdown(content);
  if (!speechText) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(speechText);
  utterance.lang = "tr-TR";
  window.speechSynthesis.speak(utterance);
  return true;
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

export async function playTts(text: string): Promise<void> {
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
    if (browserSpeechFallback(content)) return;
    throw error;
  }
  if (requestId !== requestSequence) return;

  const objectUrl = URL.createObjectURL(blob);
  const audio = new Audio(objectUrl);
  activeObjectUrl = objectUrl;
  activeAudio = audio;
  audio.addEventListener("ended", () => cleanupAudio(audio), { once: true });
  audio.addEventListener("error", () => cleanupAudio(audio), { once: true });
  await audio.play();
}
