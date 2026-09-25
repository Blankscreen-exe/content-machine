// The Voice page's sound: takes and music decoded whole, and played through Web Audio
// lined up with the video exactly as a render lines them up.
//
// A take recorded in the browser has no index to seek by, so an <audio> element nudged
// into place while playing stalls. A decoded buffer can be started at any point, at a set
// moment on the audio clock, and needs no nudging; a gain can also take it past full
// volume, as a render can.
//
// The output is opened afresh each time playing starts. An audio output stays with the
// device it opened on, and the device can change under the page: a Bluetooth headset is a
// different device while its microphone is in use, and the page reloads just after a
// recording, before Windows has switched it back. An output opened then plays, and the
// tab says so, into a device no one is listening to. Decoding needs no output at all.
(function () {
  let context = null;                   // the output, opened when playing starts
  const decoded = new Map();            // url -> the promise of its decoded audio
  let playing = [];                     // the sources started for this play-through
  // Decodes without opening an output; its rate is the one playback resamples from.
  const decoder = new OfflineAudioContext(1, 1, 48000);

  // Open the output on whatever device is current, for a click that plays: audio may only
  // start from a click. Sources still playing on the old output go with it.
  function wake() {
    stop();
    context?.close();
    context = new AudioContext();
    return context.resume();
  }

  function audio() {
    if (!context) throw new Error("the sound output is opened by pressing Play");
    return context;
  }

  function decode(url) {
    if (!decoded.has(url)) {
      decoded.set(url, fetch(url)
        .then((response) => {
          if (!response.ok) throw new Error(`the server answered ${response.status}`);
          return response.arrayBuffer();
        })
        .then((bytes) => decoder.decodeAudioData(bytes)));
    }
    return decoded.get(url);
  }

  function stop() {
    playing.forEach((source) => source.stop());
    playing = [];
  }

  // Start `buffer` at `when` on the audio clock, from `offset` seconds into it, at `volume`.
  function begin(buffer, when, offset, volume, { duration, loop = false } = {}) {
    const source = audio().createBufferSource();
    const gain = audio().createGain();
    source.buffer = buffer;
    source.loop = loop;
    gain.gain.value = volume;
    source.connect(gain).connect(audio().destination);
    if (duration === undefined) source.start(when, offset);
    else source.start(when, offset, duration);
    playing.push(source);
  }

  // Play from video time `t`, as a render would: at video time v the take is at
  // v - offset + trimStart, heard from trimStart until trimEnd; the music loops from 0.
  function start({ voice, music }, settings, t) {
    stop();
    const now = audio().currentTime;
    if (voice) {
      const from = settings.trimStart + Math.max(0, t - settings.offset);
      const end = Math.min(settings.trimEnd ?? voice.duration, voice.duration);
      if (from < end) {
        begin(voice, now + Math.max(0, settings.offset - t), from, settings.volume, { duration: end - from });
      }
    }
    if (music) begin(music, now, t % music.duration, settings.musicVolume, { loop: true });
  }

  window.contentMachine = Object.assign(window.contentMachine || {}, {
    sound: { wake, decode, start, stop },
  });
})();
