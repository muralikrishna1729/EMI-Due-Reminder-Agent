// Browser text-to-speech helpers. Voice selection stays on this device.
const WARM_NAMES = [
  "neerja", "swara", "heera", "aria", "jenny", "zira",
  "sonia", "samantha", "veena", "priya", "libby", "female"
];

function scoreVoice(voice) {
  const name = (voice.name || "").toLowerCase();
  let score = 0;
  if (voice.lang === "en-IN") score += 30;
  else if ((voice.lang || "").toLowerCase().startsWith("en")) score += 10;
  else score -= 50;
  if (/natural|neural|online/i.test(name)) score += 25;
  if (WARM_NAMES.some((candidate) => name.includes(candidate))) score += 15;
  if (voice.localService === false) score += 3;
  return score;
}

function readSavedVoice() {
  try { return localStorage.getItem("emiVoice") || ""; }
  catch (_) { return ""; }
}

function saveVoice(name) {
  try { localStorage.setItem("emiVoice", name); }
  catch (_) { /* Voice selection still works for this page session. */ }
}

function initVoicePicker(select, previewBtn) {
  if (!select) return;

  const fill = () => {
    const voices = speechSynthesis.getVoices()
      .slice()
      .sort((a, b) => scoreVoice(b) - scoreVoice(a));
    if (!voices.length) return;

    const saved = readSavedVoice();
    select.textContent = "";
    voices.forEach((voice) => {
      const option = document.createElement("option");
      option.value = voice.name;
      option.textContent = voice.name + " (" + voice.lang + ")";
      select.appendChild(option);
    });

    const selected = voices.some((voice) => voice.name === saved)
      ? saved
      : voices[0].name;
    select.value = selected;
    saveVoice(selected);
  };

  fill();
  if (typeof speechSynthesis.addEventListener === "function") {
    speechSynthesis.addEventListener("voiceschanged", fill);
  } else {
    speechSynthesis.onvoiceschanged = fill;
  }
  select.addEventListener("change", () => saveVoice(select.value));

  if (previewBtn) {
    previewBtn.addEventListener("click", () => {
      speakText("Hello, this is a quick voice preview. I hope this sounds friendly to you.");
    });
  }
}

// Returns { cancel(), spokenChars() }. onDone receives { cancelled }.
function speakText(text, options) {
  const settings = options || {};
  const rate = settings.rate === undefined ? 0.95 : settings.rate;
  const pitch = settings.pitch === undefined ? 1.05 : settings.pitch;

  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  const select = document.getElementById("voice");
  const selectedVoice = speechSynthesis.getVoices()
    .find((voice) => select && voice.name === select.value);

  if (selectedVoice) {
    utterance.voice = selectedVoice;
    utterance.lang = selectedVoice.lang;
  } else {
    utterance.lang = "en-IN";
  }
  utterance.rate = rate;
  utterance.pitch = pitch;

  let startedAt = 0;
  let spoken = 0;
  let cancelled = false;
  let finished = false;
  let guard = null;

  const finish = () => {
    if (finished) return;
    finished = true;
    if (guard !== null) clearTimeout(guard);
    if (settings.onDone) settings.onDone({ cancelled: cancelled });
  };

  utterance.onstart = () => {
    startedAt = performance.now();
    if (settings.onStart) settings.onStart();
  };
  utterance.onboundary = (event) => {
    if (typeof event.charIndex === "number") spoken = event.charIndex;
  };
  utterance.onend = finish;
  utterance.onerror = finish;

  speechSynthesis.speak(utterance);
  guard = setTimeout(finish, 4000 + text.length * 160);

  return {
    cancel() {
      if (finished) return;
      cancelled = true;
      if (guard !== null) clearTimeout(guard);
      speechSynthesis.cancel();
      finish();
    },
    spokenChars() {
      if (spoken > 0) return spoken;
      if (!startedAt) return 0;
      const estimate = ((performance.now() - startedAt) / 1000) * 14 * rate;
      return Math.min(text.length, Math.round(estimate));
    }
  };
}
