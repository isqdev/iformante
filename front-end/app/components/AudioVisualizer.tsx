"use client";

import {useEffect, useRef} from "react";

type AudioVisualizerProps = {
  active: boolean;
};

const BAR_COUNT = 36;

export function AudioVisualizer({active}: AudioVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!active) {
      return;
    }

    let audioContext: AudioContext | null = null;
    let animationFrame = 0;
    let mediaStream: MediaStream | null = null;
    let cancelled = false;

    async function startVisualizer() {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({audio: true});

        if (cancelled || !canvasRef.current) {
          mediaStream.getTracks().forEach((track) => track.stop());
          return;
        }

        audioContext = new AudioContext();
        const analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(mediaStream);

        analyser.fftSize = 128;
        analyser.smoothingTimeConstant = 0.82;
        const frequencyData = new Uint8Array(analyser.frequencyBinCount);
        source.connect(analyser);

        function draw() {
          const canvas = canvasRef.current;

          if (!canvas || !audioContext) {
            return;
          }

          const context = canvas.getContext("2d");

          if (!context) {
            return;
          }

          const bounds = canvas.getBoundingClientRect();
          const pixelRatio = window.devicePixelRatio || 1;
          const width = Math.max(1, Math.floor(bounds.width * pixelRatio));
          const height = Math.max(1, Math.floor(bounds.height * pixelRatio));

          if (canvas.width !== width || canvas.height !== height) {
            canvas.width = width;
            canvas.height = height;
          }

          analyser.getByteFrequencyData(frequencyData);
          context.clearRect(0, 0, width, height);
          context.fillStyle = getComputedStyle(canvas).color;

          const gap = 2 * pixelRatio;
          const barWidth = Math.max(
            1,
            (width - gap * (BAR_COUNT - 1)) / BAR_COUNT,
          );

          for (let index = 0; index < BAR_COUNT; index += 1) {
            const sampleIndex = Math.floor(
              (index / BAR_COUNT) * frequencyData.length,
            );
            const amplitude = frequencyData[sampleIndex] / 255;
            const minimumHeight = 3 * pixelRatio;
            const barHeight = Math.max(
              minimumHeight,
              amplitude * height * 0.82,
            );
            const x = index * (barWidth + gap);
            const y = (height - barHeight) / 2;
            const radius = Math.min(barWidth / 2, 2 * pixelRatio);

            context.beginPath();
            context.roundRect(x, y, barWidth, barHeight, radius);
            context.fill();
          }

          animationFrame = requestAnimationFrame(draw);
        }

        draw();
      } catch {
        // SpeechRecognition reports microphone errors through the existing flow.
      }
    }

    void startVisualizer();

    return () => {
      cancelled = true;
      cancelAnimationFrame(animationFrame);
      mediaStream?.getTracks().forEach((track) => track.stop());
      void audioContext?.close();
    };
  }, [active]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="h-10 min-w-0 flex-1 text-primary"
    />
  );
}
