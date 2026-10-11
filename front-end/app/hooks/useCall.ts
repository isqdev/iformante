"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CallPlayer, type Alignment } from "@/lib/call-player";
import { readChatStream } from "@/lib/chat-stream";
import type { Message } from "../models/message";

export type CallState = "off" | "starting" | "ready" | "recording" | "transcribing" | "thinking" | "speaking";
type InputSource = "keyboard" | "pointer";
const MAX_AUDIO_BYTES = 10 * 1024 * 1024;

export function useCall() {
  const [state, setState] = useState<CallState>("off");
  const [hint, setHint] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [checking, setChecking] = useState(true);
  const [available, setAvailable] = useState(false);
  const [configurationHint, setConfigurationHint] = useState("");
  const stateRef = useRef<CallState>("off");
  const player = useRef<CallPlayer | null>(null);
  const microphone = useRef<MediaStream | null>(null);
  const micSource = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const micSink = useRef<GainNode | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const held = useRef<InputSource | null>(null);
  const controller = useRef<AbortController | null>(null);
  const turnId = useRef<string | null>(null);
  const assistantId = useRef<string | null>(null);
  const history = useRef<Message[]>([]);
  const alive = useRef(true);
  const setupGeneration = useRef(0);
  const autoStarted = useRef(false);
  const setCallState = useCallback((next: CallState) => { stateRef.current = next; if (alive.current) setState(next); }, []);

  const acknowledge = useCallback((status: "completed" | "interrupted" | "failed") => {
    const id = assistantId.current;
    assistantId.current = null;
    if (!id) return;
    history.current = history.current.map((m) => m.id === id ? { ...m, playback_status: status } : m);
    if (alive.current) setMessages([...history.current]);
  }, []);

  const cancelCurrentTurn = useCallback(() => {
    const old = turnId.current;
    turnId.current = null;
    controller.current?.abort();
    controller.current = null;
    player.current?.stop();
    acknowledge("interrupted");
    if (old) void fetch("/api/call/cancel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ turn_id: old }), keepalive: true }).catch(() => {});
  }, [acknowledge]);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      setupGeneration.current += 1;
      held.current = null;
      if (recorder.current && recorder.current.state !== "inactive") {
        (recorder.current as MediaRecorder & { discard?: () => void }).discard?.();
        recorder.current.stop();
      }
      cancelCurrentTurn();
      microphone.current?.getTracks().forEach((track) => track.stop());
      microphone.current = null;
      micSource.current?.disconnect();
      micSink.current?.disconnect();
      void player.current?.close();
      player.current = null;
    };
  }, [cancelCurrentTurn]);

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/call/status", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error("Não foi possível verificar a chamada.");
      const status = await response.json();
      if (cancelled) return;
      setAvailable(status.ready === true);
      const missing = [!status.transcription_ready && "transcrição", !status.voice_ready && "voz", !status.answer_ready && "respostas"].filter(Boolean);
      setConfigurationHint(missing.length ? `A chamada aguarda a configuração de ${missing.join(" e ")} no servidor.` : "");
    }).catch((error) => { if (!cancelled) setConfigurationHint(error.message); }).finally(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, []);

  const enable = useCallback(async () => {
    if (stateRef.current !== "off") return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !window.AudioContext) {
      setHint("Este navegador não suporta chamadas. Use um navegador atualizado e uma conexão segura.");
      return;
    }
    const generation = ++setupGeneration.current;
    setCallState("starting");
    setHint("");
    let nextPlayer: CallPlayer | null = null;
    let nextMicrophone: MediaStream | null = null;
    try {
      microphone.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
      microphone.current = null;
      micSource.current?.disconnect();
      micSink.current?.disconnect();
      await player.current?.close();
      player.current = null;
      nextPlayer = await CallPlayer.create();
      if (!alive.current || setupGeneration.current !== generation) { await nextPlayer.close(); return; }
      nextMicrophone = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false });
      if (!alive.current || setupGeneration.current !== generation) { nextMicrophone.getTracks().forEach((track) => track.stop()); await nextPlayer.close(); return; }
      player.current = nextPlayer;
      microphone.current = nextMicrophone;
      analyser.current = nextPlayer.context.createAnalyser();
      analyser.current.fftSize = 1024;
      micSource.current = nextPlayer.context.createMediaStreamSource(nextMicrophone);
      micSource.current.connect(analyser.current);
      // Keep the microphone analysis graph rendering without monitoring it
      // through the speakers (or feeding speech back into the recording).
      micSink.current = nextPlayer.context.createGain();
      micSink.current.gain.value = 0;
      analyser.current.connect(micSink.current);
      micSink.current.connect(nextPlayer.context.destination);
      nextMicrophone.getAudioTracks()[0].onended = () => { cancelCurrentTurn(); setCallState("off"); setHint("O microfone foi desconectado. Tente conectar novamente."); };
      setCallState("ready");
    } catch {
      nextMicrophone?.getTracks().forEach((track) => track.stop());
      await nextPlayer?.close();
      if (alive.current && setupGeneration.current === generation) { setCallState("off"); setHint("Permita o microfone para conversar. Verifique também a saída de áudio."); }
    }
  }, [cancelCurrentTurn, setCallState]);

  useEffect(() => {
    if (autoStarted.current || checking || !available) return;
    autoStarted.current = true;
    void enable();
  }, [checking, available, enable]);

  const send = useCallback(async (blob: Blob) => {
    const id = crypto.randomUUID();
    const abort = new AbortController();
    controller.current = abort;
    turnId.current = id;
    player.current?.begin();
    setCallState("transcribing");
    const form = new FormData();
    form.append("audio", blob, blob.type.includes("mp4") ? "recording.mp4" : blob.type.includes("ogg") ? "recording.ogg" : "recording.webm");
    form.append("turn_id", id);
    form.append("messages", JSON.stringify(history.current.slice(-30).map(({ role, content, playback_status }) => ({ role, content: playback_status === "interrupted" || playback_status === "failed" ? `${content}\n[A leitura desta resposta não foi concluída pelo usuário.]` : content }))));
    let gotDone = false;
    try {
      const response = await fetch("/api/call/stream", { method: "POST", body: form, signal: abort.signal });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? body.error ?? "Não foi possível iniciar a resposta.");
      }
      for await (const event of readChatStream(response)) {
        if (turnId.current !== id || abort.signal.aborted) return;
        const data = JSON.parse(event.data);
        switch (event.event) {
          case "state": setCallState(data.value); break;
          case "transcript":
            history.current = [...history.current, { id: crypto.randomUUID(), role: "user", content: data.text, response_mode: "speech" }];
            setMessages([...history.current]);
            break;
          case "answer":
            assistantId.current = data.message_id;
            history.current = [...history.current, { id: data.message_id, role: "assistant", content: data.text, sources: data.sources, response_mode: "speech", playback_status: "pending" }];
            setMessages([...history.current]);
            break;
          case "audio_format": player.current?.format(data.sample_rate, data.channels, data.sample_width); break;
          case "alignment": player.current?.align(data.items as Alignment[]); break;
          case "audio": player.current?.append(data.sequence, data.data); break;
          case "error": throw new Error(data.message ?? "Não foi possível concluir a chamada.");
          case "done": gotDone = true; break;
        }
      }
      if (!gotDone) throw new Error("A conexão da chamada foi interrompida. Tente novamente.");
      await player.current?.end();
      if (turnId.current !== id || abort.signal.aborted) return;
      acknowledge("completed");
    } catch (error) {
      if (abort.signal.aborted || turnId.current !== id) return;
      player.current?.stop();
      acknowledge("failed");
      setHint(error instanceof Error ? error.message : "Não foi possível concluir a chamada.");
    } finally {
      if (turnId.current === id) {
        turnId.current = null;
        controller.current = null;
        setCallState("ready");
      }
    }
  }, [acknowledge, setCallState]);

  const startRecording = useCallback(() => {
    const stream = microphone.current;
    if (!stream || stream.getAudioTracks().every((track) => track.readyState !== "live")) { setHint("Habilite o microfone para falar."); return; }
    // This runs inside the actual keyboard/pointer gesture, including when
    // /call was opened directly and the browser suspended automatic audio.
    void player.current?.context.resume().catch(() => {});
    const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus", "audio/webm"].find((type) => MediaRecorder.isTypeSupported(type));
    const capture = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recorder.current = capture;
    const chunks: BlobPart[] = [];
    const started = performance.now();
    let bytes = 0;
    let voiced = false;
    let discard = false;
    const samples = new Float32Array(analyser.current?.fftSize ?? 1024);
    const sampleVoice = () => {
      analyser.current?.getFloatTimeDomainData(samples);
      const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
      if (rms > 0.006) voiced = true;
    };
    const vad = window.setInterval(sampleVoice, 40);
    capture.ondataavailable = ({ data }) => {
      chunks.push(data);
      bytes += data.size;
      if (bytes > MAX_AUDIO_BYTES) {
        discard = true;
        setHint("A gravação atingiu 10 MB. Tente uma pergunta mais curta.");
        if (capture.state !== "inactive") capture.stop();
      }
    };
    capture.onerror = () => { discard = true; setHint("Não foi possível gravar o áudio. Tente novamente."); };
    capture.onstop = () => {
      sampleVoice();
      window.clearInterval(vad);
      recorder.current = null;
      if (!alive.current) return;
      const blob = new Blob(chunks, { type: capture.mimeType });
      if (discard || bytes > MAX_AUDIO_BYTES) { setCallState("ready"); return; }
      if (!voiced || performance.now() - started < 200 || !blob.size) { setCallState("ready"); setHint("Nenhuma fala identificada. Segure para falar e solte ao terminar."); return; }
      void send(blob);
    };
    // A cancelled hold must never become an upload (blur, dialog, pointercancel).
    (capture as MediaRecorder & { discard?: () => void }).discard = () => { discard = true; };
    capture.start(250);
    setHint("");
    setCallState("recording");
  }, [send, setCallState]);

  const press = useCallback((source: InputSource) => {
    if (held.current || !available || stateRef.current !== "ready") return;
    held.current = source;
    startRecording();
  }, [available, startRecording]);

  const release = useCallback((source: InputSource, discard = false) => {
    if (held.current !== source) return;
    held.current = null;
    const capture = recorder.current as (MediaRecorder & { discard?: () => void }) | null;
    if (capture && capture.state !== "inactive") {
      if (discard) capture.discard?.();
      capture.stop();
    }
  }, []);

  useEffect(() => {
    const eligible = (target: EventTarget | null) => {
      if (document.querySelector('[role="dialog"]')) return false;
      if (!(target instanceof HTMLElement)) return true;
      if (target.closest('[data-call-talk="true"]')) return true;
      return !target.closest('input,textarea,select,button,a,[contenteditable="true"],[role="button"]');
    };
    const down = (event: KeyboardEvent) => {
      if (event.code !== "Space" || !eligible(event.target)) return;
      event.preventDefault();
      if (!event.repeat) press("keyboard");
    };
    const up = (event: KeyboardEvent) => {
      if (event.code !== "Space") return;
      if (held.current === "keyboard") event.preventDefault();
      release("keyboard");
    };
    const blur = () => { if (held.current) release(held.current, true); };
    const visibility = () => { if (document.hidden) blur(); };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", blur);
    document.addEventListener("visibilitychange", visibility);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); window.removeEventListener("blur", blur); document.removeEventListener("visibilitychange", visibility); };
  }, [press, release]);

  const disable = useCallback(() => {
    setupGeneration.current++;
    if (held.current) release(held.current, true);
    cancelCurrentTurn();
    microphone.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    microphone.current = null;
    micSource.current?.disconnect();
    micSink.current?.disconnect();
    void player.current?.close();
    player.current = null;
    setCallState("off");
    setHint("");
  }, [cancelCurrentTurn, release, setCallState]);

  return { state, hint, messages, checking, available, configurationHint, player, enable, disable, press, release };
}
