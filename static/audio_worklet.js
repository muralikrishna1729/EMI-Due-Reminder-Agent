class PCMProcessor extends AudioWorkletProcessor {
  frameCounter = 0; // absolute frame index (per-sample)

  constructor() {
    super();
    // Ensure all output channels are silent initially
    for (let i = 0; i < this.output.length; i++) {
      this.output[i].fill(0);
    }
  }

  process(inputs, outputs, parameters) {
    // Silence all output channels first
    for (let i = 0; i < this.output.length; i++) {
      const channel = this.output[i];
      for (let j = 0; j < channel.length; j++) {
        channel[j] = 0;
      } // close inner for
    } // close outer for

    // No audio input? Keep alive.
    if (!inputs || !inputs[0]) {
      return true;
    }

    const input = inputs[0];
    const channelCount = input.length; // number of Float32Array channels
    const frameCount = input[0].length; // samples per channel (assume same length for all channels)

    // Down-mix to mono (average across channels)
    const mono = new Float32Array(frameCount);
    for (let i = 0; i < frameCount; i++) {
      let sum = 0;
      for (let c = 0; c < channelCount; c++) {
        sum += input[c][i];
      }
      const sample = sum / channelCount; // average per-sample
      const x = Math.max(-1, Math.min(1, sample)); // clamp to [-1, 1]

      const scaled = x < 0 ? Math.round(x * 32768) : Math.round(x * 32767);
      const clipped = Math.max(-32768, Math.min(32767, scaled));
      mono[i] = clipped;
    } // close for (i) loop

    // Check if the audio is non-silent (simple threshold)
    const isSpeech = mono.reduce((sum, val) => sum + Math.abs(val), 0) > 100;

    // Capture start frame index, then advance the global frame counter
    const startFrame = this.frameCounter;
    this.frameCounter += mono.length; // advance by the number of frames in this block

    // If speech is detected, send a preroll_start message
    if (isSpeech) {
      const prerollBlock = new Uint8Array(4); // just the frame index, no PCM data
      const prerollView = new DataView(prerollBlock.buffer);
      prerollView.setUint32(0, startFrame, true); // little-endian frame index

      this.port.postMessage({ type: "preroll_start", startFrame: startFrame, endFrame: startFrame + 6000 }, [prerollBlock.buffer]);
    }

    // Build a transferable block: 4-byte frame index + Int16 PCM data
    const block = new Uint8Array(4 + mono.length * 2);
    const view = new DataView(block.buffer);
    view.setUint32(0, startFrame, true); // little-endian frame index

    let offset = 4;
    for (let i = 0; i < mono.length; i++) {
      const int16 = mono[i];
      view.setInt16(4 + i * 2, int16, true);
    }

    // Transfer the underlying ArrayBuffer (not the Uint8Array itself)
    this.port.postMessage(block, [block.buffer]);
    return true; // keep processor alive
  } // close function

  registerProcessor('pcm-processor', PCMProcessor);
}