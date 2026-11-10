# Voice experience decisions

Updated: 2026-11-10

## V5 defaults

| Decision | Choice | Reason |
|---|---|---|
| Browser voice | Let the user preview and select an available browser voice | Voice quality depends on the browser and operating system |
| Preferred voice ranking | Prefer English (India), voices marked Natural/Neural/Online, and likely warm voice names | Sensible starting order; the user makes the final choice |
| Voice preference storage | Save the selected browser voice name in local storage | Preference stays on the same browser/device |
| Speech rate and pitch | Start at rate 0.95 and pitch 1.05 | Slightly slower, softer default; some voices ignore pitch |
| Hold duration | 120 seconds | Enough time to find PAN/birth-year details without keeping the session open indefinitely |
| Holds per call | One | Prevents an unbounded wait loop |
| Second hold request | "I'm sorry, I can only wait once during a call. Shall we continue now?" | The agent must not silently extend the hold |
| Callback | Not supported in V5 | No scheduler, calling-hour policy, or callback state exists yet |
| Barge-in | Enabled by default in hands-free mode; headphones recommended | Browser microphone volume detection is a best-effort interruption mechanism |
| Neural server TTS | Deferred | Try the built-in browser voice picker first; avoid sending customer text to another speech provider |

## Hold expiry

The voice page waits for up to 120 seconds without sending silence turns. If the customer speaks, the conversation continues normally. If the hold expires, the page sends a silence turn and then follows the existing re-prompt/second-silence termination behavior.

A callback must not be promised until a real scheduler, customer consent, calling-hour checks, and a durable callback status are implemented.
