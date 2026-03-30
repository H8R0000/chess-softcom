const configNode = document.getElementById("clock-config");
const pageConfig = configNode ? JSON.parse(configNode.textContent) : {};

const els = {
  clockShell: document.getElementById("clockShell"),
  settingsPanel: document.getElementById("settingsPanel"),
  resultPanel: document.getElementById("resultPanel"),
  settingsBtn: document.getElementById("settingsBtn"),
  resultBtn: document.getElementById("resultBtn"),
  closeSettingsBtn: document.getElementById("closeSettingsBtn"),
  closeResultBtn: document.getElementById("closeResultBtn"),
  topPlayerSelect: document.getElementById("topPlayerSelect"),
  bottomPlayerSelect: document.getElementById("bottomPlayerSelect"),
  winnerSelect: document.getElementById("winnerSelect"),
  minutes: document.getElementById("minutes"),
  increment: document.getElementById("increment"),
  topDisplay: document.getElementById("topDisplay"),
  bottomDisplay: document.getElementById("bottomDisplay"),
  topTime: document.getElementById("topTime"),
  bottomTime: document.getElementById("bottomTime"),
  topMeta: document.getElementById("topMeta"),
  bottomMeta: document.getElementById("bottomMeta"),
  topState: document.getElementById("topState"),
  bottomState: document.getElementById("bottomState"),
  playerTop: document.getElementById("playerTop"),
  playerBottom: document.getElementById("playerBottom"),
  pauseBtn: document.getElementById("pauseBtn"),
  resetBtn: document.getElementById("resetBtn"),
  fullscreenBtn: document.getElementById("fullscreenBtn"),
  applyBtn: document.getElementById("applyBtn"),
  saveResultBtn: document.getElementById("saveResultBtn"),
  statusText: document.getElementById("statusText"),
  presets: [...document.querySelectorAll(".preset")],
};

const state = {
  baseMinutes: Number(pageConfig.initialMinutes ?? 5),
  incrementSeconds: Number(pageConfig.initialIncrement ?? 0),
  topMs: 0,
  bottomMs: 0,
  active: "top",
  running: false,
  started: false,
  finished: false,
  winnerDirty: false,
  lastTick: 0,
  rafId: 0,
};

function clampNumber(value, min, max, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

function formatTime(ms) {
  const safe = Math.max(0, ms);
  const totalMs = Math.ceil(safe);
  const totalSeconds = Math.floor(totalMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const tenths = Math.floor((totalMs % 1000) / 100);

  if (safe < 60_000) {
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${tenths}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function getSelectedPlayerName(select, fallback) {
  const option = select?.selectedOptions?.[0];
  if (option && option.value) {
    return option.textContent.trim();
  }
  return fallback;
}

function syncNames() {
  els.topDisplay.textContent = getSelectedPlayerName(
    els.topPlayerSelect,
    pageConfig.topPlayerName || "Игрок сверху"
  );
  els.bottomDisplay.textContent = getSelectedPlayerName(
    els.bottomPlayerSelect,
    pageConfig.bottomPlayerName || "Игрок снизу"
  );
  syncWinnerOptions();
}

function syncMeta() {
  const label = `+${state.incrementSeconds} сек`;
  els.topMeta.textContent = label;
  els.bottomMeta.textContent = label;
}

function getWinnerOptions() {
  return [
    { value: "draw", label: "Ничья" },
    { value: "top", label: els.topDisplay.textContent.trim() },
    { value: "bottom", label: els.bottomDisplay.textContent.trim() },
  ];
}

function syncWinnerOptions(preferredValue = null) {
  if (!els.winnerSelect) return;

  const winnerOptions = getWinnerOptions();
  const selectedValue = preferredValue ?? els.winnerSelect.value;

  els.winnerSelect.replaceChildren(
    ...winnerOptions.map(({ value, label }) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      return option;
    })
  );

  const hasSelectedValue = winnerOptions.some(({ value }) => value === selectedValue);
  els.winnerSelect.value = hasSelectedValue ? selectedValue : "draw";
}

function getHeuristicWinner() {
  if (state.finished) {
    if (state.topMs <= 0) return "bottom";
    if (state.bottomMs <= 0) return "top";
  }

  if (!state.started) {
    return "";
  }

  // const diff = Math.abs(state.topMs - state.bottomMs);
  // if (diff < 1000) {
  //   return "draw";
  // }

  return state.active === "top" ? "bottom" : "top";
}

function autofillWinner(force = false) {
  if (!els.winnerSelect) return;

  if (!force && state.winnerDirty) {
    syncWinnerOptions();
    return;
  }

  syncWinnerOptions(getHeuristicWinner() || "draw");
}

function getCsrfToken() {
  return document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";
}

function buildSaveResultPayload() {
  return new URLSearchParams({
    top_player_id: els.topPlayerSelect?.value || "",
    bottom_player_id: els.bottomPlayerSelect?.value || "",
    winner: els.winnerSelect?.value || "",
    minutes: String(state.baseMinutes),
    increment: String(state.incrementSeconds),
  });
}

async function saveResult() {
  if (!pageConfig.saveResultUrl) {
    setStatus("Сохранение результата недоступно");
    return;
  }

  if (!els.topPlayerSelect.value || !els.bottomPlayerSelect.value) {
    setStatus("Сначала выберите обоих игроков");
    return;
  }

  if (els.topPlayerSelect.value === els.bottomPlayerSelect.value) {
    setStatus("Игроки должны быть разными");
    return;
  }

  if (!els.winnerSelect.value) {
    setStatus("Выберите победителя или ничью");
    return;
  }

  if (state.running) {
    pauseClock();
  }

  const initialLabel = els.saveResultBtn.textContent;
  els.saveResultBtn.disabled = true;
  els.saveResultBtn.textContent = "Сохранение...";

  try {
    const response = await fetch(pageConfig.saveResultUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: buildSaveResultPayload().toString(),
    });

    let data = {};
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    }

    if (!response.ok) {
      throw new Error(data.error || "Не удалось сохранить результат");
    }

    closeResult();
    setStatus(data.message || "Результат сохранен");
  } catch (error) {
    setStatus(error.message || "Ошибка сохранения результата");
  } finally {
    els.saveResultBtn.disabled = false;
    els.saveResultBtn.textContent = initialLabel;
  }
}

function setStatus(text) {
  els.statusText.textContent = text;
}

function render() {
  els.topTime.textContent = formatTime(state.topMs);
  els.bottomTime.textContent = formatTime(state.bottomMs);

  const topActive = state.active === "top" && !state.finished;
  const bottomActive = state.active === "bottom" && !state.finished;

  els.playerTop.classList.toggle("active", topActive);
  els.playerBottom.classList.toggle("active", bottomActive);
  els.playerTop.classList.toggle("flagged", state.finished && state.topMs <= 0);
  els.playerBottom.classList.toggle("flagged", state.finished && state.bottomMs <= 0);

  els.topState.textContent = state.finished
    ? state.topMs <= 0
      ? "Время вышло"
      : "Победа"
    : topActive
      ? state.running
        ? "Ход"
        : "Пауза"
      : "Ожидание";

  els.bottomState.textContent = state.finished
    ? state.bottomMs <= 0
      ? "Время вышло"
      : "Победа"
    : bottomActive
      ? state.running
        ? "Ход"
        : "Пауза"
      : "Ожидание";

  els.pauseBtn.disabled = state.finished || !state.started;
  els.pauseBtn.textContent = state.running ? "⏸" : "▶";
}

function stopTicker() {
  if (state.rafId) {
    cancelAnimationFrame(state.rafId);
    state.rafId = 0;
  }
}

function finish(loser) {
  state.running = false;
  state.finished = true;
  stopTicker();
  state.active = loser;
  const winner = loser === "top" ? els.bottomDisplay.textContent : els.topDisplay.textContent;
  setStatus(`Победа: ${winner}`);
  autofillWinner(true);
  render();
}

function tick(now) {
  if (!state.running || state.finished) return;

  if (!state.lastTick) {
    state.lastTick = now;
  }

  const delta = now - state.lastTick;
  state.lastTick = now;

  if (state.active === "top") {
    state.topMs -= delta;
    if (state.topMs <= 0) {
      state.topMs = 0;
      finish("top");
      return;
    }
  } else {
    state.bottomMs -= delta;
    if (state.bottomMs <= 0) {
      state.bottomMs = 0;
      finish("bottom");
      return;
    }
  }

  render();
  state.rafId = requestAnimationFrame(tick);
}

function startClock() {
  if (state.finished) return;
  if (!state.started) {
    state.started = true;
  }
  if (state.running) return;

  state.running = true;
  state.lastTick = performance.now();
  setStatus(`Ход: ${state.active === "top" ? els.topDisplay.textContent : els.bottomDisplay.textContent}`);
  closeSettings();
  render();
  state.rafId = requestAnimationFrame(tick);
}

function pauseClock() {
  state.running = false;
  stopTicker();
  setStatus("Пауза");
  render();
}

function switchTurn(player) {
  if (state.finished) return;

  if (!state.started) {
    state.active = player === "top" ? "bottom" : "top";
    startClock();
    return;
  }

  if (!state.running || state.active !== player) return;

  if (player === "top") {
    state.topMs += state.incrementSeconds * 1000;
    state.active = "bottom";
  } else {
    state.bottomMs += state.incrementSeconds * 1000;
    state.active = "top";
  }

  state.lastTick = performance.now();
  setStatus(`Ход: ${state.active === "top" ? els.topDisplay.textContent : els.bottomDisplay.textContent}`);
  render();
}

function applySettings() {
  state.baseMinutes = clampNumber(els.minutes.value, 1, 180, 5);
  state.incrementSeconds = clampNumber(els.increment.value, 0, 60, 0);
  state.topMs = state.baseMinutes * 60 * 1000;
  state.bottomMs = state.baseMinutes * 60 * 1000;
  state.active = "top";
  state.running = false;
  state.started = false;
  state.finished = false;
  state.lastTick = 0;

  stopTicker();
  syncNames();
  syncMeta();
  state.winnerDirty = false;
  syncWinnerOptions("draw");
  setStatus("Готово к старту");
  render();
  closeSettings();
}

function resetClock() {
  applySettings();
}

function activatePreset(btn) {
  els.presets.forEach((item) => item.classList.toggle("is-active", item === btn));
  els.minutes.value = btn.dataset.minutes;
  els.increment.value = btn.dataset.increment;
}

function openSettings() {
  els.settingsPanel.classList.add("is-open");
}

function closeSettings() {
  els.settingsPanel.classList.remove("is-open");
}

function closeResult() {
  els.resultPanel.classList.remove("is-open");
}

function openResult() {
  autofillWinner();
  els.resultPanel.classList.add("is-open");
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  } catch {
    setStatus("Полный экран недоступен");
  }
}

els.pauseBtn.addEventListener("click", () => {
  if (state.running) {
    pauseClock();
  } else {
    startClock();
  }
});
els.resetBtn.addEventListener("click", resetClock);
els.applyBtn.addEventListener("click", applySettings);
els.saveResultBtn.addEventListener("click", saveResult);
els.fullscreenBtn.addEventListener("click", toggleFullscreen);
els.settingsBtn.addEventListener("click", openSettings);
els.closeSettingsBtn.addEventListener("click", closeSettings);
els.resultBtn.addEventListener("click", openResult);
els.closeResultBtn.addEventListener("click", closeResult);
els.playerTop.addEventListener("click", () => switchTurn("top"));
els.playerBottom.addEventListener("click", () => switchTurn("bottom"));
els.topPlayerSelect.addEventListener("change", syncNames);
els.bottomPlayerSelect.addEventListener("change", syncNames);
els.winnerSelect.addEventListener("change", () => {
  state.winnerDirty = true;
});

[els.playerTop, els.playerBottom].forEach((node, index) => {
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      switchTurn(index === 0 ? "top" : "bottom");
    }
  });
});

els.presets.forEach((btn) => {
  btn.addEventListener("click", () => activatePreset(btn));
});

document.addEventListener("fullscreenchange", () => {
  els.fullscreenBtn.textContent = document.fullscreenElement ? "⤡" : "⤢";
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden && state.running && !state.finished) {
    pauseClock();
  }
});

const initialPreset = els.presets.find(
  (btn) => Number(btn.dataset.minutes) === Number(pageConfig.initialMinutes ?? 5)
    && Number(btn.dataset.increment) === Number(pageConfig.initialIncrement ?? 0)
);

if (initialPreset) {
  activatePreset(initialPreset);
}

if (pageConfig.topPlayerId) {
  els.topPlayerSelect.value = String(pageConfig.topPlayerId);
}

if (pageConfig.bottomPlayerId) {
  els.bottomPlayerSelect.value = String(pageConfig.bottomPlayerId);
}

applySettings();
