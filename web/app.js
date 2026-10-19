// Controls and playback; mirrors gui/controls.py and gui/app.py with the physics in a Web Worker.
const DEFAULT_CONFIG = "../gui_config.json";
const SETTINGS = { T: [10, false], n_steps: [1000, true], steps_per_frame: [5, true], N: [10, true] };

const worker = new Worker("worker.js");
const pending = new Map();
let nextId = 0;

function call(fn, ...args) {
  return new Promise((resolve, reject) => {
    pending.set(nextId, { resolve, reject });
    worker.postMessage({ id: nextId++, fn, args });
  });
}

worker.onmessage = ({ data }) => {
  if (data.type === "progress") setStatus(data.text);
  else if (data.type === "ready") start();
  else if (data.type === "error") setStatus("Failed to load: " + data.text);
  else {
    const p = pending.get(data.id);
    pending.delete(data.id);
    data.error ? p.reject(new Error(data.error)) : p.resolve(data.result);
  }
};

const $ = (id) => document.getElementById(id);
const valid = Object.fromEntries(Object.entries(SETTINGS).map(([k, [d]]) => [k, d]));
let track = [], state = null, playing = false, run = null;

function setStatus(text) {
  $("status").textContent = text;
}

// Parsed positive value of a setting; invalid text keeps the last valid value and turns the box red.
function setting(name) {
  const input = $(name);
  const value = Number(input.value.trim());
  const ok = input.value.trim() !== "" && value > 0 && (!SETTINGS[name][1] || Number.isInteger(value));
  input.classList.toggle("invalid", !ok);
  if (ok) valid[name] = value;
  return valid[name];
}

function settings() {
  const s = Object.fromEntries(Object.keys(SETTINGS).map((k) => [k, setting(k)]));
  return { ...s, loop: $("loop").checked, cumulative: $("cumulative").checked,
           hide_particles: $("hide_particles").checked };
}

function applySettings(s) {
  for (const name of Object.keys(SETTINGS)) if (name in s) $(name).value = String(s[name]);
  $("loop").checked = !!s.loop;
  $("cumulative").checked = !!s.cumulative;
  $("hide_particles").checked = !!s.hide_particles;
}

const dt = () => setting("T") / setting("n_steps");

// --- particle state ----------------------------------------------------------
function apply(result) {
  if (result.frames) track.push(...result.frames);
  else track = [result.pos];
  state = result;
  show();
}

function show() {
  if (!state) return;
  const cumulative = $("cumulative").checked;
  plot.setParticles(track, state.alive, cumulative ? state.cumulative : state.counts,
                    cumulative ? state.scales : null, !$("hide_particles").checked);
  const alive = state.alive.filter(Boolean).length;
  setStatus(`step ${state.step}  t=${(state.step * dt()).toFixed(3)}  alive ${alive}/${state.alive.length}`);
}

async function resample(keepCounts = false) {
  await pause();
  apply(await call("resample", setting("N"), keepCounts));
}

async function reset() {
  await pause();
  apply(await call("reset"));
}

async function step() {
  await pause();
  apply(await call("step", 1, dt(), setting("n_steps")));
}

// --- play / pause (worker computes, main thread draws) ------------------------
function play() {
  playing = true;
  $("play").textContent = "Pause";
  if (!run) run = runLoop().finally(() => { run = null; playing = false; $("play").textContent = "Play"; });
}

async function pause() {
  playing = false;
  if (run) await run;
}

async function runLoop() {
  while (playing) {
    const result = await call("step", setting("steps_per_frame"), dt(), setting("n_steps"));
    apply(result);
    if (result.done) {
      if (!$("loop").checked) break;
      apply(await call("resample", setting("N"), true));
    }
    await new Promise(requestAnimationFrame);
  }
}

async function interrupt() {
  const wasPlaying = playing;
  await pause();
  return wasPlaying;
}

function resume(wasPlaying) {
  const loop = $("loop").checked;
  if (loop && !state.alive.some(Boolean)) {
    call("resample", setting("N"), true).then(apply).then(() => play());
  } else if (wasPlaying || loop) play();
}

// --- generic property dialog (one entry per dataclass field) -------------------
function editDialog(title, values, submit, allowDelete = false) {
  const dialog = $("dialog"), fields = $("fields");
  $("dialog-title").textContent = title;
  $("dialog-error").textContent = "";
  $("delete").hidden = !allowDelete;
  fields.innerHTML = "";
  for (const [name, value] of Object.entries(values)) {
    const label = document.createElement("label");
    label.textContent = name;
    const input = document.createElement("input");
    input.name = name;
    input.value = value;
    fields.append(label, input);
  }
  dialog.showModal();
  return new Promise((resolve) => {
    const finish = (result) => { dialog.close(); resolve(result); };
    $("dialog-form").onsubmit = async (e) => {
      e.preventDefault();
      const strings = Object.fromEntries([...fields.querySelectorAll("input")].map((i) => [i.name, i.value]));
      const error = await submit(strings);
      if (error) $("dialog-error").textContent = error;
      else finish(strings);
    };
    $("cancel").onclick = () => finish(null);
    $("delete").onclick = () => finish("delete");
    dialog.oncancel = (e) => { e.preventDefault(); finish(null); };
  });
}

async function refreshScene() {
  plot.setScene(await call("scene"));
  show();
}

async function addElement(type) {
  const wasPlaying = await interrupt();
  setStatus(`Drag a box for the ${type}`);
  plot.startRectangle(async (corners) => {
    if (corners) {
      const values = await call("new_element_values", type, corners);
      await editDialog(type, values, (strings) => call("add_element", type, strings));
    }
    await refreshScene();
    resume(wasPlaying);
  });
}

async function editElement(index) {
  const wasPlaying = await interrupt();
  const el = plot.scene.elements[index];
  const values = await call("element_values", index);
  const result = await editDialog(el.type, values, (s) => call("update_element", index, s), true);
  if (result === "delete") await call("delete_element", index);
  await refreshScene();
  resume(wasPlaying);
}

async function editSource() {
  const wasPlaying = await interrupt();
  const result = await editDialog("ParticleSource", await call("source_values"), (s) => call("set_source", s));
  if (result) {
    await refreshScene();
    await resample();
  }
  resume(wasPlaying);
}

// --- configuration files -------------------------------------------------------
async function loadConfigText(text) {
  await pause();
  applySettings(await call("load_config", text));
  await refreshScene();
  await resample();
}

async function saveConfig() {
  const text = await call("save_config", settings());
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  a.download = "gui_config.json";
  a.click();
  URL.revokeObjectURL(a.href);
}

// --- startup -------------------------------------------------------------------
const plot = new Plot($("canvas"), editElement);

async function start() {
  for (const type of await call("element_types")) {
    const button = document.createElement("button");
    button.textContent = `Add ${type}`;
    button.onclick = () => addElement(type);
    $("add-buttons").append(button);
  }
  $("edit-source").onclick = editSource;
  $("save").onclick = saveConfig;
  $("load-button").onclick = () => $("load").click();
  $("load").onchange = async (e) => {
    if (e.target.files[0]) await loadConfigText(await e.target.files[0].text());
    e.target.value = "";
  };
  $("play").onclick = () => (playing ? pause() : state.alive.some(Boolean) && play());
  $("step").onclick = step;
  $("reset").onclick = () => reset();
  $("resample").onclick = () => resample();
  $("cumulative").onchange = show;
  $("hide_particles").onchange = show;
  document.querySelectorAll("#controls button, #controls input").forEach((el) => (el.disabled = false));

  // Always start from the repository's saved configuration, like the desktop interface does.
  const response = await fetch(DEFAULT_CONFIG);
  if (response.ok) {
    await loadConfigText(await response.text());
    return;
  }
  await refreshScene();
  await resample();
}
