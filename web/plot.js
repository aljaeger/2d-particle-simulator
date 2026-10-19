// Canvas rendering of the scene and particles; mirrors gui/plot_window.py and visualization.py.
const GRID_N = 5;

function detectorColor(counts, scale) {
  if (!counts) return "rgba(128,128,128,0.3)";
  const level = scale ? Math.min(counts / scale, 1) : 1 - Math.pow(0.7, counts);
  return `rgba(0,153,0,${0.3 + 0.7 * level})`;
}

function niceStep(range) {
  const raw = range / 6;
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  return [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw);
}

class Plot {
  constructor(canvas, onElementClick, setStatus = () => {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onElementClick = onElementClick;
    this.setStatus = setStatus;
    this.scene = null;
    this.track = [];
    this.alive = [];
    this.counts = {};
    this.scales = null;
    this.visible = true;
    this.rectCallback = null;
    this.corner = null;
    this.hover = null;
    this.margin = { left: 40, right: 10, top: 10, bottom: 28 };
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
    canvas.addEventListener("pointerdown", (e) => this.onDown(e));
    canvas.addEventListener("pointermove", (e) => this.onMove(e));
    this.resize();
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const { clientWidth: w, clientHeight: h } = this.canvas.parentElement;
    this.canvas.width = w * dpr;
    this.canvas.height = h * dpr;
    this.canvas.style.width = w + "px";
    this.canvas.style.height = h + "px";
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.width = w;
    this.height = h;
    this.draw();
  }

  setScene(scene) {
    this.scene = scene;
    this.draw();
  }

  setParticles(track, alive, counts, scales, visible) {
    Object.assign(this, { track, alive, counts, scales, visible });
    this.draw();
  }

  // The box is placed by tapping two opposite corners (drag selection does not work on phones).
  startRectangle(callback) {
    this.rectCallback = callback;
    this.corner = null;
    this.hover = null;
    this.canvas.style.cursor = "crosshair";
    this.draw();
  }

  // --- coordinates ---------------------------------------------------------
  updateTransform() {
    const [x0, x1] = this.scene.xlim;
    const [y0, y1] = this.scene.ylim;
    const m = this.margin;
    const w = this.width - m.left - m.right;
    const h = this.height - m.top - m.bottom;
    this.scale = Math.max(Math.min(w / (x1 - x0), h / (y1 - y0)), 1e-9);
    this.ox = m.left + (w - this.scale * (x1 - x0)) / 2;
    this.oy = m.top + (h - this.scale * (y1 - y0)) / 2;
    this.box = { x: this.ox, y: this.oy, w: this.scale * (x1 - x0), h: this.scale * (y1 - y0) };
  }

  toPixel(x, y) {
    return [this.ox + (x - this.scene.xlim[0]) * this.scale,
            this.oy + (this.scene.ylim[1] - y) * this.scale];
  }

  toData(px, py) {
    return [this.scene.xlim[0] + (px - this.ox) / this.scale,
            this.scene.ylim[1] - (py - this.oy) / this.scale];
  }

  mouse(e) {
    const r = this.canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  // --- pointer: tap two corners when an add is pending, otherwise tap to edit --
  onDown(e) {
    if (!this.scene || (e.pointerType === "mouse" && e.button !== 0)) return;
    e.preventDefault();
    const [px, py] = this.mouse(e);
    if (this.rectCallback) {
      if (!this.corner) {
        this.corner = [px, py];
        this.hover = [px, py];
        this.setStatus("Tap the opposite corner");
        this.draw();
      } else this.finishRectangle(px, py);
      return;
    }
    const [x, y] = this.toData(px, py);
    for (const el of [...this.scene.elements].reverse()) {
      if (el.xmin <= x && x <= el.xmax && el.ymin <= y && y <= el.ymax) {
        this.onElementClick(el.index);
        return;
      }
    }
  }

  onMove(e) {
    if (!this.corner) return;
    this.hover = this.mouse(e);
    this.draw();
  }

  // A second tap on (almost) the same spot cancels the placement.
  finishRectangle(px, py) {
    const start = this.corner;
    const callback = this.rectCallback;
    this.rectCallback = this.corner = this.hover = null;
    this.canvas.style.cursor = "";
    this.draw();
    const moved = Math.abs(px - start[0]) > 3 && Math.abs(py - start[1]) > 3;
    callback(moved ? [...this.toData(...start), ...this.toData(px, py)] : null);
  }

  // --- drawing ------------------------------------------------------------
  draw() {
    const ctx = this.ctx;
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, this.width, this.height);
    if (!this.scene) return;
    this.updateTransform();
    this.drawAxes();
    ctx.save();
    ctx.beginPath();
    ctx.rect(this.box.x, this.box.y, this.box.w, this.box.h);
    ctx.clip();
    for (const el of this.scene.elements) this.drawElement(el);
    this.drawStar(...this.toPixel(...this.scene.source), 7);
    if (this.visible) this.drawParticles();
    ctx.restore();
    if (this.corner) {
      const [cx, cy] = this.corner, [hx, hy] = this.hover;
      ctx.save();
      ctx.strokeStyle = "black";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - 6, cy); ctx.lineTo(cx + 6, cy);
      ctx.moveTo(cx, cy - 6); ctx.lineTo(cx, cy + 6);
      ctx.stroke();
      ctx.setLineDash([4, 3]);
      ctx.strokeRect(cx, cy, hx - cx, hy - cy);
      ctx.restore();
    }
  }

  drawAxes() {
    const ctx = this.ctx;
    const { x, y, w, h } = this.box;
    ctx.strokeStyle = "black";
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = "black";
    ctx.font = "11px sans-serif";
    const [x0, x1] = this.scene.xlim;
    const [y0, y1] = this.scene.ylim;
    const sx = niceStep(x1 - x0), sy = niceStep(y1 - y0);
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let v = Math.ceil(x0 / sx) * sx; v <= x1 + 1e-9; v += sx) {
      const [px] = this.toPixel(v, 0);
      ctx.fillRect(px - 0.5, y + h, 1, 4);
      ctx.fillText(+v.toFixed(6), px, y + h + 6);
    }
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let v = Math.ceil(y0 / sy) * sy; v <= y1 + 1e-9; v += sy) {
      const [, py] = this.toPixel(0, v);
      ctx.fillRect(x - 4, py - 0.5, 4, 1);
      ctx.fillText(+v.toFixed(6), x - 6, py);
    }
  }

  rect(el, fill, stroke, lineWidth = 1) {
    const ctx = this.ctx;
    const [px, py] = this.toPixel(el.xmin, el.ymax);
    const w = (el.xmax - el.xmin) * this.scale, h = (el.ymax - el.ymin) * this.scale;
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fillRect(px, py, w, h);
    }
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lineWidth;
      ctx.strokeRect(px, py, w, h);
    }
  }

  drawElement(el) {
    const ctx = this.ctx;
    switch (el.type) {
      case "Wall":
        this.rect(el, "black", "black");
        break;
      case "Detector":
        this.rect(el, detectorColor(this.counts[el.id] || 0, this.scales && this.scales[el.id]), "black");
        break;
      case "DetectorArray":
        for (const cell of el.cells) {
          this.rect(cell, detectorColor(this.counts[cell.id] || 0, this.scales && this.scales[cell.id]), "black");
        }
        this.rect(el, null, "black", 1.5);
        break;
      case "MagneticField":
        this.rect(el, "rgba(255,0,0,0.2)", "rgba(255,0,0,0.2)");
        for (const [x, y] of el.grid) this.marker(...this.toPixel(x, y), el.sign, 8, "red");
        break;
      case "Quadrupole":
        this.rect(el, "rgba(255,140,0,0.2)", "rgba(255,140,0,0.2)");
        for (const [x, y, b] of el.markers) {
          if (b !== 0) this.marker(...this.toPixel(x, y), Math.sign(b), 8 * Math.abs(b), "darkorange");
        }
        break;
      case "ElectricField":
        this.rect(el, "rgba(0,0,255,0.2)", "rgba(0,0,255,0.2)");
        if (el.grid) for (const [x, y] of el.grid) this.arrow(x - el.dx / 2, y - el.dy / 2, el.dx, el.dy);
        break;
      default:
        this.rect(el, "rgba(128,128,128,0.3)", "black");
    }
  }

  // Field direction marker: a cross (into the page) or a circled dot (out of the page).
  marker(px, py, sign, size, color) {
    const ctx = this.ctx;
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1;
    const r = size / 2;
    ctx.beginPath();
    if (sign < 0) {
      ctx.moveTo(px - r * 0.75, py - r * 0.75);
      ctx.lineTo(px + r * 0.75, py + r * 0.75);
      ctx.moveTo(px - r * 0.75, py + r * 0.75);
      ctx.lineTo(px + r * 0.75, py - r * 0.75);
      ctx.stroke();
    } else {
      ctx.arc(px, py, r, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(px, py, Math.max(r / 3, 1), 0, 2 * Math.PI);
      ctx.fill();
    }
  }

  arrow(x, y, dx, dy) {
    const ctx = this.ctx;
    const [ax, ay] = this.toPixel(x, y);
    const [bx, by] = this.toPixel(x + dx, y + dy);
    const angle = Math.atan2(by - ay, bx - ax);
    const head = Math.min(6, Math.hypot(bx - ax, by - ay) / 2);
    ctx.strokeStyle = "blue";
    ctx.fillStyle = "blue";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(bx, by);
    ctx.lineTo(bx - head * Math.cos(angle - 0.4), by - head * Math.sin(angle - 0.4));
    ctx.lineTo(bx - head * Math.cos(angle + 0.4), by - head * Math.sin(angle + 0.4));
    ctx.fill();
  }

  drawStar(px, py, r) {
    const ctx = this.ctx;
    ctx.fillStyle = "black";
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i * Math.PI) / 5;
      const d = i % 2 ? r * 0.4 : r;
      ctx.lineTo(px + d * Math.cos(a), py + d * Math.sin(a));
    }
    ctx.fill();
  }

  drawParticles() {
    const ctx = this.ctx;
    if (!this.track.length) return;
    const n = this.track[0].length;
    ctx.strokeStyle = "black";
    ctx.lineWidth = 0.8;
    for (let p = 0; p < n; p++) {
      ctx.beginPath();
      this.track.forEach((frame, i) => {
        const [px, py] = this.toPixel(frame[p][0], frame[p][1]);
        if (i) ctx.lineTo(px, py);
        else ctx.moveTo(px, py);
      });
      ctx.stroke();
    }
    ctx.fillStyle = "black";
    const last = this.track[this.track.length - 1];
    for (let p = 0; p < n; p++) {
      if (!this.alive[p]) continue;
      const [px, py] = this.toPixel(last[p][0], last[p][1]);
      ctx.beginPath();
      ctx.arc(px, py, 2.5, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
}
