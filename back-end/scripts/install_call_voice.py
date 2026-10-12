"""Install the pinned Portuguese Pocket TTS model and its George voice state."""
import hashlib
from importlib.util import find_spec
from pathlib import Path

import httpx
import yaml

REVISION = "575d14372df89a4534bcb989870a34e77544b09f"
BASE = f"https://huggingface.co/kyutai/pocket-tts-without-voice-cloning/resolve/{REVISION}/languages/portuguese"
FILES = {
    "model.safetensors": ("model.safetensors", "28e20f32515ba8bd0eaec69671f11f8921414fcdc375aa072fa09f46cc1057c5"),
    "tokenizer.json": ("tokenizer.json", "b33e269f7f042a763080d71ba087d74d2f6759674b238a723c028e436b1a25ab"),
    "george.safetensors": ("embeddings/george.safetensors", "8e37c8fd8839aab501bdc0c30c8e4d37996e62fb66c063d3e54c80c98b4b6ea5"),
}


def write_local_config(target: Path):
    # Keep the architecture from the pinned runtime, with fully local asset paths.
    package = find_spec("pocket_tts")
    if not package or not package.submodule_search_locations:
        raise RuntimeError("Install pocket-tts before installing its model.")
    template = Path(next(iter(package.submodule_search_locations))) / "config" / "portuguese.yaml"
    config = yaml.safe_load(template.read_text(encoding="utf-8"))
    config["weights_path"] = str(target / "model.safetensors")
    config["weights_path_without_voice_cloning"] = None
    config["flow_lm"]["lookup_table"]["tokenizer_path"] = str(target / "tokenizer.json")
    path = target / "portuguese.yaml"
    partial = target / "portuguese.yaml.part"
    try:
        partial.write_text(yaml.safe_dump(config, allow_unicode=False), encoding="utf-8")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def main():
    target = Path(__file__).resolve().parents[1] / "voices" / "pocket-tts"
    target.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for filename, (remote_path, expected) in FILES.items():
            path = target / filename
            if path.exists():
                with path.open("rb") as existing:
                    if hashlib.file_digest(existing, "sha256").hexdigest() == expected:
                        print(f"Verified {filename}", flush=True)
                        continue
            partial = target / f"{filename}.part"
            digest = hashlib.sha256()
            try:
                with client.stream("GET", f"{BASE}/{remote_path}") as response:
                    response.raise_for_status()
                    with partial.open("wb") as output:
                        for data in response.iter_bytes():
                            output.write(data)
                            digest.update(data)
                if digest.hexdigest() != expected:
                    raise RuntimeError(f"Checksum mismatch: {filename}")
                partial.replace(path)
            finally:
                partial.unlink(missing_ok=True)
            print(f"Installed {filename}", flush=True)
    write_local_config(target)
    print("Installed Portuguese Pocket TTS with George (24 kHz)", flush=True)


if __name__ == "__main__":
    main()
