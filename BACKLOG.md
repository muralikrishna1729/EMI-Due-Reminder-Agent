# Voice experience backlog

- [ ] Add a callback scheduler with explicit customer consent, calling-hour rules, retry limits, and a durable callback-requested status. Do not promise callbacks until this exists.
- [ ] Add a server-side customer-ended disposition/API so a manual browser End Call also closes the backend session.
- [ ] Add audio pre-roll buffering so the first syllable is not lost when VAD detects speech or barge-in.
- [ ] Evaluate stronger acoustic echo cancellation/full-duplex audio; current browser volume-based barge-in can false-trigger with speakers.
- [ ] Add automated browser tests for voice-picker persistence, hold countdown, microphone lifecycle, and interruption behavior.
- [ ] Add more language-specific STT/TTS configuration and verify Hindi/Hinglish voice behavior.
- [ ] Consider server-side neural TTS only if the browser voice picker does not meet voice-quality needs; review provider terms and data handling first.
