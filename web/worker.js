// Runs the Python simulator in a Web Worker through Pyodide and serves JSON RPC calls to bridge.py.
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
const PY_FILES = [
  "simulator.py",
  "elements/__init__.py", "elements/base.py", "elements/wall.py", "elements/detector.py",
  "elements/detector_array.py", "elements/magnetic_field.py", "elements/electric_field.py",
  "elements/quadrupole.py",
  "gui/__init__.py", "gui/fields.py", "gui/config.py",
  "web/bridge.py",
];

importScripts(PYODIDE_URL + "pyodide.js");

async function init() {
  postMessage({ type: "progress", text: "Loading Python runtime…" });
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  postMessage({ type: "progress", text: "Loading numpy…" });
  await pyodide.loadPackage("numpy");
  postMessage({ type: "progress", text: "Loading simulator…" });
  for (const file of PY_FILES) {
    const response = await fetch("../" + file);
    if (!response.ok) throw new Error(`cannot fetch ${file}: ${response.status}`);
    pyodide.FS.mkdirTree("/app/" + file.split("/").slice(0, -1).join("/"));
    pyodide.FS.writeFile("/app/" + file, await response.text());
  }
  pyodide.runPython("import sys; sys.path[:0] = ['/app', '/app/web']");
  return pyodide.pyimport("bridge").call;
}

const ready = init();
ready.then(() => postMessage({ type: "ready" }), (e) => postMessage({ type: "error", text: String(e) }));

onmessage = async ({ data }) => {
  const call = await ready;
  try {
    postMessage({ id: data.id, result: JSON.parse(call(data.fn, JSON.stringify(data.args))) });
  } catch (e) {
    postMessage({ id: data.id, error: String(e) });
  }
};
