"""Download the pinned Brazilian medium voice; verify before replacing local files."""
import hashlib
from pathlib import Path

import httpx

REVISION = "2f8dbe0"
BASE = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/pt/pt_BR/faber/medium"
FILES = {
    "pt_BR-faber-medium.onnx": "e0724a2f07965f6523d2a1e96b488a4c",
    "pt_BR-faber-medium.onnx.json": "b6c2c4e9755d9bd92485a65d4070cb2f",
}


def main():
    target = Path(__file__).resolve().parents[1] / "voices"
    target.mkdir(exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for filename, expected in FILES.items():
            path = target / filename
            if path.exists() and hashlib.md5(path.read_bytes()).hexdigest() == expected:
                print(f"Verified {filename}")
                continue
            partial = target / f"{filename}.part"
            digest = hashlib.md5()
            try:
                with client.stream("GET", f"{BASE}/{filename}") as response:
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
            print(f"Installed {filename}")


if __name__ == "__main__":
    main()
