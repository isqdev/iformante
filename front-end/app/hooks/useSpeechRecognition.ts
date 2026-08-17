"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

type SpeechRecognitionResultItem = {
  transcript: string;
};

type SpeechRecognitionResult = {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechRecognitionResultItem;
};

type SpeechRecognitionEvent = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: SpeechRecognitionResult;
  };
};

type SpeechRecognitionErrorEvent = {
  error: string;
};

type SpeechRecognitionInstance = {
  abort: () => void;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onstart: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

type UseSpeechRecognitionOptions = {
  onError: (message: string) => void;
  onFinalTranscript: (transcript: string) => void;
};

const SILENCE_TIMEOUT_MS = 2000;
const INITIAL_SPEECH_TIMEOUT_MS = 10000;

export function useSpeechRecognition({
  onError,
  onFinalTranscript,
}: UseSpeechRecognitionOptions) {
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const silenceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcriptRef = useRef("");
  const cancelledRef = useRef(false);
  const failedRef = useRef(false);
  const submittedRef = useRef(false);
  const onErrorRef = useRef(onError);
  const onFinalTranscriptRef = useRef(onFinalTranscript);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const isSupported = useSyncExternalStore(
    subscribeToSpeechRecognitionSupport,
    getSpeechRecognitionSupport,
    getServerSpeechRecognitionSupport,
  );

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    onFinalTranscriptRef.current = onFinalTranscript;
  }, [onFinalTranscript]);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      clearTimeoutIfPresent(silenceTimeoutRef);
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, []);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    clearTimeoutIfPresent(silenceTimeoutRef);
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    transcriptRef.current = "";
    setIsListening(false);
    setTranscript("");
  }, []);

  const submit = useCallback(() => {
    const normalizedTranscript = transcriptRef.current.trim();

    if (!normalizedTranscript || submittedRef.current) {
      return false;
    }

    submittedRef.current = true;
    clearTimeoutIfPresent(silenceTimeoutRef);
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setIsListening(false);
    onFinalTranscriptRef.current(normalizedTranscript);
    return true;
  }, []);

  const start = useCallback(() => {
    const SpeechRecognition =
      window.SpeechRecognition ?? window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      onErrorRef.current(
        "O reconhecimento de voz não está disponível neste navegador.",
      );
      return false;
    }

    recognitionRef.current?.abort();
    cancelledRef.current = false;
    failedRef.current = false;
    submittedRef.current = false;
    transcriptRef.current = "";
    clearTimeoutIfPresent(silenceTimeoutRef);
    setTranscript("");

    const recognition = new SpeechRecognition();
    recognition.lang = "pt-BR";
    recognition.continuous = true;
    recognition.interimResults = true;

    function finishAfterSilence() {
      if (cancelledRef.current || submittedRef.current) {
        return;
      }

      const normalizedTranscript = transcriptRef.current.trim();

      if (!normalizedTranscript) {
        failedRef.current = true;
        recognition.abort();
        recognitionRef.current = null;
        setIsListening(false);
        onErrorRef.current("Nenhuma fala foi identificada.");
        return;
      }

      submit();
    }

    function restartSilenceTimeout(timeout = SILENCE_TIMEOUT_MS) {
      clearTimeoutIfPresent(silenceTimeoutRef);
      silenceTimeoutRef.current = setTimeout(finishAfterSilence, timeout);
    }

    recognition.onstart = () => {
      setIsListening(true);
      restartSilenceTimeout(INITIAL_SPEECH_TIMEOUT_MS);
    };

    recognition.onresult = (event) => {
      const transcriptParts: string[] = [];

      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index];
        const resultTranscript = result[0]?.transcript ?? "";

        if (resultTranscript.trim()) {
          transcriptParts.push(resultTranscript.trim());
        }
      }

      const completeTranscript = transcriptParts.join(" ");
      transcriptRef.current = completeTranscript;
      setTranscript(completeTranscript);
      restartSilenceTimeout();
    };

    recognition.onerror = (event) => {
      clearTimeoutIfPresent(silenceTimeoutRef);
      setIsListening(false);
      recognitionRef.current = null;

      if (cancelledRef.current || event.error === "aborted") {
        return;
      }

      failedRef.current = true;
      onErrorRef.current(getSpeechRecognitionErrorMessage(event.error));
    };

    recognition.onend = () => {
      clearTimeoutIfPresent(silenceTimeoutRef);
      setIsListening(false);
      recognitionRef.current = null;

      if (
        !cancelledRef.current &&
        !failedRef.current &&
        !submittedRef.current
      ) {
        const normalizedTranscript = transcriptRef.current.trim();

        if (normalizedTranscript) {
          submittedRef.current = true;
          onFinalTranscriptRef.current(normalizedTranscript);
        } else {
          onErrorRef.current("Nenhuma fala foi identificada.");
        }
      }
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
      return true;
    } catch {
      recognitionRef.current = null;
      onErrorRef.current("Não foi possível iniciar o reconhecimento de voz.");
      return false;
    }
  }, [submit]);

  return {
    cancel,
    isListening,
    isSupported,
    start,
    submit,
    transcript,
  };
}

function clearTimeoutIfPresent(
  timeoutRef: { current: ReturnType<typeof setTimeout> | null },
) {
  if (timeoutRef.current === null) {
    return;
  }

  clearTimeout(timeoutRef.current);
  timeoutRef.current = null;
}

function subscribeToSpeechRecognitionSupport() {
  return () => undefined;
}

function getSpeechRecognitionSupport() {
  return Boolean(window.SpeechRecognition ?? window.webkitSpeechRecognition);
}

function getServerSpeechRecognitionSupport() {
  return false;
}

function getSpeechRecognitionErrorMessage(error: string) {
  if (error === "not-allowed" || error === "service-not-allowed") {
    return "Permita o acesso ao microfone para usar a entrada por voz.";
  }

  if (error === "no-speech") {
    return "Nenhuma fala foi identificada.";
  }

  if (error === "audio-capture") {
    return "Nenhum microfone foi encontrado.";
  }

  if (error === "network") {
    return "O reconhecimento de voz está indisponível no momento.";
  }

  return "Nao foi possivel reconhecer a fala.";
}
