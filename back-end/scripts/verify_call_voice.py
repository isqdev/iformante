"""Local voice/streaming smoke test. Network call is explicit via --api-url."""
import argparse
import asyncio
import base64
import json
import time
import uuid
import wave
from pathlib import Path

import httpx
from piper import PiperVoice

from app.services.call_audio import PiperService
from app.services.speech_text import normalize_speech, within_speech_budget


async def check_worker(model):
    service = PiperService(str(model))
    try:
        await service.warm_up()
        pid = service._process.pid
        events = [event async for event in service.stream("Olá! Como posso ajudar?")]
        assert any(name == "audio" for name, _ in events)
        assert any(name == "alignment" for name, _ in events)
        again = [event async for event in service.stream("Estou pronto para ouvir.")]
        assert service._process.pid == pid, "Voice must remain loaded between turns"
        interrupted = service.stream("Vamos conversar sobre os cursos do campus.")
        await anext(interrupted)
        await interrupted.aclose()
        assert service._process is None, "Interruption must stop the synthesis worker"
        restarted = [event async for event in service.stream("Pode falar.")]
        assert any(name == "audio" for name, _ in restarted)
        print(json.dumps({"worker_reused": True, "worker_cancelled": True, "worker_restarted": True, "events": len(events), "second_events": len(again)}))
    finally:
        await service.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "voices"
    model = folder / "pt_BR-faber-medium.onnx"
    voice = PiperVoice.load(model, include_alignments=True)
    examples = [
        "O campus oferece cursos técnicos e superiores. Para saber os requisitos de ingresso, consulte o edital do processo seletivo. Posso ajudar com informações sobre um curso específico ou sobre as etapas de inscrição e os documentos necessários para participar corretamente.",
        normalize_speech("O prazo é 21/10/2026, às 08:30. O curso tem 1.200 horas. A inscrição é gratuita."),
    ]
    for text in examples:
        assert within_speech_budget(text)
        chunks = list(voice.synthesize(text, include_alignments=True))
        print(json.dumps({"words": len(text.split()), "seconds": round(sum(len(c.audio_int16_array) / c.sample_rate for c in chunks), 2), "phoneme_alignments": sum(len(c.phoneme_alignments or []) for c in chunks)}))
    asyncio.run(check_worker(model))
    if not args.api_url:
        return
    input_path = folder / "call-test-input.wav"
    with wave.open(str(input_path), "wb") as output:
        voice.synthesize_wav("Quais são os cursos superiores do Instituto Federal do Paraná, campus Paranavaí?", output)
    audio = bytearray()
    events = []
    answer = ""
    first_audio = None
    started = time.monotonic()
    with input_path.open("rb") as recording, httpx.Client(timeout=120) as client:
        with client.stream("POST", f"{args.api_url.rstrip('/')}/call/stream", files={"audio": (input_path.name, recording, "audio/wav")}, data={"turn_id": str(uuid.uuid4())}) as response:
            response.raise_for_status()
            name = ""
            for line in response.iter_lines():
                if line.startswith("event: "):
                    name = line[7:]
                if line.startswith("data: "):
                    payload = json.loads(line[6:])
                    events.append(name)
                    if name == "error":
                        raise RuntimeError(payload["message"])
                    if name == "answer":
                        answer = payload["text"]
                    if name == "audio":
                        if first_audio is None:
                            first_audio = time.monotonic() - started
                        audio.extend(base64.b64decode(payload["data"]))
    assert "transcript" in events and "rag" in events and "alignment" in events and "done" in events
    assert within_speech_budget(answer)
    assert events.index("answer") < events.index("audio") < events.index("done")
    with wave.open(str(folder / "call-test-output.wav"), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(22050); output.writeframes(audio)
    print(json.dumps({"end_to_end": True, "answer_words": len(answer.split()), "audio_seconds": round(len(audio) / 2 / 22050, 2), "first_audio_seconds": round(first_audio, 2), "audio_frames": events.count("audio"), "alignment_batches": events.count("alignment")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
