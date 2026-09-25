// The Voice page: recording a take over the draft, the teleprompter that says what to read
// and when, playing the take lined up with the draft as a render would, and the waveform
// of the chosen take with its trimmed parts shaded.
//
// The server keeps what is saved; this only plays and records. Play with voice reads the
// form as it stands, so a change can be heard before it is saved.
(function () {
  const dataElement = document.getElementById("studio-data");
  if (!dataElement) return;
  const studio = JSON.parse(dataElement.textContent);
  const form = document.getElementById("mix");
  const video = document.getElementById("studio-video");
  const status = document.getElementById("studio-status");

  // Buttons that delete ask first.
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-confirm]");
    if (button && !window.confirm(button.dataset.confirm)) event.preventDefault();
  });

  // ---- the settings, as the form has them now ------------------------------------------

  function number(name, fallback) {
    const value = parseFloat(form.elements[name]?.value);
    return Number.isFinite(value) ? value : fallback;
  }

  function settings() {
    const chosen = form.querySelector('input[name="take"]:checked');
    return {
      take: chosen ? chosen.value : "",
      offset: number("offset", 0),
      trimStart: number("trim_start", 0),
      trimEnd: number("trim_end", null),
      volume: number("volume", 1),
      music: form.elements.music?.value || "",
      musicVolume: number("music_volume", 0.12),
    };
  }

  form.addEventListener("click", (event) => {
    const button = event.target.closest("[data-nudge]");
    if (!button) return;
    const offset = form.elements.offset;
    offset.value = (number("offset", 0) + parseFloat(button.dataset.nudge)).toFixed(2);
    offset.dispatchEvent(new Event("input", { bubbles: true }));
  });

  // ---- waveform of the chosen take -------------------------------------------------------

  const canvas = document.getElementById("waveform");
  let waveform = { take: null, peaks: null, seconds: 0 };

  async function loadWaveform() {
    const take = settings().take;
    if (!canvas || take === waveform.take) return drawWaveform();
    waveform = { take, peaks: null, seconds: 0 };
    if (take) {
      try {
        const bytes = await (await fetch(studio.takeUrls[take])).arrayBuffer();
        const audio = await new AudioContext().decodeAudioData(bytes);
        const samples = audio.getChannelData(0);
        const step = Math.max(1, Math.floor(samples.length / canvas.width));
        const peaks = [];
        for (let x = 0; x < canvas.width; x++) {
          let peak = 0;
          for (let i = x * step; i < (x + 1) * step && i < samples.length; i++) peak = Math.max(peak, Math.abs(samples[i]));
          peaks.push(peak);
        }
        if (waveform.take === take) waveform = { take, peaks, seconds: audio.duration };
      } catch (error) {
        status.textContent = `The waveform of ${take} could not be drawn: ${error.message}`;
      }
    }
    drawWaveform();
  }

  function drawWaveform() {
    if (!canvas) return;
    const context = canvas.getContext("2d");
    const { width, height } = canvas;
    const ink = getComputedStyle(canvas).color;
    context.clearRect(0, 0, width, height);
    if (!waveform.peaks) return;
    context.fillStyle = ink;
    waveform.peaks.forEach((peak, x) => {
      const bar = Math.max(1, peak * height);
      context.fillRect(x, (height - bar) / 2, 1, bar);
    });
    // what the trims leave out is shaded
    const { trimStart, trimEnd } = settings();
    const toX = (seconds) => (seconds / waveform.seconds) * width;
    context.fillStyle = "rgba(128, 128, 128, 0.55)";
    context.fillRect(0, 0, toX(trimStart), height);
    if (trimEnd !== null) context.fillRect(toX(trimEnd), 0, width - toX(trimEnd), height);
  }

  form.addEventListener("input", loadWaveform);
  form.addEventListener("change", loadWaveform);
  loadWaveform();

  if (!video) return;                  // no draft: nothing to read along to or record over

  // ---- teleprompter -------------------------------------------------------------------------

  const nowLine = document.getElementById("teleprompter-now");
  const nextLine = document.getElementById("teleprompter-next");
  let shown = null;                    // the scene whose words are on screen

  function sceneAt(frame) {
    const index = studio.scenes.findIndex((s) => frame >= s.from && frame < s.from + s.duration);
    if (index >= 0) return index;
    return frame < 0 ? 0 : studio.scenes.length - 1;
  }

  function drawTeleprompter() {
    if (!studio.scenes.length) return;
    const frame = Math.floor(video.currentTime * studio.fps);
    const index = sceneAt(frame);
    const scene = studio.scenes[index];
    if (shown !== index) {
      shown = index;
      nowLine.replaceChildren(...scene.script.split(" ").filter(Boolean).map((word) => {
        const span = document.createElement("span");
        span.textContent = word + " ";
        return span;
      }));
      nextLine.textContent = studio.scenes[index + 1]?.script || "";
    }
    // words light up as they would be said, spread over the scene's speech
    const words = nowLine.children;
    const said = scene.speech ? ((frame - scene.from) / scene.speech) * words.length : 0;
    Array.from(words).forEach((span, i) => {
      span.className = i < Math.floor(said) ? "said" : i === Math.floor(said) ? "saying" : "";
    });
  }

  function tick() {
    drawTeleprompter();
    if (!video.paused) requestAnimationFrame(tick);
  }
  video.addEventListener("play", () => requestAnimationFrame(tick));
  video.addEventListener("seeked", drawTeleprompter);
  video.addEventListener("loadedmetadata", drawTeleprompter);

  // ---- playing the take and music lined up with the draft ---------------------------------

  const voiceAudio = new Audio();
  const musicAudio = new Audio();
  musicAudio.loop = true;
  const playing = { voice: null, music: null };   // which file each is set to
  const DRIFT = 0.15;                  // seconds out of step before the take is put back in place

  function load(audio, role, url) {
    if (playing[role] !== url) {
      audio.src = url;
      playing[role] = url;
    }
  }

  function follow() {
    if (video.paused) return;
    const s = settings();
    const t = video.currentTime;
    const at = t - s.offset + s.trimStart;               // where in the take the render would be
    const heard = s.take && t >= s.offset && at >= s.trimStart && (s.trimEnd === null || at < s.trimEnd);
    if (heard) {
      load(voiceAudio, "voice", studio.takeUrls[s.take]);
      voiceAudio.volume = Math.min(1, s.volume);          // a browser cannot play louder than 1
      if (voiceAudio.paused || Math.abs(voiceAudio.currentTime - at) > DRIFT) voiceAudio.currentTime = at;
      if (voiceAudio.paused) voiceAudio.play();
    } else if (!voiceAudio.paused) {
      voiceAudio.pause();
    }
    if (s.music) {
      load(musicAudio, "music", studio.musicUrls[s.music]);
      musicAudio.volume = Math.min(1, s.musicVolume);
      if (musicAudio.paused) musicAudio.play();
    } else if (!musicAudio.paused) {
      musicAudio.pause();
    }
    requestAnimationFrame(follow);
  }

  function stopFollowing() {
    voiceAudio.pause();
    musicAudio.pause();
  }

  const playButton = document.getElementById("play");
  playButton.addEventListener("click", () => {
    if (!video.paused) return video.pause();
    video.muted = true;                // an older render's sound would get in the way
    video.currentTime = 0;
    musicAudio.currentTime = 0;
    video.play().then(() => requestAnimationFrame(follow));
  });
  video.addEventListener("pause", stopFollowing);
  video.addEventListener("ended", stopFollowing);

  // ---- recording a take -----------------------------------------------------------------

  const recordButton = document.getElementById("record");
  const stopButton = document.getElementById("stop");
  const countdown = document.getElementById("studio-countdown");
  const TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

  function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function countDown(from) {
    countdown.hidden = false;
    for (let n = from; n > 0; n--) {
      countdown.textContent = n;
      await wait(1000);
    }
    countdown.hidden = true;
  }

  async function upload(blob) {
    const name = blob.type.includes("mp4") ? "take.m4a" : "take.webm";
    const body = new FormData();
    body.append("take", blob, name);
    status.textContent = "Saving the take...";
    const response = await fetch(studio.uploadUrl, { method: "POST", body });
    if (response.ok) return window.location.reload();
    const answer = await response.json().catch(() => ({}));
    status.textContent = answer.error || `The take could not be saved (${response.status}).`;
    recordButton.disabled = false;
  }

  recordButton.addEventListener("click", async () => {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      status.textContent = "Browsers only allow the microphone at localhost: open this page at localhost on the machine running the app.";
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      status.textContent = `The microphone could not be opened: ${error.message}`;
      return;
    }
    const type = TYPES.find((t) => MediaRecorder.isTypeSupported(t));
    const recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    const chunks = [];
    recorder.addEventListener("dataavailable", (event) => event.data.size && chunks.push(event.data));
    recorder.addEventListener("stop", () => {
      stream.getTracks().forEach((track) => track.stop());
      stopButton.hidden = true;
      upload(new Blob(chunks, { type: recorder.mimeType }));
    });

    recordButton.disabled = true;
    video.pause();
    video.currentTime = 0;
    video.muted = true;
    await countDown(3);
    recorder.start();
    await video.play();
    status.textContent = "Recording. Read along.";
    stopButton.hidden = false;
    const finish = () => recorder.state === "recording" && recorder.stop();
    stopButton.onclick = () => { video.pause(); finish(); };
    video.addEventListener("ended", finish, { once: true });
  });
})();
