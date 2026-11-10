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
4. **Wait time mismatch in voice loop**: If a user asks to wait a few minutes, the backend VAD silence timer still triggers at ~8s. Resolved by instructing the agent prompt never to promise multi-minute waits and simply acknowledge "take your time".
5. **Non-chronological date proposals**: LLMs could propose earlier dates when renegotiating. Resolved by prompt instruction enforcing that counter-proposals always progress forward in calendar time.

## V5 implementation status — 2026-11-10

The V5 code has been added on the feature/voice branch. This section records implementation scope only; the browser and microphone checks below have **not** been run in this development environment, so no PASS result is claimed.

| Feature | Implemented behavior | Validation still required |
|---|---|---|
| Voice picker | Lists installed browser voices, ranks likely warm English/India voices, previews them, and remembers the selection in local storage | Choose a voice in the target browser/OS and confirm it sounds better |
| Warmer endings | Warm canned DNC, silence and repeated-abuse closings; retains state-specific PTP/escalation endings | Listen to every call-ending path |
| Customer hold | One 120-second hold per call; no silence turn during the hold; normal re-prompt behavior after expiry | Check speaking during the hold, expiry, and a second hold request |
| Barge-in | Hands-free page monitors microphone level while TTS plays, cancels TTS after sustained speech, and sends the heard character position with the recording | Test with headphones and speakers; check interruption latency and false triggers |
| Interrupted history | Server truncates the latest assistant message at the reported heard position before processing the interruption | Confirm a customer saying "yes" cannot agree to a date that was not spoken |

### V5 manual checks still outstanding

1. Preview several voices in Microsoft Edge and Chrome; choose the preferred voice and reload to confirm persistence.
2. Ask for two minutes to find PAN/birth-year details; confirm the status countdown and that no silence turn is sent during the hold.
3. Speak during the hold; confirm the verification flow continues.
4. Request a second hold; confirm the one-hold limit response.
5. Remain silent for the full hold; confirm re-prompt, then normal no-response termination.
6. Listen to PTP, escalation, wrong-person, DNC, failed-auth, no-response and abuse endings.
7. Interrupt a long agent sentence with headphones; measure how quickly speech stops and confirm the interruption is processed.
8. Repeat interruption with speakers; record the number of false triggers and the conditions.

**No result for interruption success or false-trigger rate is recorded yet.** Those are real microphone/browser observations and must be filled in only after running the checks on the target device.
