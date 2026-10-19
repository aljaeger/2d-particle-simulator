# Browser version of the interactive interface

`web/` is an alternative to the tkinter interface in `gui/` that runs in a browser, so it can be
embedded in a PowerPoint slide with the Web Viewer add-in. The Python physics (`simulator.py`,
`elements/`) and the dataclass-driven property dialogs (`gui/fields.py`, `gui/config.py`) run
unchanged inside the browser through [Pyodide](https://pyodide.org) in a Web Worker; only the
tkinter/matplotlib layer is replaced by `index.html`, `app.js` and `plot.js`. `bridge.py` is the
Python entry point the worker talks to.

Configurations saved from the browser are the same JSON as `gui_config.json`, so they can be
exchanged with the desktop interface in both directions.

## Running locally

The page must be served over HTTP from the repository root (Web Workers and `fetch` do not work
from `file://`), for example:

    python -m http.server 8000

then open <http://localhost:8000/web/>. The first load fetches the Python runtime and numpy
(about 10 MB) from the jsdelivr CDN; later loads come from the browser cache. The page always
starts from the repository's `gui_config.json`; other configurations can be opened with the
"Load configuration" button, which reads a local file only.

## Hosting

Any static https host that serves the whole repository works, for example GitHub Pages on the
repository (the page fetches `../simulator.py`, `../elements/*.py`, `../gui/fields.py` and
`../gui/config.py` relative to `web/`). The host must allow the page to be shown in an iframe
(GitHub Pages does). Commit the `gui_config.json` you want to present.

## PowerPoint

1. Host the repository as above and note the page URL, e.g.
   `https://<user>.github.io/2d-particle-simulator/web/`.
2. In PowerPoint: Insert → Get Add-ins → search "Web Viewer" → Add.
3. Paste the URL into the Web Viewer pane and press Preview. The add-in stays interactive in
   slideshow mode.
4. Open the slide once before the talk so the runtime is cached, and keep the network connection:
   the add-in itself and the Pyodide CDN need it.

WebAssembly is required, which current Office builds provide (Windows Office renders add-ins with
Edge WebView2).

## Adding an element type

Define it in `elements/` and register it in `elements/__init__.py` and `gui/fields.py` as for the
desktop interface, then add its file to `PY_FILES` in `worker.js`. It gets an "Add" button and a
property dialog automatically; `plot.js` draws unknown types as a grey rectangle until a drawer is
added to `drawElement` (and `element_spec` in `bridge.py` if the drawing needs physics data).
