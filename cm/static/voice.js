// The Voice page: the draft with a transport and a timeline under it, the teleprompter that
// says what to read and when, and recording a take over the draft.
//
// The server keeps what is saved; this only plays and records. Playback reads the form as
// it stands, so a change can be heard before it is saved. The sound itself is
// studio_sound.js; the strip under the video is studio_timeline.js.
(function () {
  const dataElement = document.getElementById("studio-data");
  if (!dataElement) return;
  const studio = JSON.parse(dataElement.textContent);
  const { sound, timeline: timelines } = window.contentMachine;
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

  if (!video) return;                  // no draft: nothing to play, read along to, or record over

  // ---- the sound for the settings as they stand -------------------------------------------

  function loadSound(s) {
    return Promise.all([
      s.take ? sound.decode(studio.takeUrls[s.take]) : null,
      s.music ? sound.decode(studio.musicUrls[s.music]) : null,
    ]).then(([voice, music]) => ({ voice, music }));
  }

  // Start the sound again from where the video is, if it is playing: after a seek, or a
  // change of offset, trim or volume, so lining up can be done by ear.
  function restartSound() {
    if (video.paused) return;
    const s = settings();
    loadSound(s).then((buffers) => { if (!video.paused) sound.start(buffers, s, video.currentTime); });
  }

  // ---- timeline -------------------------------------------------------------------------

  let recording = false;
  const strip = timelines.create(document.getElementById("timeline"), {
    scenes: studio.scenes,
    fps: studio.fps,
    onSeek: (seconds) => { if (!recording) video.currentTime = seconds; },
  });
  let shownTake = null;

  function showSettings() {
    const s = settings();
    strip.update({ settings: s });
    if (s.take === shownTake) return;
    shownTake = s.take;
    strip.update({ take: null });
    if (!s.take) return;
    sound.decode(studio.takeUrls[s.take])
      .then((buffer) => { if (shownTake === s.take) strip.update({ take: timelines.peaks(buffer) }); })
      .catch((error) => { status.textContent = `${s.take} could not be read: ${error.message}`; });
  }

  form.addEventListener("input", () => { showSettings(); restartSound(); });
  form.addEventListener("change", () => { showSettings(); restartSound(); });
  video.addEventListener("loadedmetadata", () => strip.update({ duration: video.duration }));
  if (video.readyState >= 1) strip.update({ duration: video.duration });
  showSettings();

  // ---- teleprompter -----------------------------------------------------------------------

  const nowLine = document.getElementById("teleprompter-now");
  const nextLine = document.getElementById("teleprompter-next");
  let shownScene = null;

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
    if (shownScene !== index) {
      shownScene = index;
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

  // ---- transport ----------------------------------------------------------------------------

  const playButton = document.getElementById("play");
  const startButton = document.getElementById("to-start");
  const clock = document.getElementById("clock");

  function time(seconds) {
    const whole = Math.max(0, seconds || 0);
    return `${Math.floor(whole / 60)}:${(whole % 60).toFixed(1).padStart(4, "0")}`;
  }

  function showTime() {
    clock.textContent = `${time(video.currentTime)} / ${time(video.duration)}`;
    strip.update({ time: video.currentTime });
    drawTeleprompter();
  }

  function tick() {
    showTime();
    if (!video.paused) requestAnimationFrame(tick);
  }

  async function play() {
    sound.wake();                      // audio may only start from a click, so ask now
    const s = settings();
    status.textContent = "Loading the sound...";
    let buffers;
    try {
      buffers = await loadSound(s);
    } catch (error) {
      status.textContent = `The sound could not be loaded: ${error.message}`;
      return;
    }
    status.textContent = "";
    video.muted = true;                // an older render's sound would get in the way
    if (video.ended) video.currentTime = 0;
    await video.play();
    sound.start(buffers, s, video.currentTime);
  }

  playButton.addEventListener("click", () => (video.paused ? play() : video.pause()));
  startButton.addEventListener("click", () => { video.currentTime = 0; });
  document.addEventListener("keydown", (event) => {
    if (event.key !== " " || recording || event.target.closest("input, select, textarea, button")) return;
    event.preventDefault();            // the space bar plays and pauses, rather than scrolling
    playButton.click();
  });

  video.addEventListener("play", () => { playButton.textContent = "Pause"; requestAnimationFrame(tick); });
  video.addEventListener("pause", () => { playButton.textContent = "Play"; sound.stop(); showTime(); });
  video.addEventListener("seeking", sound.stop);
  video.addEventListener("seeked", () => { showTime(); if (!recording) restartSound(); });
  video.addEventListener("loadedmetadata", showTime);

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

  function lockTransport(locked) {
    recording = locked;
    [playButton, startButton].forEach((button) => { button.disabled = locked; });
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
    lockTransport(false);
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
    lockTransport(true);
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
