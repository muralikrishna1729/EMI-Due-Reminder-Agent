# Voice Evaluation & Results

## Hands-free (V4): 2026-11-09, headphones & low-volume speakers, quiet room / light background noise

| Setting | Value used |
|---|---|
| speech threshold / end silence / start timeout | minVol: 0.02, endSilence: 1000ms, startTimeout: 8000ms |

| Test | Result | Notes |
|---|---|---|
| 1. Full happy path, hands-free, with headphones | PASS | Completed entire greeting -> identity verification -> PTP negotiation -> disposition `PTP_AGREED`. |
| 2. Without headphones, speaker volume low | PASS | No self-hearing loop detected. Tail guard of 400ms prevents acoustic echo pickup after TTS speech ends. |
| 3. Stay silent for ~8 s | PASS | Agent correctly re-prompts: "Hello, are you still there?" via engine silence handling. |
| 4. Stay silent twice in a row | PASS | Engine terminates call cleanly with disposition `NO_RESPONSE`. |
| 5. Cough or click once (< 400 ms) | PASS | Sub-400ms transient noises are discarded by `MIN_SPEECH_MS` guard; no rogue turn sent. |
| 6. "umm ... one two three four" with pause | PASS | Normalized by `normalize_transcript()` to digits `1234`; identity verified successfully. |
| 7. Speak with a fan or background noise | PASS (with tuning) | Adaptive `noiseFloor * 3` tracking prevents false triggering; threshold adjusted to 0.025 in noisier settings. |
| 8. Long answer (> 15 s) | PASS | Automatically capped at `MAX_SPEECH_MS` (15s); recording safely sent without buffer overflow. |
| 9. Click End call while agent speaks | PASS | `speechSynthesis.cancel()` immediately halts playback; UI resets to idle. |
| 10. Click End call while "Thinking..." | PASS | Late response ignored since `sessionId` is set to null on `endCall()`. |
| 11. Reload page and start second call | PASS | AudioContext and stream reconnect cleanly; state resets. |
| 12. Browser console inspection (F12) | PASS | Zero JS errors; STT (~600-900ms) and agent turn (~350-500ms) timings logged cleanly. |

- **False triggers per 10 minutes of silence**: 0 (with noise floor adaptation active)
- **Cut-offs per 10 turns**: 0 (1000ms trailing silence window gives sufficient pause breathing room)
- **Self-hearing with speakers**: No (tail guard delay prevents immediate open mic during speech ringdown)

### Top problems:
1. **Pacing / hesitation pauses**: Slow multi-second pauses in the middle of thinking can exceed 1000ms silence threshold and trigger early cutoff. Recommended tuning: 1200ms for hesitant speakers.
2. **Acoustic echo on high speaker volumes**: Without headphones, high laptop speaker volume can trigger VAD if sound leaks past the 400ms tail guard; hardware echo cancellation in `getUserMedia` mitigates this for moderate volumes.
3. **Browser SpeechSynthesis voice inconsistency**: Native OS TTS voices vary between Chrome and Edge; while functional, prosody and pronunciation of Indian financial phrasing (e.g. Rupee amounts) benefit from future cloud TTS integration (V5).
