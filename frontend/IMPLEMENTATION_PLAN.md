# Live Simulator Implementation Plan

> **For agentic workers:** Implement task-by-task using a test-first workflow. Steps use checkbox syntax for tracking.

**Goal:** Turn the Live Simulator into a safe text-based client for real call sessions.

**Architecture:** Keep active-session and transcript state in a focused `useSimulator` hook. Keep HTTP request/response parsing in a simulator API module, and divide the UI into session setup, status, transcript, and composer components. TanStack Query mutations will make the state-changing calls without retries.

**Tech Stack:** React 19, TypeScript, React Router, TanStack Query, Vite, Tailwind CSS v4, Lucide React.

**Spec:** `C:\Users\Lenovo\.codex\attachments\00013970-785d-4054-acb3-804cbf777bbc\Pasted text.txt`

## Global Constraints

- Modify only `frontend/`; do not modify backend APIs, models, guardrails, or audio/WebSocket code.
- Use real `POST /api/calls` and `POST /api/calls/{session_id}/turn` contracts only.
- Do not retry state-changing mutations or expose credentials.
- Keep transcripts in memory; do not fabricate customer information, responses, state transitions, or records.
- Voice controls remain visibly disabled for a future milestone.
- Protect creation and turn POSTs with synchronous ref locks as well as pending mutation state.
- Validate session and turn responses at runtime before updating local conversation state.
- Treat network failures, timeouts, HTTP 5xx responses, and malformed success payloads as uncertain outcomes.
- Warn before browser refresh or navigation during an active or uncertain session; never persist transcript content.

## Review Focus

- Whitespace-only account IDs must never issue a call-creation request.
- An uncertain session creation must remain locked until the user explicitly acknowledges that a prior backend session might be active.
- Ambiguous network failures must show an unconfirmed result and prevent another turn on the same session.
- HTTP 403/404 validation errors must be human-readable and allow a safe correction or fresh session.
- Repeated Enter presses and clicks while pending must result in one mutation only.
- A completed session must never permit another text submission and must show the backend disposition.

### Task 1: Typed simulator API

**Files:**
- Create: `src/features/simulator/api/simulator-api.ts`
- Create: `src/features/simulator/types/simulator-types.ts`
- Test: frontend test runner configuration and `src/features/simulator/api/simulator-api.test.ts`

**Interfaces:**
- Produces `startConversation(accountId)` and `sendTextTurn(sessionId, text)` returning validated backend data.

- [ ] Write tests for valid JSON parsing, malformed JSON payloads, 4xx validation errors, and conservative uncertain-error classification for transport failures and 5xx responses.
- [ ] Run the tests and observe expected failures before API implementation.
- [ ] Implement typed request helpers with no retries and human-readable error classification.
- [ ] Run API tests and confirm they pass.

### Task 2: Session lifecycle hook

**Files:**
- Create: `src/features/simulator/hooks/use-simulator.ts`
- Test: `src/features/simulator/hooks/use-simulator.test.ts`

**Interfaces:**
- Consumes API functions from Task 1.
- Produces `startSession`, `sendMessage`, `acknowledgeUncertainSession`, `startFreshSession`, transcript entries, state, completion, uncertainty, and mutation status.

- [ ] Write tests for opening-message ordering, state updates, synchronous duplicate locks, completion, uncertain session creation acknowledgement, and uncertain turn locking.
- [ ] Run the tests and observe expected failures.
- [ ] Implement in-memory transcript state using stable IDs, non-retrying TanStack mutations, ref locks, and a warning predicate for active/uncertain sessions.
- [ ] Run hook tests and confirm they pass.

### Task 3: Simulator UI

**Files:**
- Create: `src/features/simulator/components/session-setup.tsx`
- Create: `src/features/simulator/components/conversation-panel.tsx`
- Create: `src/features/simulator/components/message-bubble.tsx`
- Create: `src/features/simulator/components/message-composer.tsx`
- Create: `src/features/simulator/components/session-status.tsx`
- Modify: `src/features/simulator/simulator-page.tsx`
- Modify: `src/index.css`

**Interfaces:**
- Consumes `useSimulator` from Task 2.

- [ ] Write component tests for validation, keyboard behavior, disabled controls, visible completion/hold/error states, uncertain-outcome acknowledgement, and leave-warning behavior.
- [ ] Run tests and observe expected failures.
- [ ] Implement accessible components with a controlled multiline composer, auto-scroll, state badge, hold notice, unconfirmed-outcome messaging, explicit acknowledgement actions, safe fresh-session action, and active-session navigation warning.
- [ ] Run UI tests and confirm they pass.

### Task 4: Full verification

**Files:**
- Modify: only files necessary to fix verification findings.

- [ ] Run `npm run build` and `npm run lint` from `frontend/`.
- [ ] Run the real local backend and frontend, then manually test seeded accounts `ACC-88392` and `ACC-77120`, unknown-account behavior, multiple turns, hold, ending, unavailable-backend handling, and navigation warning behavior.
- [ ] Report actual results and any backend/provider limitation without inventing a workaround.
