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
const XQ_TOP_FLIP = HEIGHT - BOTTOM;
const XQ_BANK_FLIP = XQ_TOP_FLIP + 4;
const CHESS_TOP_FLIP = XQ_BANK_FLIP + .87;
const CHESS_BOTTOM_FLIP = CHESS_TOP_FLIP + 4;
const XIANGQI_PALETTES = {
  red: {
    marks: ["帥", "車", "炮", "馬", "相", "仕", "兵"],
    shadow: "#956948", fill: "#f8e0b6", outline: "#74342a", ring: "#bb774f", ink: "#762822",
  },
  black: {
    marks: ["將", "車", "砲", "馬", "象", "士", "卒"],
    shadow: "#7c6550", fill: "#eee4cf", outline: "#1e2724", ring: "#586862", ink: "#161d1b",
  },
};
const CHESS_MARKS = {
  white: ["♔", "♕", "♖", "♗", "♘", "♙"],
  black: ["♚", "♛", "♜", "♝", "♞", "♟"],
};
const MARKS = {
  red: ["#ac3542", "#e9869077"], gold: ["#a66326", "#eaba6977"],
  blue: ["#2969ad", "#8cc4f477"], green: ["#236e54", "#8bd5ad77"],
};

export function point(square, flipped = false, mirrorX = false) {
  const row = Math.floor(square / FILES);
  const col = square % FILES;
  if (row < RIVER) {
    const dispCol = mirrorX ? 7 - col : col;
    const dispRow = flipped ? 3 - row : row;
    return [LEFT + dispCol + .5, (flipped ? CHESS_TOP_FLIP : TOP) + dispRow + .5];
  }
  const dispCol = mirrorX ? 8 - col : col;
  const dispRow = flipped ? 8 - row : row - RIVER;
  return [LEFT + dispCol, (flipped ? XQ_TOP_FLIP : BANK) + dispRow];
}

export function at(x, y, flipped = false, mirrorX = false) {
  const col = x - LEFT;
  const chessTop = flipped ? CHESS_TOP_FLIP : TOP;
  if (y >= chessTop && y < chessTop + 4 && col >= 0 && col < 8) {
    const dispRow = Math.floor(y - chessTop);
    const dispCol = Math.floor(col);
    return (flipped ? 3 - dispRow : dispRow) * FILES + (mirrorX ? 7 - dispCol : dispCol);
  }
  const row = y - (flipped ? XQ_TOP_FLIP : BANK);
  if (row >= -.46 && row <= 4.46 && col >= -.47 && col <= 8.47) {
    const dispRow = Math.floor(row + .5);
    const dispCol = Math.floor(col + .5);
    return (flipped ? 8 - dispRow : RIVER + dispRow) * FILES + (mirrorX ? 8 - dispCol : dispCol);
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
    this.frame = {
      cells: [], candidates: new Set(), targets: new Set(), premoves: [], palace: [],
      flipped: false, chessColor: "white", xiangqiColor: "red",
      threatSource: null, threatTargets: new Set(), threatCaptures: new Set(),
    };
    this.highlights = new Map();
    this.arrows = new Map();
    this.gesture = null;
    this.cursor = 4;
    this.keyboard = false;
    this.atlases = {white: new Image(), black: new Image()};
    this.atlases.white.onload = () => this.draw();
    this.atlases.black.onload = () => this.draw();
    this.atlases.white.src = "/assets/western-pieces.png";
    this.atlases.black.src = "/assets/western-pieces-black.png";

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

  isMirrorX(frame = this.frame) {
    return Boolean(frame.flipped) && (frame.chessColor ?? "white") === "black";
  }

  show(frame) {
    if (
      this.frame.revision !== frame.revision
      || Boolean(this.frame.flipped) !== Boolean(frame.flipped)
      || this.isMirrorX(this.frame) !== this.isMirrorX(frame)
    ) {
      this.gesture = null;
    }
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
    const origin = at(x, y, Boolean(this.frame.flipped), this.isMirrorX());
    this.gesture = {id: event.pointerId, button: event.button, origin, x, y, drag: null, hover: origin};
    this.canvas.setPointerCapture(event.pointerId);
  }

  move(event) {
    const [x, y] = this.pointer(event);
    const square = at(x, y, Boolean(this.frame.flipped), this.isMirrorX());
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
    const square = at(...this.pointer(event), Boolean(this.frame.flipped), this.isMirrorX());
    if (g.button === 0) {
      this.callbacks.choose(square, Boolean(g.drag));
    } else if (square !== null && g.origin !== null) {
      if (square === g.origin) {
        if (this.callbacks.cancelPremove(square)) return;
        if (!event.shiftKey && !event.altKey && !event.ctrlKey && this.callbacks.inspectThreat?.(square)) return;
      }
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
    const rowStep = this.frame.flipped ? -1 : 1;
    const colStep = this.isMirrorX() ? -1 : 1;
    let nextRow = row;
    let nextCol = col;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      this.highlights.clear();
      this.arrows.clear();
      this.callbacks.choose(this.cursor, false);
    } else if (event.key === "ArrowUp") nextRow = Math.max(0, Math.min(8, row - rowStep));
    else if (event.key === "ArrowDown") nextRow = Math.max(0, Math.min(8, row + rowStep));
    else if (event.key === "ArrowLeft") nextCol = Math.max(0, col - colStep);
    else if (event.key === "ArrowRight") nextCol = Math.max(0, col + colStep);
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
    const [x, y] = point(square, Boolean(this.frame.flipped), this.isMirrorX());
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
    const flipped = Boolean(this.frame.flipped);
    const mirrorX = this.isMirrorX();
    const [x, y] = point(src, flipped, mirrorX);
    const [endX, endY] = point(dst, flipped, mirrorX);
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
    const chessColor = this.frame.chessColor ?? "white";
    const xiangqiColor = this.frame.xiangqiColor ?? "red";
    if (piece <= 6) {
      const atlas = this.atlases[chessColor] ?? this.atlases.white;
      if (atlas.complete && atlas.naturalWidth) {
        const size = Math.max(24, Math.min(128, 4 * Math.round(this.canvas.width / WIDTH * .94 / 4)));
        const n = (size - 24) / 4;
        const stripY = n * (24 + size - 4) / 2;
        ctx.drawImage(atlas, (piece - 1) * size, stripY, size, size, x - .47, y - .47, .94, .94);
      } else {
        const fallback = CHESS_MARKS[chessColor] ?? CHESS_MARKS.white;
        this.text(fallback[piece - 1], x, y + .02, chessColor === "black" ? "#161d1b" : "#f7f4eb", .76, "Segoe UI Symbol, serif");
      }
      return;
    }
    const palette = XIANGQI_PALETTES[xiangqiColor] ?? XIANGQI_PALETTES.red;
    this.disc(x + .018, y + .054, .386, palette.shadow);
    this.disc(x, y, .385, palette.fill, palette.outline, .04);
    this.disc(x, y, .321, null, palette.ring, .019);
    this.text(palette.marks[piece - 7], x, y + .01, palette.ink, .47, "Microsoft YaHei, Noto Sans CJK SC, serif");
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
    const flipped = Boolean(this.frame.flipped);
    const mirrorX = this.isMirrorX();
    const chessTop = flipped ? CHESS_TOP_FLIP : TOP;
    const riverTop = flipped ? XQ_BANK_FLIP : SHORE;
    const riverBottom = flipped ? CHESS_TOP_FLIP : BANK;
    const xqTop = flipped ? XQ_TOP_FLIP : BANK;
    const xqBottom = flipped ? XQ_BANK_FLIP : BOTTOM;
    const coordinate = "#efe6d1";
    for (let dispRow = 0; dispRow < 4; dispRow++) {
      for (let dispCol = 0; dispCol < 8; dispCol++) {
        ctx.fillStyle = (dispRow + dispCol) % 2 ? "#779582" : "#e7ddbc";
        ctx.fillRect(LEFT + dispCol, chessTop + dispRow, 1, 1);
      }
      this.text(flipped ? 5 + dispRow : 8 - dispRow, LEFT - .34, chessTop + dispRow + .5, coordinate, .20);
    }
    const chessFiles = mirrorX ? "hgfedcba" : "abcdefgh";
    const chessFileY = flipped ? CHESS_BOTTOM_FLIP + .25 : TOP - .25;
    for (let dispCol = 0; dispCol < 8; dispCol++) {
      this.text(chessFiles[dispCol], LEFT + dispCol + .5, chessFileY, coordinate, .20);
    }

    ctx.fillStyle = "#244a50";
    ctx.fillRect(LEFT, riverTop, 8, riverBottom - riverTop);
    this.line(LEFT, flipped ? riverBottom : riverTop, RIGHT, flipped ? riverBottom : riverTop, "#83a39d");
    for (const offset of [.29, .58]) {
      this.line(LEFT + .52, riverTop + offset, LEFT + 3.32, riverTop + offset, "#517c80");
      this.line(RIGHT - 3.32, riverTop + offset, RIGHT - .52, riverTop + offset, "#517c80");
    }
    this.text("SÔNG", WIDTH / 2, riverTop + .43, "#f4e3b7", .24);
    ctx.fillStyle = "#dfba8c";
    ctx.fillRect(LEFT - .40, flipped ? xqTop - .43 : xqTop, 8.8, 4.43);
    const xqFileY = flipped ? xqTop - .60 : xqBottom + .60;
    for (let dispCol = 0; dispCol <= 8; dispCol++) {
      this.line(LEFT + dispCol, xqTop, LEFT + dispCol, xqBottom, "#785639");
      this.text(mirrorX ? dispCol + 1 : 9 - dispCol, LEFT + dispCol, xqFileY, coordinate, .20);
    }
    for (let dispRow = 0; dispRow <= 4; dispRow++) {
      this.line(LEFT, xqTop + dispRow, RIGHT, xqTop + dispRow, "#785639");
      this.text(flipped ? dispRow + 1 : 5 - dispRow, LEFT - .53, xqTop + dispRow, coordinate, .20);
    }
    const palaceTop = flipped ? xqTop : xqTop + 2;
    const palaceBottom = flipped ? xqTop + 2 : xqBottom;
    this.line(LEFT + 3, palaceTop, LEFT + 5, palaceBottom, "#785639");
    this.line(LEFT + 5, palaceTop, LEFT + 3, palaceBottom, "#785639");
    const {
      selection, palace, cells, targets, premoves, last, check, showTargets, planning,
      threatSource, threatTargets, threatCaptures,
    } = this.frame;
    if (palace.length) {
      const [x, y] = point(palace[0], flipped, mirrorX);
      const [farX, farY] = point(palace.at(-1), flipped, mirrorX);
      ctx.strokeStyle = "#225679";
      ctx.lineWidth = .043;
      ctx.strokeRect(
        Math.min(x, farX) - .48, Math.min(y, farY) - .48,
        Math.abs(farX - x) + .96, Math.abs(farY - y) + .96,
      );
    }
    if (last) for (const sq of last.slice(0, 2)) this.mark(sq, "#f5d695ad", "#986525");
    for (const plan of premoves) for (const sq of plan.move.slice(0, 2)) this.mark(sq, "#dec8f7b8", "#6d44a9");
    if (selection != null) this.mark(selection, planning ? "#dec8f7ad" : "#a7d6c3d4", planning ? "#6d44a9" : "#20654f");
    if (check != null) this.mark(check, "#ec8d968c", "#9b2938");
    if (threatSource != null) this.mark(threatSource, "#ee8b7ea8", "#cf3d38", .465);
    for (const [sq, color] of this.highlights) {
      const [stroke, fill] = MARKS[color];
      this.mark(sq, sq === selection || sq === check || sq === threatSource ? null : fill, stroke, .469);
    }
    if (this.keyboard) this.mark(this.cursor, null, "#faf2b7", .493);

    const drag = this.gesture?.drag;
    for (let sq = 0; sq < cells.length; sq++) {
      if (cells[sq] && !(drag && sq === this.gesture.origin)) this.piece(cells[sq], ...point(sq, flipped, mirrorX));
    }
    if (showTargets) for (const sq of targets) {
      const [x, y] = point(sq, flipped, mirrorX);
      if (planning) {
        ctx.setLineDash([.07, .06]);
        this.disc(x, y, .41, null, "#6d44a9", .05);
        ctx.setLineDash([]);
      } else if (cells[sq]) this.disc(x, y, .454, null, "#a02f41", .07);
      else this.disc(x, y, .115, "#1a765d", "#ebf5e4", .026);
    }
    if (threatTargets?.size) for (const sq of threatTargets) {
      const [x, y] = point(sq, flipped, mirrorX);
      if (threatCaptures?.has(sq)) {
        this.disc(x, y, .46, null, "#fff4e6", .08);
        this.disc(x, y, .46, null, "#cf322d", .05);
      } else {
        ctx.setLineDash([.07, .055]);
        this.disc(x, y, .31, null, "#d4453a", .034);
        ctx.setLineDash([]);
        this.disc(x, y, .115, "#d4453a", "#fff4e6", .024);
      }
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
