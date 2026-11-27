import {BoardView} from "./board.mjs";

const $ = (id) => document.getElementById(id);
const rows = $("move-log");
const promotion = $("promotion");
const games = new Map();
const settings = {rules: "classic", mode: "local", human: 0, seconds: 3};
const promotionIcons = {"2": "♛", "3": "♜", "4": "♝", "5": "♞"};
const WK = 1;
const WR = 3;

let config = null;
let active = null;
let retry = null;
let error = "";
let notice = "";
let selection = null;
let pending = [];
let logGame = null;

const current = () => games.get(settings.rules);
const records = (game = current()) => game?.records ?? [];
const history = (game = current()) => records(game).map(({move}) => move);
const sameMove = (a, b) => a[0] === b[0] && a[1] === b[1] && a[2] === b[2];
const botTurn = (game = current()) => settings.mode === "bot" && game && !game.outcome && game.turn !== settings.human;
const castleFor = (move) => config.castles.find((castle) => sameMove(castle.move, move));

const board = new BoardView($("board"), {
  choose,
  grab(square) {
    if (input().candidates.has(square)) {
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
  notice = "";
}

function choose(square, dragged) {
  const frame = input();
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
    icon.textContent = promotionIcons[move[2]];
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

async function request(action, moves, move = null) {
  if (active) return;
  const task = {action, rules: settings.rules, controller: new AbortController()};
  active = task;
  error = "";
  notice = "";
  retry = null;
  render();
  try {
    const response = await fetch("/api/game", {
      method: "POST", headers: {"Content-Type": "application/json"},
      signal: task.controller.signal,
      body: JSON.stringify({action, rules: task.rules, history: moves, move, seconds: settings.seconds}),
    });
    const next = await responseJSON(response);
    if (active !== task) return;
    if (action === "bot" && promotion.open) {
      await new Promise((done) => promotion.addEventListener("close", done, {once: true}));
    }
    if (active !== task) return;
    games.set(task.rules, next);
    active = null;
    selection = null;
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
    error = failure instanceof TypeError ? "Không kết nối được với máy chủ." : failure.message;
    retry = () => request(action, moves, move);
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

function render() {
  const game = current();
  const frame = input();
  for (const type of ["rules", "mode", "human", "seconds"]) {
    for (const button of document.querySelectorAll("[data-" + type + "]")) {
      button.setAttribute("aria-pressed", String(button.dataset[type] === String(settings[type])));
    }
  }
  $("bot-settings").hidden = settings.mode !== "bot";
  $("undo").disabled = !undoCount(game) || Boolean(active && active.action !== "bot");
  $("new-game").disabled = !config;
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
  $("turn-symbol").textContent = activeSide === 1 ? "帥" : activeSide === null ? "=" : "♚";
  $("turn-symbol").classList.toggle("east", activeSide === 1);

  [$("seat-west"), $("seat-east")].forEach((seat, side) => {
    const playing = Boolean(game && !game.outcome && game.turn === side);
    seat.classList.toggle("active", playing);
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
  });
}

for (const button of document.querySelectorAll("[data-rules]")) {
  button.addEventListener("click", () => {
    if (settings.rules === button.dataset.rules) return;
    cancelRequest();
    settings.rules = button.dataset.rules;
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
  clearSelection();
  board.clear();
  request("state", []);
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
