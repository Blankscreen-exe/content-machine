// The Voice page's timeline: a strip as long as the video, with the frames along the top
// and the chosen take's waveform below, placed where the render will place it, its
// trimmed parts faded. A playhead marks where the video is; pressing or dragging on the
// strip moves the video there.
(function () {
  const FRAMES_LANE = 26;               // CSS pixels given to the frames along the top
  const GAP = 6;
  const PEAKS_PER_SECOND = 100;

  // The loudest point in each hundredth of a second, worked out once, so drawing never
  // walks through the samples themselves.
  function peaks(buffer) {
    const samples = buffer.getChannelData(0);
    const step = Math.max(1, Math.round(buffer.sampleRate / PEAKS_PER_SECOND));
    const out = new Float32Array(Math.ceil(samples.length / step));
    for (let i = 0; i < out.length; i++) {
      let peak = 0;
      const end = Math.min(samples.length, (i + 1) * step);
      for (let j = i * step; j < end; j++) peak = Math.max(peak, Math.abs(samples[j]));
      out[i] = peak;
    }
    return out;
  }

  // `scenes` and `fps` place the frames; `onSeek(seconds)` is called as the strip is pressed or dragged.
  function create(canvas, { scenes, fps, onSeek }) {
    const context = canvas.getContext("2d");
    const state = { duration: 0, time: 0, take: null, settings: null };

    function fit() {
      const ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      return { width, height };
    }

    function drawFrames(x, ink) {
      context.font = "12px sans-serif";
      context.textBaseline = "middle";
      scenes.forEach((scene, i) => {
        const left = x(scene.from / fps);
        const right = x((scene.from + scene.duration) / fps);
        context.globalAlpha = i % 2 ? 0.08 : 0.16;
        context.fillStyle = ink;
        context.fillRect(left, 0, right - left, FRAMES_LANE);
        context.save();
        context.beginPath();
        context.rect(left, 0, right - left - 4, FRAMES_LANE);
        context.clip();
        context.globalAlpha = 0.85;
        context.fillText(scene.title || `Frame ${i + 1}`, left + 6, FRAMES_LANE / 2);
        context.restore();
      });
    }

    function drawTake(width, height, ink) {
      const top = FRAMES_LANE + GAP;
      const lane = height - top;
      const middle = top + lane / 2;
      context.fillStyle = ink;
      if (!state.take) {
        context.globalAlpha = 0.5;
        context.fillText("No take chosen", 6, middle);
        return;
      }
      const s = state.settings;
      const end = s.trimEnd ?? Infinity;
      const perPixel = state.duration / width;
      for (let px = 0; px < width; px++) {
        // the part of the take under this pixel: at video time v it is at v - offset + trimStart
        const from = px * perPixel - s.offset + s.trimStart;
        const first = Math.max(0, Math.floor(from * PEAKS_PER_SECOND));
        const last = Math.min(state.take.length, Math.ceil((from + perPixel) * PEAKS_PER_SECOND));
        if (first >= last) continue;
        let peak = 0;
        for (let i = first; i < last; i++) peak = Math.max(peak, state.take[i]);
        const heard = from >= s.trimStart && from < end;
        const bar = Math.max(1, Math.min(lane, peak * s.volume * lane));
        context.globalAlpha = heard ? 0.85 : 0.18;
        context.fillRect(px, middle - bar / 2, 1, bar);
      }
    }

    function draw() {
      const { width, height } = fit();
      const ink = getComputedStyle(canvas).color;
      context.clearRect(0, 0, width, height);
      if (!state.duration) return;
      const x = (seconds) => (seconds / state.duration) * width;
      drawFrames(x, ink);
      drawTake(width, height, ink);
      context.globalAlpha = 1;
      context.fillStyle = ink;
      context.fillRect(Math.round(x(state.time)) - 1, 0, 2, height);
    }

    // Anything given replaces what the strip shows, and it is drawn again.
    function update(changes) {
      Object.assign(state, changes);
      draw();
    }

    function seekTo(event) {
      if (!state.duration) return;
      const box = canvas.getBoundingClientRect();
      const share = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
      onSeek(share * state.duration);
    }
    canvas.addEventListener("pointerdown", (event) => {
      canvas.setPointerCapture(event.pointerId);
      seekTo(event);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (canvas.hasPointerCapture(event.pointerId)) seekTo(event);
    });
    new ResizeObserver(draw).observe(canvas);

    return { update };
  }

  window.contentMachine = Object.assign(window.contentMachine || {}, {
    timeline: { create, peaks },
  });
})();
