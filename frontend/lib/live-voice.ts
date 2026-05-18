"use client";

import {
  GoogleGenAI,
  Modality,
  type FunctionCall,
  type FunctionDeclaration,
  type LiveServerMessage,
  type Session,
  Type,
} from "@google/genai";

const COACH_TOOL_NAME = "continue_coach_turn";
const OUTPUT_SAMPLE_RATE = 24_000;

const LIVE_SYSTEM_PROMPT = `
Sen Cüzdan Koçu'nun gerçek zamanlı ses katmanısın.
- Her kullanıcı turunda önce ${COACH_TOOL_NAME} aracını çağır.
- Kullanıcının söylediğini Türkçe, anlamı bozmadan "message" alanına yaz.
- Finansal veri, hesaplama, tavsiye, hedef, rapor veya uygulama durumu hakkında kendi başına cevap verme.
- Araçtan dönen "assistant_text" metnini doğal Türkçe ile seslendir; içerik ekleme, kapsam genişletme.
- Araç bir onay istediğini söylerse bunu açıkça aktar; işlemi onaylanmış gibi sunma.
- Kısa selamlaşmalar dahil tüm turları araç üzerinden geçir ki sohbet geçmişi korunabilsin.
`.trim();

const coachTurnFunction: FunctionDeclaration = {
  name: COACH_TOOL_NAME,
  description:
    "Current authenticated user's voice turn must be delegated to the existing scoped finance coach.",
  parameters: {
    type: Type.OBJECT,
    properties: {
      message: {
        type: Type.STRING,
        description: "The user's spoken Turkish message, preserving intent.",
      },
    },
    required: ["message"],
  },
};

export type GeminiLiveVoiceOptions = {
  token: string;
  model: string;
  voiceName: string;
  onStatus?: (status: "connecting" | "listening" | "closed") => void;
  onInputTranscript?: (text: string) => void;
  onError?: (message: string) => void;
};

export type CoachTurnDelegate = (message: string) => Promise<string>;

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    const chunk = bytes.subarray(offset, offset + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return window.btoa(binary);
}

function base64ToBytes(data: string): Uint8Array {
  const binary = window.atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function floatToPcm16(channel: Float32Array): Uint8Array {
  const output = new Int16Array(channel.length);
  for (let index = 0; index < channel.length; index += 1) {
    const clamped = Math.max(-1, Math.min(1, channel[index] ?? 0));
    output[index] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return new Uint8Array(output.buffer);
}

function pcm16ToFloat(bytes: Uint8Array): Float32Array {
  const samples = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
  const output = new Float32Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    output[index] = (samples[index] ?? 0) / 0x8000;
  }
  return output;
}

function inlineAudioParts(message: LiveServerMessage): string[] {
  const parts = message.serverContent?.modelTurn?.parts ?? [];
  return parts.flatMap((part) => {
    const data = part.inlineData?.data;
    return typeof data === "string" ? [data] : [];
  });
}

export class GeminiLiveVoiceSession {
  private readonly options: GeminiLiveVoiceOptions;
  private readonly delegateCoachTurn: CoachTurnDelegate;
  private session: Session | null = null;
  private captureContext: AudioContext | null = null;
  private playbackContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private stream: MediaStream | null = null;
  private scheduledSources = new Set<AudioBufferSourceNode>();
  private playbackCursor = 0;
  private closed = false;

  constructor(options: GeminiLiveVoiceOptions, delegateCoachTurn: CoachTurnDelegate) {
    this.options = options;
    this.delegateCoachTurn = delegateCoachTurn;
  }

  async start(): Promise<void> {
    this.options.onStatus?.("connecting");
    const ai = new GoogleGenAI({ apiKey: this.options.token });
    this.session = await ai.live.connect({
      model: this.options.model,
      config: {
        responseModalities: [Modality.AUDIO],
        inputAudioTranscription: {},
        outputAudioTranscription: {},
        systemInstruction: {
          parts: [{ text: LIVE_SYSTEM_PROMPT }],
        },
        speechConfig: {
          voiceConfig: {
            prebuiltVoiceConfig: {
              voiceName: this.options.voiceName,
            },
          },
        },
        tools: [{ functionDeclarations: [coachTurnFunction] }],
      },
      callbacks: {
        onmessage: (message) => {
          void this.handleMessage(message);
        },
        onerror: () => {
          this.options.onError?.("Canlı sesli sohbet bağlantısı kesildi.");
        },
        onclose: () => {
          if (!this.closed) this.options.onStatus?.("closed");
        },
      },
    });
    await this.startMicrophone();
    this.options.onStatus?.("listening");
  }

  async stop(): Promise<void> {
    this.closed = true;
    this.stopPlayback();
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.session?.sendRealtimeInput({ audioStreamEnd: true });
    this.session?.close();
    await this.captureContext?.close();
    await this.playbackContext?.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.captureContext = null;
    this.playbackContext = null;
    this.session = null;
    this.options.onStatus?.("closed");
  }

  private async startMicrophone(): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Bu tarayıcı canlı mikrofon akışını desteklemiyor.");
    }
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    this.captureContext = new AudioContext();
    this.source = this.captureContext.createMediaStreamSource(this.stream);
    this.processor = this.captureContext.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (event) => {
      if (!this.session || this.closed || !this.captureContext) return;
      const pcm = floatToPcm16(event.inputBuffer.getChannelData(0));
      this.session.sendRealtimeInput({
        audio: {
          data: bytesToBase64(pcm),
          mimeType: `audio/pcm;rate=${this.captureContext.sampleRate}`,
        },
      });
    };
    this.source.connect(this.processor);
    this.processor.connect(this.captureContext.destination);
  }

  private async handleMessage(message: LiveServerMessage): Promise<void> {
    const serverContent = message.serverContent;
    if (serverContent?.interrupted) this.stopPlayback();

    const inputTranscript = serverContent?.inputTranscription;
    if (inputTranscript?.finished && inputTranscript.text) {
      this.options.onInputTranscript?.(inputTranscript.text.trim());
    }

    for (const data of inlineAudioParts(message)) {
      await this.playAudioChunk(data);
    }

    const functionCalls = message.toolCall?.functionCalls ?? [];
    if (functionCalls.length > 0) {
      await this.handleFunctionCalls(functionCalls);
    }
  }

  private async handleFunctionCalls(functionCalls: FunctionCall[]): Promise<void> {
    if (!this.session) return;
    const functionResponses = await Promise.all(
      functionCalls.map(async (call) => {
        const userMessage =
          call.name === COACH_TOOL_NAME && typeof call.args?.message === "string"
            ? call.args.message.trim()
            : "";
        if (!userMessage) {
          return {
            id: call.id,
            name: call.name ?? COACH_TOOL_NAME,
            response: {
              error: "Kullanıcı mesajı anlaşılamadı.",
            },
          };
        }
        try {
          const assistantText = await this.delegateCoachTurn(userMessage);
          return {
            id: call.id,
            name: call.name ?? COACH_TOOL_NAME,
            response: {
              assistant_text: assistantText,
            },
          };
        } catch {
          return {
            id: call.id,
            name: call.name ?? COACH_TOOL_NAME,
            response: {
              error: "Koç yanıtı hazırlanamadı.",
            },
          };
        }
      }),
    );
    this.session.sendToolResponse({ functionResponses });
  }

  private async playAudioChunk(data: string): Promise<void> {
    const bytes = base64ToBytes(data);
    if (bytes.byteLength < 2) return;
    const samples = pcm16ToFloat(bytes);
    if (!this.playbackContext) this.playbackContext = new AudioContext();
    const audioBuffer = this.playbackContext.createBuffer(1, samples.length, OUTPUT_SAMPLE_RATE);
    audioBuffer.copyToChannel(new Float32Array(samples), 0);
    const source = this.playbackContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.playbackContext.destination);
    const startAt = Math.max(this.playbackContext.currentTime, this.playbackCursor);
    source.start(startAt);
    this.playbackCursor = startAt + audioBuffer.duration;
    this.scheduledSources.add(source);
    source.addEventListener(
      "ended",
      () => {
        this.scheduledSources.delete(source);
      },
      { once: true },
    );
  }

  private stopPlayback() {
    for (const source of this.scheduledSources) {
      try {
        source.stop();
      } catch {
        // Already stopped or not yet scheduled; safe to ignore.
      }
    }
    this.scheduledSources.clear();
    if (this.playbackContext) this.playbackCursor = this.playbackContext.currentTime;
  }
}
