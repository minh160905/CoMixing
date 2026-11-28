import {BoardView} from "./board.mjs";

const $ = (id) => document.getElementById(id);
const rows = $("move-log");
const promotion = $("promotion");
const games = new Map();
const setups = new Map();
const settings = {
  rules: "classic", mode: "local", human: 0, seconds: 3,
  chessColor: "white", xiangqiColor: "red",
};
const promotionIcons = {
  white: {"2": "♕", "3": "♖", "4": "♗", "5": "♘"},
  black: {"2": "♛", "3": "♜", "4": "♝", "5": "♞"},
};
const WK = 1;
const WQ = 2;
const WR = 3;
const XK = 7;
const XE = 11;
const XA = 12;
const FILES = 9;
const RIVER = 4;
const SIZE = 81;
const START_CELLS = (() => {
  const c = new Array(SIZE).fill(0);
  [3, 5, 4, 2, 1, 4, 5, 3].forEach((p, col) => { c[col] = p; });
  for (let col = 0; col < 8; col++) c[FILES + col] = 6;
  [8, 10, 11, 12, 7, 12, 11, 10, 8].forEach((p, col) => { c[8 * FILES + col] = p; });
  c[6 * FILES + 1] = 9;
  c[6 * FILES + 7] = 9;
  for (const col of [0, 2, 4, 6, 8]) c[5 * FILES + col] = 13;
  return c;
})();
const XIANGQI_PALETTE_STYLE = {
  red: {marks: ["帥", "車", "炮", "馬", "相", "仕", "兵"], fill: "#f8e0b6", outline: "#74342a", ink: "#762822"},
  black: {marks: ["將", "車", "砲", "馬", "象", "士", "卒"], fill: "#eee4cf", outline: "#1e2724", ink: "#161d1b"},
};
const validPieceColors = (chessColor, xiangqiColor) => !(chessColor === "black" && xiangqiColor === "black");
const boardFlipped = () => settings.mode === "bot" && settings.human === 0;
const validSquare = (sq) => sq !== null && sq >= 0 && sq < SIZE && (Math.floor(sq / FILES) >= RIVER || sq % FILES < 8);
const insidePalace = (sq) => {
  const r = Math.floor(sq / FILES);
  const c = sq % FILES;
  return r >= 6 && c >= 3 && c <= 5;
};

let config = null;
let active = null;
let retry = null;
let error = "";
let notice = "";
let selection = null;
let threatSource = null;
let pending = [];
let logGame = null;
const practice = {active: false, cells: START_CELLS.slice(), turn: 1, brush: WQ, cannonOpen: true, serverError: ""};
let paletteDrag = null;

const current = () => games.get(settings.rules);
const records = (game = current()) => game?.records ?? [];
const history = (game = current()) => records(game).map(({move}) => move);
const sameMove = (a, b) => a[0] === b[0] && a[1] === b[1] && a[2] === b[2];
const botTurn = (game = current()) => !practice.active && settings.mode === "bot" && game && !game.outcome && game.turn !== settings.human;
const opponentSide = (game = current()) => (settings.mode === "bot" ? 1 - settings.human : (game ? 1 - game.turn : null));
const castleFor = (move) => config.castles.find((castle) => sameMove(castle.move, move));

const board = new BoardView($("board"), {
  choose,
  grab(square) {
    if (input().candidates.has(square)) {
      threatSource = null;
      selection = square;
      render();
    }
  },
  cancelPremove(square) {
    if (!pending.some(({move}) => move[0] === square || move[1] === square)) return false;
    clearSelection();
    notice = "Đã hủy PreMove.";
    render();
    return true;
  },
  inspectThreat(square) {
    const game = current();
    const opp = opponentSide(game);
    const piece = game?.cells[square];
    if (game && config && piece && config.sideByPiece[piece] === opp) {
      threatSource = threatSource === square ? null : square;
      render();
      return true;
    }
    if (threatSource !== null) {
      threatSource = null;
      render();
    }
    return false;
  },
  editClick(square) {
    if (!practice.active || !validSquare(square)) return;
    placePracticePiece(square, practice.brush);
  },
  editDrop(origin, target) {
    if (!practice.active || !validSquare(origin)) return;
    const piece = practice.cells[origin];
    if (!piece) return;
    practice.serverError = "";
    if (!validSquare(target)) {
      practice.cells[origin] = 0;
    } else if (target !== origin) {
      practice.cells[origin] = 0;
      practice.cells[target] = piece;
    }
    render();
  },
  editDelete(square) {
    if (!practice.active || !validSquare(square) || !practice.cells[square]) return;
    practice.serverError = "";
    practice.cells[square] = 0;
    render();
  },
  focus(square) {
    if (!config) return;
    const piece = input().cells[square];
    const side = config.sideByPiece[piece];
    $("square-info").textContent = config.coords[square] + (piece ? ", " + config.pieces[piece] + " " + config.sides[side] : ", trống");
  },
});

function project(game) {
  const cells = game.cells.slice();
  let rights = game.rights;
  for (const {piece, move} of pending) {
    const [src, dst, promoted] = move;
    if (cells[src] !== piece) break;
    if (piece === WK) rights = 0;
    for (const castling of config.castles) {
      if ([src, dst].includes(castling.rook[0]) && cells[castling.rook[0]] === WR) rights &= ~castling.right;
    }
    cells[src] = 0;
    cells[dst] = promoted || piece;
    const castle = piece === WK && castleFor(move);
    if (castle) {
      cells[castle.rook[0]] = 0;
      cells[castle.rook[1]] = WR;
    }
  }
  return {cells, rights};
}

function speculativeMoves(cells, rights, src) {
  const piece = cells[src];
  const balancedKing = piece === WK && settings.rules === "balanced";
  const insidePalace = (sq) => config.palace.includes(sq);
  if (balancedKing && !insidePalace(src)) return [];
  const moves = config.geometry[piece][src]
    .filter(([dst]) => !balancedKing || insidePalace(dst))
    .map(([dst, promotion]) => [src, dst, promotion]);
  if (piece === WK) for (const castle of config.castles) {
    if (castle.move[0] === src && (rights & castle.right) && cells[castle.rook[0]] === WR
        && (!balancedKing || insidePalace(castle.move[1]))) moves.push(castle.move);
  }
  return moves;
}

function input() {
  const game = current();
  const candidates = new Set();
  const planning = Boolean(game && active?.action === "bot" && $("enable-premove").checked);
  const frame = {cells: game?.cells ?? [], moves: [], candidates, side: null, planning};
  if (!game || game.outcome) return frame;
  if (planning) {
    const {cells, rights} = project(game);
    frame.cells = cells;
    if (pending.length >= config.maxPremoves) return frame;
    frame.side = settings.human;
    for (let sq = 0; sq < cells.length; sq++) if (config.sideByPiece[cells[sq]] === frame.side) candidates.add(sq);
    if (candidates.has(selection)) frame.moves = speculativeMoves(cells, rights, selection);
  } else if (!active && !botTurn(game)) {
    frame.side = game.turn;
    for (const move of game.legal) candidates.add(move[0]);
    frame.moves = game.legal.filter(([src]) => src === selection);
  }
  return frame;
}

function clearSelection() {
  pending = [];
  selection = null;
  threatSource = null;
  notice = "";
}

function choose(square, dragged) {
  const frame = input();
  if (threatSource !== null) {
    threatSource = null;
    if (frame.side === null) {
      render();
      return;
    }
  }
  if (frame.side === null) return;
  const own = square !== null && config.sideByPiece[frame.cells[square]] === frame.side;
  const choices = frame.moves.filter((move) => move[1] === square);
  if (choices.length && (dragged || !frame.planning || !own)) {
    if (choices.length > 1) choosePromotion(choices, frame);
    else applyChoice(choices[0], frame);
    return;
  }
  selection = !dragged && own && selection !== square ? square : null;
  notice = "";
  render();
}

function applyChoice(move, frame) {
  if (frame.planning) {
    pending.push({piece: frame.cells[move[0]], move});
    selection = null;
    notice = "";
    render();
  } else {
    request("move", history(), move);
  }
}

function choosePromotion(choices, frame) {
  $("promotion-choices").replaceChildren(...choices.map((move) => {
    const button = document.createElement("button");
    const icon = document.createElement("span");
    button.type = "button";
    icon.className = "promotion-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = promotionIcons[settings.chessColor][move[2]];
    button.append(icon, config.pieces[move[2]]);
    button.addEventListener("click", () => {
      promotion.close();
      applyChoice(move, frame);
    });
    return button;
  }));
  promotion.showModal();
}

async function responseJSON(response) {
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload) throw new Error(payload?.error ?? "Máy chủ chưa phản hồi được. Hãy thử lại.");
  return payload;
}

function cancelRequest() {
  const old = active;
  active = null;
  old?.controller.abort();
  error = "";
  retry = null;
}

async function request(action, moves, move = null, customSetup = undefined) {
  if (active) return;
  const setup = customSetup === undefined ? setups.get(settings.rules) ?? null : customSetup;
  const task = {action, rules: settings.rules, controller: new AbortController()};
  active = task;
  error = "";
  notice = "";
  retry = null;
  render();
  try {
    const body = {action, rules: task.rules, history: moves, move, seconds: settings.seconds};
    if (setup) body.setup = setup;
    const response = await fetch("/api/game", {
      method: "POST", headers: {"Content-Type": "application/json"},
      signal: task.controller.signal,
      body: JSON.stringify(body),
    });
    const next = await responseJSON(response);
    if (active !== task) return;
    if (action === "bot" && promotion.open) {
      await new Promise((done) => promotion.addEventListener("close", done, {once: true}));
    }
    if (active !== task) return;
    if (setup) setups.set(task.rules, setup);
    else setups.delete(task.rules);
    games.set(task.rules, next);
    active = null;
    selection = null;
    threatSource = null;
    if (practice.active && customSetup) {
      practice.active = false;
      practice.serverError = "";
    }
    if (next.outcome) pending = [];
    if (action === "bot" && pending.length) {
      const entry = pending.shift();
      if (next.cells[entry.move[0]] === entry.piece && next.legal.some((move) => sameMove(move, entry.move))) {
        return request("move", history(next), entry.move);
      }
      pending = [];
      notice = "Đã hủy PreMove vì nước đi không còn hợp lệ.";
    }
    render();
    runBot();
  } catch (failure) {
    if (active !== task) return;
    active = null;
    pending = [];
    selection = null;
    const msg = failure instanceof TypeError ? "Không kết nối được với máy chủ." : failure.message;
    if (practice.active && customSetup) {
      practice.serverError = msg;
      render();
      return;
    }
    error = msg;
    retry = () => request(action, moves, move, customSetup);
    render();
  }
}

function runBot() {
  if (config && !active && !error && botTurn()) request("bot", history());
}

function undoCount(game) {
  const moves = records(game);
  if (!moves.length) return 0;
  if (settings.mode !== "bot" || config.sideByPiece[moves.at(-1).piece] === settings.human) return 1;
  return moves.length > 1 ? 2 : 0;
}

function renderHistory(game) {
  if (logGame === game) return;
  logGame = game;
  const moves = records(game);
  $("move-count").textContent = moves.length + " nước";
  $("empty-log").hidden = moves.length > 0;
  rows.replaceChildren(...moves.map((item, index) => {
    const [src, dst, promotion] = item.move;
    let text = item.castle ? (dst < src ? "Nhập thành xa" : "Nhập thành gần")
      : config.coords[src] + (item.capture ? " × " : " → ") + config.coords[dst];
    if (promotion) text += " = " + config.pieces[promotion];
    const row = document.createElement("tr");
    row.className = config.sideByPiece[item.piece] === 0 ? "west" : "east";
    for (const value of [index + 1, config.pieces[item.piece], text]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    return row;
  }));
  const log = $("log-wrap");
  log.scrollTop = log.scrollHeight;
}

function placePracticePiece(square, piece) {
  if (!validSquare(square)) return;
  practice.serverError = "";
  if (piece === WK || piece === XK) {
    for (let sq = 0; sq < practice.cells.length; sq++) {
      if (practice.cells[sq] === piece) practice.cells[sq] = 0;
    }
  }
  practice.cells[square] = piece;
  render();
}

function validatePracticeClient() {
  let wk = -1;
  let xk = -1;
  let wkCount = 0;
  let xkCount = 0;
  for (let sq = 0; sq < practice.cells.length; sq++) {
    const p = practice.cells[sq];
    if (!p) continue;
    if (p === WK) { wk = sq; wkCount++; }
    else if (p === XK) { xk = sq; xkCount++; }
    else if (p === XA && !insidePalace(sq)) return "Sĩ cờ tướng phải nằm trong cung Tướng.";
    else if (p === XE && Math.floor(sq / FILES) < RIVER) return "Tượng cờ tướng phải nằm ở phần sân cờ tướng.";
  }
  if (wkCount !== 1) return "Cần đúng 1 Vua cờ vua trên bàn.";
  if (xkCount !== 1) return "Cần đúng 1 Tướng cờ tướng trên bàn.";
  if (!insidePalace(xk)) return "Tướng cờ tướng phải nằm trong cung Tướng.";
  if (settings.rules === "balanced" && config && !config.palace.includes(wk)) {
    return "Ở bộ luật Cân bằng, Vua cờ vua phải nằm trong cung c8–f6.";
  }
  return null;
}

function drawMiniPiece(canvas, piece) {
  const ctx = canvas.getContext("2d");
  const sz = canvas.width;
  ctx.clearRect(0, 0, sz, sz);
  if (piece <= 6) {
    const atlas = board.atlases[settings.chessColor] ?? board.atlases.white;
    if (atlas.complete && atlas.naturalWidth) {
      const srcSize = 48;
      const n = (srcSize - 24) / 4;
      const stripY = n * (24 + srcSize - 4) / 2;
      ctx.drawImage(atlas, (piece - 1) * srcSize, stripY, srcSize, srcSize, 1, 1, sz - 2, sz - 2);
    } else {
      ctx.fillStyle = settings.chessColor === "black" ? "#1c2321" : "#f6efdd";
      ctx.font = "700 " + Math.round(sz * .72) + "px Segoe UI Symbol, serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const glyphs = settings.chessColor === "black" ? ["♚", "♛", "♜", "♝", "♞", "♟"] : ["♔", "♕", "♖", "♗", "♘", "♙"];
      ctx.fillText(glyphs[piece - 1], sz / 2, sz / 2 + 1);
    }
    return;
  }
  const pal = XIANGQI_PALETTE_STYLE[settings.xiangqiColor] ?? XIANGQI_PALETTE_STYLE.red;
  const r = sz * .43;
  ctx.beginPath();
  ctx.arc(sz / 2, sz / 2, r, 0, Math.PI * 2);
  ctx.fillStyle = pal.fill;
  ctx.fill();
  ctx.strokeStyle = pal.outline;
  ctx.lineWidth = Math.max(1.5, sz * .055);
  ctx.stroke();
  ctx.fillStyle = pal.ink;
  ctx.font = "700 " + Math.round(sz * .52) + "px Microsoft YaHei, Noto Sans CJK SC, serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(pal.marks[piece - 7], sz / 2, sz / 2 + 1);
}

const paletteButtons = new Map();

function buildPalette() {
  const makeBtn = (piece, parent, px) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "palette-piece";
    button.setAttribute("aria-pressed", "false");
    button.title = config?.pieces[piece] ?? "";
    const canvas = document.createElement("canvas");
    canvas.width = px;
    canvas.height = px;
    button.append(canvas);
    button.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      practice.brush = piece;
      paletteDrag = {id: event.pointerId, piece, x: event.clientX, y: event.clientY, dragging: false};
      button.setPointerCapture(event.pointerId);
      render();
    });
    button.addEventListener("pointermove", (event) => {
      if (!paletteDrag || paletteDrag.id !== event.pointerId) return;
      if (!paletteDrag.dragging && Math.hypot(event.clientX - paletteDrag.x, event.clientY - paletteDrag.y) < 6) return;
      paletteDrag.dragging = true;
      const ghost = $("palette-ghost");
      if (ghost.hidden) {
        let gCanvas = ghost.querySelector("canvas");
        if (!gCanvas) {
          gCanvas = document.createElement("canvas");
          gCanvas.width = 48;
          gCanvas.height = 48;
          ghost.append(gCanvas);
        }
        drawMiniPiece(gCanvas, paletteDrag.piece);
        ghost.hidden = false;
      }
      ghost.style.left = event.clientX + "px";
      ghost.style.top = event.clientY + "px";
      board.setPalettePreview(paletteDrag.piece, event.clientX, event.clientY);
    });
    const finishDrag = (event) => {
      if (!paletteDrag || paletteDrag.id !== event.pointerId) return;
      const {piece: dropped, dragging} = paletteDrag;
      paletteDrag = null;
      $("palette-ghost").hidden = true;
      board.clearPalettePreview();
      if (dragging && event.type === "pointerup") {
        const sq = board.squareAtClient(event.clientX, event.clientY);
        if (sq !== null) placePracticePiece(sq, dropped);
      }
    };
    button.addEventListener("pointerup", finishDrag);
    button.addEventListener("pointercancel", finishDrag);
    parent.append(button);
    paletteButtons.set(piece, {button, canvas});
  };
  for (let p = 1; p <= 6; p++) makeBtn(p, $("palette-west"), 36);
  for (let p = 7; p <= 13; p++) makeBtn(p, $("palette-east"), 34);
  for (const img of Object.values(board.atlases)) {
    img.addEventListener("load", () => { if (practice.active) renderPalette(); });
  }
}

function renderPalette() {
  for (const [piece, {button, canvas}] of paletteButtons) {
    button.setAttribute("aria-pressed", String(practice.brush === piece));
    if (config) button.title = config.pieces[piece];
    drawMiniPiece(canvas, piece);
  }
  $("practice-eraser").setAttribute("aria-pressed", String(practice.brush === 0));
}

function render() {
  const game = current();
  const frame = input();
  for (const type of ["rules", "mode", "human", "seconds"]) {
    for (const button of document.querySelectorAll("[data-" + type + "]")) {
      button.setAttribute("aria-pressed", String(button.dataset[type] === String(settings[type])));
    }
  }
  for (const button of document.querySelectorAll("[data-chess-color]")) {
    const value = button.dataset.chessColor;
    button.setAttribute("aria-pressed", String(value === settings.chessColor));
    button.disabled = !validPieceColors(value, settings.xiangqiColor);
  }
  for (const button of document.querySelectorAll("[data-xiangqi-color]")) {
    const value = button.dataset.xiangqiColor;
    button.setAttribute("aria-pressed", String(value === settings.xiangqiColor));
    button.disabled = !validPieceColors(settings.chessColor, value);
  }
  $("practice-toggle").setAttribute("aria-pressed", String(practice.active));
  $("practice-panel").hidden = !practice.active;
  $("history-panel").hidden = practice.active;
  const flipped = boardFlipped();
  document.querySelector(".playing-area").classList.toggle("flipped", flipped);
  $("bot-settings").hidden = settings.mode !== "bot";
  $("new-game").disabled = !config;
  const chessMark = settings.chessColor === "white" ? "♔" : "♚";
  const xiangqiMark = settings.xiangqiColor === "black" ? "將" : "帥";

  if (practice.active) {
    renderPalette();
    for (const button of document.querySelectorAll("[data-practice-turn]")) {
      button.setAttribute("aria-pressed", String(Number(button.dataset.practiceTurn) === practice.turn));
    }
    $("practice-cannon-open").checked = practice.cannonOpen;
    const localError = validatePracticeClient();
    const statusText = practice.serverError || localError || "Thế cờ hợp lệ · Bấm để bắt đầu chơi.";
    const statusEl = $("practice-status");
    statusEl.textContent = statusText;
    statusEl.classList.toggle("error", Boolean(practice.serverError || localError));
    $("practice-start").disabled = Boolean(localError || active);
    $("turn-caption").textContent = "Phòng tập";
    $("turn-title").textContent = "Xếp thế cờ";
    const brushLabel = practice.brush === 0
      ? "Xóa quân"
      : (config ? config.pieces[practice.brush] + " (" + config.sides[config.sideByPiece[practice.brush]] + ")" : "");
    $("detail").textContent = "Đang chọn: " + brushLabel;
    $("detail").classList.remove("error");
    $("retry").hidden = true;
    $("turn-symbol").textContent = practice.turn === 1 ? xiangqiMark : chessMark;
    $("turn-symbol").classList.toggle("east", practice.turn === 1);
    [$("seat-west"), $("seat-east")].forEach((seat, side) => {
      seat.classList.toggle("active", practice.turn === side);
      seat.querySelector(".seat-icon").textContent = side === 0 ? chessMark : xiangqiMark;
      seat.querySelector(".seat-role").textContent = settings.mode === "bot" ? (settings.human === side ? "Bạn" : "Máy") : "";
      seat.querySelector(".seat-status").textContent = practice.turn === side ? "Đi trước" : "";
    });
    const occupied = new Set();
    for (let sq = 0; sq < practice.cells.length; sq++) if (practice.cells[sq]) occupied.add(sq);
    board.show({
      revision: "practice", cells: practice.cells, candidates: occupied,
      targets: new Set(), premoves: [], selection: null, planning: false,
      palace: config && settings.rules === "balanced" ? config.palace : [],
      showTargets: false, last: null, check: null,
      flipped, chessColor: settings.chessColor, xiangqiColor: settings.xiangqiColor,
      threatSource: null, threatTargets: new Set(), threatCaptures: new Set(),
      editing: true,
    });
    return;
  }

  const opp = opponentSide(game);
  if (threatSource !== null) {
    const inspected = game?.cells[threatSource];
    if (!inspected || !config || config.sideByPiece[inspected] !== opp) threatSource = null;
  }
  const threatList = threatSource !== null ? (game?.threats?.[String(threatSource)] ?? []) : [];
  const threatTargets = new Set(threatList);
  const threatCaptures = new Set(threatList.filter((sq) => Boolean(game?.cells[sq])));
  $("undo").disabled = !undoCount(game) || Boolean(active && active.action !== "bot");
  const activeSide = game?.outcome ? game.outcome.winner : game?.turn;
  let caption = game?.outcome ? "Kết quả" : "Lượt đi";
  let detail = error || notice || "Chọn một quân để đi";
  let title = "Đang tải bàn cờ";
  if (game?.outcome) {
    title = activeSide === null ? "Hòa cờ" : config.sides[activeSide] + " thắng";
    detail = error || game.outcome.reason;
  } else if (game) {
    title = config.sides[game.turn];
    if (settings.mode === "bot") caption = botTurn(game) ? "Lượt máy" : "Lượt của bạn";
    if (frame.planning) detail = pending.length ? "PreMove " + pending.length + "/" + config.maxPremoves + " · Esc để hủy"
      : "Máy đang tính · Có thể đặt trước";
    else if (active?.action === "bot") detail = "Máy đang tính…";
    else if (active) detail = "Đang cập nhật bàn cờ…";
    else if (!error && !notice && game.bot) detail = "Bot · độ sâu " + game.bot.depth + " · " + game.bot.nodes.toLocaleString("vi-VN") + " nút";
    if (selection !== null && frame.candidates.has(selection)) {
      const name = config.pieces[frame.cells[selection]];
      detail = (frame.planning ? "Đặt trước " : "") + name + " · " + config.coords[selection];
    } else if (threatSource !== null && !error) {
      const name = config.pieces[game.cells[threatSource]];
      const hitNote = threatCaptures.size ? " (" + threatCaptures.size + " quân bị đe dọa)" : "";
      detail = "Đe dọa: " + name + " · " + config.coords[threatSource] + " · " + threatTargets.size + " ô" + hitNote;
    }
    if (game.check !== null && !error) detail = "Đang bị chiếu · " + detail;
  } else if (!error) {
    detail = "Đang kết nối với bộ luật trò chơi…";
  }
  $("turn-caption").textContent = caption;
  $("turn-title").textContent = title;
  $("detail").textContent = detail;
  $("detail").classList.toggle("error", Boolean(error));
  $("retry").hidden = !retry;
  $("turn-symbol").textContent = activeSide === 1 ? xiangqiMark : activeSide === null ? "=" : chessMark;
  $("turn-symbol").classList.toggle("east", activeSide === 1);

  [$("seat-west"), $("seat-east")].forEach((seat, side) => {
    const playing = Boolean(game && !game.outcome && game.turn === side);
    seat.classList.toggle("active", playing);
    seat.querySelector(".seat-icon").textContent = side === 0 ? chessMark : xiangqiMark;
    seat.querySelector(".seat-role").textContent = settings.mode === "bot" ? (settings.human === side ? "Bạn" : "Máy") : "";
    seat.querySelector(".seat-status").textContent = playing ? (game.check !== null ? "Bị chiếu" : "Đang đi") : "";
  });
  renderHistory(game);
  board.show({
    revision: game, ...frame, selection, premoves: pending,
    targets: new Set(frame.moves.map((move) => move[1])),
    palace: config && settings.rules === "balanced" ? config.palace : [],
    showTargets: $("show-targets").checked,
    last: $("show-last").checked ? records(game).at(-1)?.move : null, check: game?.check,
    flipped, chessColor: settings.chessColor, xiangqiColor: settings.xiangqiColor,
    threatSource, threatTargets, threatCaptures,
    editing: false,
  });
}

for (const button of document.querySelectorAll("[data-rules]")) {
  button.addEventListener("click", () => {
    if (settings.rules === button.dataset.rules) return;
    settings.rules = button.dataset.rules;
    if (practice.active) {
      practice.serverError = "";
      render();
      return;
    }
    cancelRequest();
    clearSelection();
    board.clear();
    if (config && !current()) request("state", []);
    else { render(); runBot(); }
  });
}
for (const type of ["mode", "human", "seconds"]) {
  for (const button of document.querySelectorAll("[data-" + type + "]")) {
    button.addEventListener("click", () => {
      const value = type === "mode" ? button.dataset[type] : Number(button.dataset[type]);
      if (settings[type] === value) return;
      if (active?.action === "bot") cancelRequest();
      if (error && current()) { error = ""; retry = null; }
      settings[type] = value;
      if (type !== "seconds") clearSelection();
      render();
      runBot();
    });
  }
}
for (const button of document.querySelectorAll("[data-chess-color]")) {
  button.addEventListener("click", () => {
    const color = button.dataset.chessColor;
    if (settings.chessColor === color || !validPieceColors(color, settings.xiangqiColor)) return;
    settings.chessColor = color;
    render();
  });
}
for (const button of document.querySelectorAll("[data-xiangqi-color]")) {
  button.addEventListener("click", () => {
    const color = button.dataset.xiangqiColor;
    if (settings.xiangqiColor === color || !validPieceColors(settings.chessColor, color)) return;
    settings.xiangqiColor = color;
    render();
  });
}
for (const button of document.querySelectorAll("[data-dialog]")) {
  button.addEventListener("click", () => $(button.dataset.dialog).showModal());
}
for (const option of ["enable-premove", "show-last", "show-targets"]) {
  $(option).addEventListener("change", () => {
    if (!$("enable-premove").checked && active?.action === "bot") clearSelection();
    render();
  });
}
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || document.querySelector("dialog[open]")) return;
  const hadPlan = pending.length > 0;
  clearSelection();
  if (hadPlan) notice = "Đã hủy PreMove.";
  board.clear();
  render();
});
$("new-game").addEventListener("click", () => {
  cancelRequest();
  practice.active = false;
  practice.serverError = "";
  setups.delete(settings.rules);
  clearSelection();
  board.clear();
  request("state", [], null, null);
});
function togglePractice() {
  cancelRequest();
  clearSelection();
  board.clear();
  practice.serverError = "";
  if (practice.active) {
    practice.active = false;
  } else {
    const game = current();
    practice.cells = game ? game.cells.slice() : START_CELLS.slice();
    practice.turn = game ? game.turn : 1;
    practice.active = true;
  }
  render();
}
$("practice-toggle").addEventListener("click", togglePractice);
$("practice-exit").addEventListener("click", togglePractice);
$("practice-eraser").addEventListener("click", () => {
  practice.brush = 0;
  render();
});
$("practice-clear").addEventListener("click", () => {
  practice.cells = new Array(SIZE).fill(0);
  practice.cells[4] = WK;
  practice.cells[8 * FILES + 4] = XK;
  practice.serverError = "";
  render();
});
$("practice-default").addEventListener("click", () => {
  practice.cells = START_CELLS.slice();
  practice.turn = 1;
  practice.serverError = "";
  render();
});
for (const button of document.querySelectorAll("[data-practice-turn]")) {
  button.addEventListener("click", () => {
    practice.turn = Number(button.dataset.practiceTurn);
    practice.serverError = "";
    render();
  });
}
$("practice-cannon-open").addEventListener("change", () => {
  practice.cannonOpen = $("practice-cannon-open").checked;
  practice.serverError = "";
  render();
});
$("practice-start").addEventListener("click", () => {
  if (validatePracticeClient()) { render(); return; }
  const setup = {
    cells: practice.cells.slice(),
    turn: practice.turn,
    ply: practice.cannonOpen ? 5 : 0,
  };
  request("state", [], null, setup);
});
$("undo").addEventListener("click", () => {
  const count = undoCount(current());
  if (!count) return;
  cancelRequest();
  clearSelection();
  board.clear();
  request("state", history().slice(0, -count));
});
$("retry").addEventListener("click", () => retry?.());

async function start() {
  buildPalette();
  retry = null;
  error = "";
  render();
  try {
    config = await responseJSON(await fetch("/api/game"));
    request("state", []);
  } catch (failure) {
    error = "Không tải được bộ luật trò chơi.";
    retry = start;
    render();
  }
}

start();
