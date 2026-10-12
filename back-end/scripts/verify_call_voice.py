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
from app.config import settings
from app.services.call_audio import PocketTTSService
from app.services.speech_text import normalize_speech


async def check_worker(folder):
    service = PocketTTSService(settings.pocket_tts_config_path, settings.pocket_tts_voice_path)
    try:
        await service.warm_up()
        pid = service._process.pid
        events = [event async for event in service.stream("Olá! Como posso ajudar?")]
        assert any(name == "audio" for name, _ in events)
        assert next(payload for name, payload in events if name == "audio_format") == {"sample_rate": 24000, "channels": 1, "sample_width": 2}
        again = [event async for event in service.stream("Estou pronto para ouvir.")]
        assert service._process.pid == pid, "Voice must remain loaded between turns"
        interrupted = service.stream("Vamos conversar sobre os cursos do campus.")
        await anext(interrupted)
        await interrupted.aclose()
        assert service._process is None, "Interruption must stop the synthesis worker"
        restarted = [event async for event in service.stream("Pode falar.")]
        assert any(name == "audio" for name, _ in restarted)
        examples = [
            "O campus oferece cursos técnicos e superiores. Para saber os requisitos de ingresso, consulte o edital do processo seletivo. Posso ajudar com informações sobre um curso específico ou sobre as etapas de inscrição e os documentos necessários para participar corretamente.",
            normalize_speech("O prazo é 21/10/2026, às 08:30. O curso tem 1.200 horas. A inscrição é gratuita."),
            "Quais são os cursos superiores do Instituto Federal do Paraná, campus Paranavaí?",
            "O campus oferece cursos técnicos e superiores. Para saber os requisitos de ingresso, consulte o edital do processo seletivo. Posso ajudar com informações sobre um curso específico ou sobre as etapas de inscrição e os documentos necessários para participar corretamente. Assim, você consegue se preparar com antecedência, conferir os requisitos com calma e acompanhar cada etapa do processo de seleção.",
        ]
        for index, text in enumerate(examples):
            if index == 3:
                assert len(text.split()) == 60, "Exercise the full spoken-word budget"
            chunks = [event async for event in service.stream(text)]
            frames = [payload for name, payload in chunks if name == "audio"]
            assert [frame["sequence"] for frame in frames] == list(range(len(frames)))
            audio = b"".join(base64.b64decode(frame["data"]) for frame in frames)
            assert len(audio) // 2 == chunks[-1][1]["samples"]
            rate = next(payload["sample_rate"] for name, payload in chunks if name == "audio_format")
            filename = "call-test-input.wav" if index == 2 else f"call-test-sample-{index + 1}.wav"
            with wave.open(str(folder / filename), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(rate)
                output.writeframes(audio)
            print(json.dumps({"voice": Path(service.voice_path).stem, "words": len(text.split()), "seconds": round(len(audio) / 2 / rate, 2), "sample_rate": rate}), flush=True)
        print(json.dumps({"worker_reused": True, "worker_cancelled": True, "worker_restarted": True, "events": len(events), "second_events": len(again)}), flush=True)
    finally:
        await service.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "voices"
    asyncio.run(check_worker(folder))
    if not args.api_url:
        return
    input_path = folder / "call-test-input.wav"
    audio = bytearray()
    events = []
    answer = ""
    first_audio = None
    rate = None
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
                    if name == "audio_format":
                        rate = payload["sample_rate"]
                    if name == "audio":
                        if first_audio is None:
                            first_audio = time.monotonic() - started
                        audio.extend(base64.b64decode(payload["data"]))
    assert "transcript" in events and "rag" in events and "done" in events
    assert rate and audio
    assert events.index("answer") < events.index("audio") < events.index("done")
    with wave.open(str(folder / "call-test-output.wav"), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate); output.writeframes(audio)
    print(json.dumps({"end_to_end": True, "answer_words": len(answer.split()), "audio_seconds": round(len(audio) / 2 / rate, 2), "first_audio_seconds": round(first_audio, 2), "audio_frames": events.count("audio")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
