const FILES = 9;
const RIVER = 4;
const WIDTH = 9.4;
const HEIGHT = 10.24;
const LEFT = .70;
const TOP = .53;
const RIGHT = LEFT + 8;
const SHORE = TOP + 4;
const BANK = SHORE + .87;
const BOTTOM = BANK + 4;
const XIANGQI_MARKS = ["帥", "車", "炮", "馬", "相", "仕", "兵"];
const CHESS_MARKS = ["♚", "♛", "♜", "♝", "♞", "♟"];
const MARKS = {
  red: ["#ac3542", "#e9869077"], gold: ["#a66326", "#eaba6977"],
  blue: ["#2969ad", "#8cc4f477"], green: ["#236e54", "#8bd5ad77"],
};

export function point(square) {
  const row = Math.floor(square / FILES);
  const col = square % FILES;
  return row < RIVER ? [LEFT + col + .5, TOP + row + .5] : [LEFT + col, BANK + row - RIVER];
}

function at(x, y) {
  const col = x - LEFT;
  if (y >= TOP && y < SHORE && col >= 0 && col < 8) return Math.floor(y - TOP) * FILES + Math.floor(col);
  const row = y - BANK;
  if (row >= -.46 && row <= 4.46 && col >= -.47 && col <= 8.47) {
    return (RIVER + Math.floor(row + .5)) * FILES + Math.floor(col + .5);
  }
  return null;
}

function annotationColor(event, arrow) {
  if (event.shiftKey) return "green";
  if (event.altKey) return "blue";
  if (event.ctrlKey) return arrow ? "red" : "gold";
  return arrow ? "gold" : "red";
}

export class BoardView {
  constructor(canvas, callbacks) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.callbacks = callbacks;
    this.frame = {cells: [], candidates: new Set(), targets: new Set(), premoves: [], palace: []};
    this.highlights = new Map();
    this.arrows = new Map();
    this.gesture = null;
    this.cursor = 4;
    this.keyboard = false;
    this.atlas = new Image();
    this.atlas.onload = () => this.draw();
    this.atlas.src = "/assets/western-pieces.png";

    new ResizeObserver(() => this.draw()).observe(canvas);
    canvas.addEventListener("contextmenu", (event) => event.preventDefault());
    canvas.addEventListener("pointerdown", (event) => this.press(event));
    canvas.addEventListener("pointermove", (event) => this.move(event));
    canvas.addEventListener("pointerup", (event) => this.release(event));
    canvas.addEventListener("pointercancel", () => this.cancel());
    canvas.addEventListener("lostpointercapture", () => this.cancel());
    canvas.addEventListener("keydown", (event) => this.key(event));
    canvas.addEventListener("blur", () => { this.keyboard = false; this.draw(); });
  }

  show(frame) {
    if (this.frame.revision !== frame.revision) this.gesture = null;
    this.frame = frame;
    this.draw();
  }

  clear() {
    this.gesture = null;
    this.highlights.clear();
    this.arrows.clear();
    this.draw();
  }

  cancel() {
    if (!this.gesture) return;
    this.gesture = null;
    this.draw();
  }

  pointer(event) {
    const rect = this.canvas.getBoundingClientRect();
    return [(event.clientX - rect.left) * WIDTH / rect.width, (event.clientY - rect.top) * HEIGHT / rect.height];
  }

  press(event) {
    if (this.gesture || (event.button !== 0 && event.button !== 2)) return;
    event.preventDefault();
    this.canvas.focus({preventScroll: true});
    this.keyboard = false;
    if (event.button === 0) this.clear();
    const [x, y] = this.pointer(event);
    const origin = at(x, y);
    this.gesture = {id: event.pointerId, button: event.button, origin, x, y, drag: null, hover: origin};
    this.canvas.setPointerCapture(event.pointerId);
  }

  move(event) {
    const [x, y] = this.pointer(event);
    const square = at(x, y);
    const g = this.gesture;
    if (!g) {
      const {candidates, targets} = this.frame;
      this.canvas.style.cursor = candidates.has(square) || targets.has(square) ? "pointer" : "";
      return;
    }
    if (g.id !== event.pointerId) return;
    if (g.button === 2) {
      if (g.hover !== square) {
        g.hover = square;
        this.draw();
      }
    } else if (this.frame.candidates.has(g.origin) && (g.drag || Math.hypot(x - g.x, y - g.y) > .12)) {
      if (!g.drag) this.callbacks.grab(g.origin);
      g.drag = [x, y];
      this.draw();
    }
  }

  release(event) {
    const g = this.gesture;
    if (!g || g.id !== event.pointerId) return;
    this.gesture = null;
    const square = at(...this.pointer(event));
    if (g.button === 0) {
      this.callbacks.choose(square, Boolean(g.drag));
    } else if (square !== null && g.origin !== null) {
      if (square === g.origin && this.callbacks.cancelPremove(square)) return;
      const arrows = square !== g.origin;
      const marks = arrows ? this.arrows : this.highlights;
      const key = arrows ? g.origin + "/" + square : square;
      const color = annotationColor(event, arrows);
      if (marks.get(key) === color) marks.delete(key);
      else marks.set(key, color);
    }
    this.draw();
  }

  key(event) {
    const row = Math.floor(this.cursor / FILES);
    const col = this.cursor % FILES;
    let nextRow = row;
    let nextCol = col;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      this.highlights.clear();
      this.arrows.clear();
      this.callbacks.choose(this.cursor, false);
    } else if (event.key === "ArrowUp") nextRow = Math.max(0, row - 1);
    else if (event.key === "ArrowDown") nextRow = Math.min(8, row + 1);
    else if (event.key === "ArrowLeft") nextCol = Math.max(0, col - 1);
    else if (event.key === "ArrowRight") nextCol = col + 1;
    else return;
    event.preventDefault();
    nextCol = Math.min(nextRow < RIVER ? 7 : 8, nextCol);
    this.cursor = nextRow * FILES + nextCol;
    this.keyboard = true;
    this.callbacks.focus(this.cursor);
    this.draw();
  }

  line(x1, y1, x2, y2, color, width = .018) {
    const ctx = this.ctx;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  text(value, x, y, fill, size, font = "Segoe UI, system-ui, sans-serif") {
    const ctx = this.ctx;
    ctx.fillStyle = fill;
    ctx.font = "700 " + size + "px " + font;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(value, x, y);
  }

  disc(x, y, radius, fill, stroke, width = .025) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = width; ctx.stroke(); }
  }

  mark(square, fill, stroke, radius = .445) {
    const [x, y] = point(square);
    if (square >= 36) {
      this.disc(x, y, radius, fill, stroke, .046);
    } else {
      const ctx = this.ctx;
      if (fill) { ctx.fillStyle = fill; ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2); }
      ctx.strokeStyle = stroke;
      ctx.lineWidth = .046;
      ctx.strokeRect(x - radius, y - radius, radius * 2, radius * 2);
    }
  }

  arrow(src, dst, color) {
    const [x, y] = point(src);
    const [endX, endY] = point(dst);
    const length = Math.hypot(endX - x, endY - y);
    const dx = (endX - x) / length;
    const dy = (endY - y) / length;
    const tipX = endX - .27 * dx;
    const tipY = endY - .27 * dy;
    const baseX = tipX - .23 * dx;
    const baseY = tipY - .23 * dy;
    const ctx = this.ctx;
    ctx.save();
    ctx.lineCap = "round";
    this.line(x + .24 * dx, y + .24 * dy, baseX, baseY, color, .11);
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(tipX, tipY);
    ctx.lineTo(baseX - .115 * dy, baseY + .115 * dx);
    ctx.lineTo(baseX + .115 * dy, baseY - .115 * dx);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  piece(piece, x, y) {
    const ctx = this.ctx;
    if (piece <= 6) {
      if (this.atlas.complete && this.atlas.naturalWidth) {
        const size = Math.max(24, Math.min(128, 4 * Math.round(this.canvas.width / WIDTH * .94 / 4)));
        const n = (size - 24) / 4;
        const stripY = n * (24 + size - 4) / 2;
        ctx.drawImage(this.atlas, (piece - 1) * size, stripY, size, size, x - .47, y - .47, .94, .94);
      } else {
        this.text(CHESS_MARKS[piece - 1], x, y + .02, "#172a38", .76, "Segoe UI Symbol, serif");
      }
      return;
    }
    this.disc(x + .018, y + .054, .386, "#956948");
    this.disc(x, y, .385, "#f8e0b6", "#74342a", .04);
    this.disc(x, y, .321, null, "#bb774f", .019);
    this.text(XIANGQI_MARKS[piece - 7], x, y + .01, "#762822", .47, "Microsoft YaHei, Noto Sans CJK SC, serif");
  }

  draw() {
    const canvas = this.canvas;
    const ctx = this.ctx;
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = window.devicePixelRatio || 1;
    const width = Math.round(rect.width * ratio);
    const height = Math.round(rect.height * ratio);
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    ctx.setTransform(width / WIDTH, 0, 0, height / HEIGHT, 0, 0);
    ctx.clearRect(0, 0, WIDTH, HEIGHT);
    ctx.fillStyle = "#101a17";
    ctx.fillRect(.11, .10, 9.22, 10.12);
    ctx.fillStyle = "#2a3e35";
    ctx.fillRect(.06, .04, 9.25, 10.10);
    ctx.strokeStyle = "#557564";
    ctx.lineWidth = .02;
    ctx.strokeRect(.12, .10, 9.13, 9.98);
    const coordinate = "#efe6d1";
    for (let row = 0; row < 4; row++) {
      for (let col = 0; col < 8; col++) {
        ctx.fillStyle = (row + col) % 2 ? "#779582" : "#e7ddbc";
        ctx.fillRect(LEFT + col, TOP + row, 1, 1);
      }
      this.text(8 - row, LEFT - .34, TOP + row + .5, coordinate, .20);
    }
    for (let col = 0; col < 8; col++) this.text("abcdefgh"[col], LEFT + col + .5, TOP - .25, coordinate, .20);

    ctx.fillStyle = "#244a50";
    ctx.fillRect(LEFT, SHORE, 8, BANK - SHORE);
    this.line(LEFT, SHORE, RIGHT, SHORE, "#83a39d");
    for (const offset of [.29, .58]) {
      this.line(LEFT + .52, SHORE + offset, LEFT + 3.32, SHORE + offset, "#517c80");
      this.line(RIGHT - 3.32, SHORE + offset, RIGHT - .52, SHORE + offset, "#517c80");
    }
    this.text("SÔNG", WIDTH / 2, SHORE + .43, "#f4e3b7", .24);
    ctx.fillStyle = "#dfba8c";
    ctx.fillRect(LEFT - .40, BANK, 8.8, 4.43);
    for (let col = 0; col <= 8; col++) {
      this.line(LEFT + col, BANK, LEFT + col, BOTTOM, "#785639");
      this.text(9 - col, LEFT + col, BOTTOM + .60, coordinate, .20);
    }
    for (let row = 0; row <= 4; row++) {
      this.line(LEFT, BANK + row, RIGHT, BANK + row, "#785639");
      this.text(5 - row, LEFT - .53, BANK + row, coordinate, .20);
    }
    this.line(LEFT + 3, BANK + 2, LEFT + 5, BOTTOM, "#785639");
    this.line(LEFT + 5, BANK + 2, LEFT + 3, BOTTOM, "#785639");
    const {selection, palace, cells, targets, premoves, last, check, showTargets, planning} = this.frame;
    if (palace.length) {
      const [x, y] = point(palace[0]);
      const [farX, farY] = point(palace.at(-1));
      ctx.strokeStyle = "#225679";
      ctx.lineWidth = .043;
      ctx.strokeRect(x - .48, y - .48, farX - x + .96, farY - y + .96);
    }
    if (last) for (const sq of last.slice(0, 2)) this.mark(sq, "#f5d695ad", "#986525");
    for (const plan of premoves) for (const sq of plan.move.slice(0, 2)) this.mark(sq, "#dec8f7b8", "#6d44a9");
    if (selection != null) this.mark(selection, planning ? "#dec8f7ad" : "#a7d6c3d4", planning ? "#6d44a9" : "#20654f");
    if (check != null) this.mark(check, "#ec8d968c", "#9b2938");
    for (const [sq, color] of this.highlights) {
      const [stroke, fill] = MARKS[color];
      this.mark(sq, sq === selection || sq === check ? null : fill, stroke, .469);
    }
    if (this.keyboard) this.mark(this.cursor, null, "#faf2b7", .493);

    const drag = this.gesture?.drag;
    for (let sq = 0; sq < cells.length; sq++) if (cells[sq] && !(drag && sq === this.gesture.origin)) this.piece(cells[sq], ...point(sq));
    if (showTargets) for (const sq of targets) {
      const [x, y] = point(sq);
      if (planning) {
        ctx.setLineDash([.07, .06]);
        this.disc(x, y, .41, null, "#6d44a9", .05);
        ctx.setLineDash([]);
      } else if (cells[sq]) this.disc(x, y, .454, null, "#a02f41", .07);
      else this.disc(x, y, .115, "#1a765d", "#ebf5e4", .026);
    }
    for (const [key, color] of this.arrows) {
      const [src, dst] = key.split("/").map(Number);
      this.arrow(src, dst, MARKS[color][0]);
    }
    const trace = this.gesture;
    if (trace?.button === 2 && trace.origin != null && trace.hover != null && trace.origin !== trace.hover) {
      this.arrow(trace.origin, trace.hover, "#c48435");
    }
    if (drag && cells[trace.origin]) this.piece(cells[trace.origin], ...drag);
  }
}
