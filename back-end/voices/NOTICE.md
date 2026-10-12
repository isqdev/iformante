# Voice used by the Chamada module

Model: Kyutai Pocket TTS, Portuguese, public catalog-only weights, CC-BY-4.0.
Model and license: https://huggingface.co/kyutai/pocket-tts-without-voice-cloning.
Source revision: `575d14372df89a4534bcb989870a34e77544b09f`.

Voice: George, with the state precomputed for the Portuguese model.
Original reference: VCTK `p315_023_enhanced.wav` (English recording), CC-BY-4.0.
Voice catalog and attribution: https://huggingface.co/kyutai/tts-voices.
Output: mono PCM16, 24,000 Hz. Text uses Portuguese model tokenization;
Brazilian numbers, dates and abbreviations are normalized before synthesis.

Runtime: `pocket-tts` 3.3.0, MIT, using PyTorch on CPU.
Source and license: https://github.com/kyutai-labs/pocket-tts.

The installer downloads the Portuguese model, tokenizer and George voice state
from the pinned public model revision. It checks SHA-256 before replacing files
and writes a configuration referencing only those local assets.
Downloaded models and generated configurations are not committed to Git.
