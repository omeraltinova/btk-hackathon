"use client";

const COACH_TOOL_NAME = "continue_coach_turn";
const INPUT_SAMPLE_RATE = 16_000;
const OUTPUT_SAMPLE_RATE = 24_000;
const GEMINI_LIVE_WEBSOCKET_URL =
  "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained";

const LIVE_SYSTEM_PROMPT = `
Sen Cüzdan Koçu'nun gerçek zamanlı ses katmanısın.
- Her kullanıcı turunda önce ${COACH_TOOL_NAME} aracını çağır.
- Kullanıcının söylediğini Türkçe, anlamı bozmadan "message" alanına yaz.
- Finansal veri, hesaplama, tavsiye, hedef, rapor veya uygulama durumu hakkında kendi başına cevap verme.
- Araçtan dönen "assistant_text" metnini doğal Türkçe ile seslendir; içerik ekleme, kapsam genişletme.
- Araç bir onay istediğini söylerse bunu açıkça aktar; işlemi onaylanmış gibi sunma.
- Kısa selamlaşmalar dahil tüm turları araç üzerinden geçir ki sohbet geçmişi korunabilsin.
`.trim();

const coachTurnFunction = {
  name: COACH_TOOL_NAME,
  description:
    "Current authenticated user's voice turn must be delegated to the existing scoped finance coach.",
  parameters: {
    type: "OBJECT",
    properties: {
      message: {
        type: "STRING",
        description: "The user's spoken Turkish message, preserving intent.",
      },
    },
    required: ["message"],
  },
};

type GeminiLiveInlineAudioPart = {
  inlineData?: {
    data?: string;
  };
};

type GeminiLiveFunctionCall = {
  id?: string;
  name?: string;
  args?: Record<string, unknown> | null;
};

type GeminiLiveServerMessage = {
  serverContent?: {
    interrupted?: boolean;
    inputTranscription?: {
      text?: string;
      finished?: boolean;
    };
    modelTurn?: {
      parts?: GeminiLiveInlineAudioPart[];
    };
  };
  toolCall?: {
    functionCalls?: GeminiLiveFunctionCall[];
  };
};

type GeminiLiveFunctionResponse = {
  id?: string;
  name: string;
  response: {
    assistant_text?: string;
    error?: string;
  };
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

function inlineAudioParts(message: GeminiLiveServerMessage): string[] {
  const parts = message.serverContent?.modelTurn?.parts ?? [];
  return parts.flatMap((part) => {
    const data = part.inlineData?.data;
    return typeof data === "string" ? [data] : [];
  });
}

export class GeminiLiveVoiceSession {
  private readonly options: GeminiLiveVoiceOptions;
  private readonly delegateCoachTurn: CoachTurnDelegate;
  private socket: WebSocket | null = null;
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
    await this.connectSocket();
    await this.startMicrophone();
    this.options.onStatus?.("listening");
  }

  async stop(): Promise<void> {
    this.closed = true;
    this.stopPlayback();
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.sendMessage({ realtimeInput: { audioStreamEnd: true } });
    this.socket?.close();
    await this.captureContext?.close();
    await this.playbackContext?.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.captureContext = null;
    this.playbackContext = null;
    this.socket = null;
    this.options.onStatus?.("closed");
  }

  private connectSocket(): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = `${GEMINI_LIVE_WEBSOCKET_URL}?access_token=${encodeURIComponent(this.options.token)}`;
      const socket = new WebSocket(url);
      let opened = false;
      this.socket = socket;
      const fail = (message: string) => {
        if (this.socket === socket) this.socket = null;
        reject(new Error(message));
      };
      socket.onopen = () => {
        opened = true;
        this.sendSetupMessage();
        resolve();
      };
      socket.onerror = () => {
        if (opened) {
          if (!this.closed) this.options.onError?.("Canlı sesli sohbet bağlantısı kesildi.");
          if (this.socket === socket) this.socket = null;
          return;
        }
        fail("Canlı sesli sohbet bağlantısı kurulamadı.");
      };
      socket.onclose = () => {
        if (!this.closed) this.options.onStatus?.("closed");
      };
      socket.onmessage = (event) => {
        void this.handleSocketMessage(event);
      };
    });
  }

  private sendSetupMessage() {
    this.sendMessage({
      setup: {
        model: `models/${this.options.model}`,
        generationConfig: {
          responseModalities: ["AUDIO"],
          speechConfig: {
            voiceConfig: {
              prebuiltVoiceConfig: {
                voiceName: this.options.voiceName,
              },
            },
          },
        },
        inputAudioTranscription: {},
        outputAudioTranscription: {},
        systemInstruction: {
          parts: [{ text: LIVE_SYSTEM_PROMPT }],
        },
        tools: [{ functionDeclarations: [coachTurnFunction] }],
      },
    });
  }

  private sendMessage(message: unknown) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  private async handleSocketMessage(event: MessageEvent) {
    const rawMessage =
      event.data instanceof Blob
        ? await event.data.text()
        : event.data instanceof ArrayBuffer
          ? new TextDecoder().decode(event.data)
          : String(event.data);
    let message: GeminiLiveServerMessage;
    try {
      message = JSON.parse(rawMessage) as GeminiLiveServerMessage;
    } catch {
      return;
    }
    await this.handleMessage(message);
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
    this.captureContext = new AudioContext({ sampleRate: INPUT_SAMPLE_RATE });
    this.source = this.captureContext.createMediaStreamSource(this.stream);
    this.processor = this.captureContext.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (event) => {
      if (
        !this.socket ||
        this.socket.readyState !== WebSocket.OPEN ||
        this.closed ||
        !this.captureContext
      ) {
        return;
      }
      const pcm = floatToPcm16(event.inputBuffer.getChannelData(0));
      this.sendMessage({
        realtimeInput: {
          audio: {
            data: bytesToBase64(pcm),
            mimeType: `audio/pcm;rate=${INPUT_SAMPLE_RATE}`,
          },
        },
      });
    };
    this.source.connect(this.processor);
    this.processor.connect(this.captureContext.destination);
  }

  private async handleMessage(message: GeminiLiveServerMessage): Promise<void> {
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

  private async handleFunctionCalls(functionCalls: GeminiLiveFunctionCall[]): Promise<void> {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
    const functionResponses: GeminiLiveFunctionResponse[] = await Promise.all(
      functionCalls.map(async (call) => {
        const rawMessage = call.args?.message;
        const userMessage =
          call.name === COACH_TOOL_NAME && typeof rawMessage === "string" ? rawMessage.trim() : "";
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
    this.sendMessage({
      toolResponse: {
        functionResponses,
      },
    });
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
