import crypto from "node:crypto";

import { LocalWebSocketClient } from "./protocol.js";

const PLUGIN_UUID = "com.cokkles.tarkov-personal-agent";
const ACTIONS = {
  status: `${PLUGIN_UUID}.status`,
  startRaid: `${PLUGIN_UUID}.start-raid`,
  endRaid: `${PLUGIN_UUID}.end-raid`,
  pmcHeard: `${PLUGIN_UUID}.pmc-heard`,
  playerSeen: `${PLUGIN_UUID}.player-seen`,
  fightStarted: `${PLUGIN_UUID}.fight-started`,
  routeChanged: `${PLUGIN_UUID}.route-changed`,
  importantLoot: `${PLUGIN_UUID}.important-loot`,
  mistake: `${PLUGIN_UUID}.mistake`,
  goodDecision: `${PLUGIN_UUID}.good-decision`,
};

const MARKERS = new Map([
  [ACTIONS.pmcHeard, "contact.audio.possible_pmc"],
  [ACTIONS.playerSeen, "contact.visual.player"],
  [ACTIONS.fightStarted, "combat.engagement.started"],
  [ACTIONS.routeChanged, "decision.route.changed"],
  [ACTIONS.importantLoot, "loot.important"],
  [ACTIONS.mistake, "review.mistake"],
  [ACTIONS.goodDecision, "review.good_decision"],
]);

const DEFAULT_SETTINGS = {
  baseUrl: "http://127.0.0.1:8765",
  token: "",
};

function argumentValue(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const port = argumentValue("-port");
const pluginUUID = argumentValue("-pluginUUID") ?? PLUGIN_UUID;
const registerEvent = argumentValue("-registerEvent");
if (!port || !registerEvent) {
  throw new Error("Stream Deck did not supply the required connection arguments");
}

const streamDeck = new LocalWebSocketClient(port);
const statusContexts = new Set();
const recentPresses = new Map();
let globalSettings = { ...DEFAULT_SETTINGS };
let statusPoll = null;

function send(event) {
  streamDeck.sendJson(event);
}

function showOk(context) {
  send({ event: "showOk", context });
}

function showAlert(context) {
  send({ event: "showAlert", context });
}

function setTitle(context, title) {
  send({
    event: "setTitle",
    context,
    payload: { title, target: 0 },
  });
}

function propertyInspectorMessage(action, context, payload) {
  send({
    event: "sendToPropertyInspector",
    action,
    context,
    payload,
  });
}

function normalizedBaseUrl() {
  return String(globalSettings.baseUrl || DEFAULT_SETTINGS.baseUrl).replace(/\/+$/, "");
}

async function apiRequest(path, options = {}, timeoutMs = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const headers = {
    Accept: "application/json",
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(globalSettings.token ? { "X-TPA-Token": String(globalSettings.token) } : {}),
  };
  try {
    const response = await fetch(`${normalizedBaseUrl()}${path}`, {
      ...options,
      headers: { ...headers, ...(options.headers || {}) },
      signal: controller.signal,
    });
    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      const detail = payload && typeof payload === "object" ? payload.detail : payload;
      throw new Error(detail || `Agent request failed with HTTP ${response.status}`);
    }
    return payload;
  } finally {
    clearTimeout(timer);
  }
}

function shouldDebounce(context) {
  const now = Date.now();
  const previous = recentPresses.get(context) ?? 0;
  recentPresses.set(context, now);
  return now - previous < 750;
}

async function createMarker(context, markerType) {
  if (shouldDebounce(context)) {
    showOk(context);
    return;
  }
  await apiRequest(
    "/api/markers",
    {
      method: "POST",
      body: JSON.stringify({
        marker_type: markerType,
        source: "stream_deck",
        request_id: crypto.randomUUID(),
      }),
    },
    4000,
  );
  showOk(context);
}

async function startRaid(context, settings) {
  await apiRequest(
    "/api/control/raid/start",
    {
      method: "POST",
      body: JSON.stringify({
        game: "tarkov",
        map_name: settings.mapName || null,
        character_type: settings.characterType || "Scav",
        primary_objective: settings.primaryObjective || null,
        secondary_objective: settings.secondaryObjective || null,
      }),
    },
    10000,
  );
  showOk(context);
  await refreshStatus();
}

async function endRaid(context, settings) {
  await apiRequest(
    "/api/control/raid/end",
    {
      method: "POST",
      body: JSON.stringify({ result: settings.result || null }),
    },
    60000,
  );
  showOk(context);
  await refreshStatus();
}

async function loadStatus() {
  return apiRequest("/api/status", { method: "GET" }, 3000);
}

async function refreshStatus() {
  if (statusContexts.size === 0) return;
  try {
    const status = await loadStatus();
    const active = status && status.active_raid;
    const title = active ? "RAID\nACTIVE" : "AGENT\nONLINE";
    for (const context of statusContexts) setTitle(context, title);
  } catch {
    for (const context of statusContexts) setTitle(context, "AGENT\nOFFLINE");
  }
}

function startStatusPolling() {
  if (statusPoll !== null) return;
  statusPoll = setInterval(() => {
    refreshStatus().catch(() => {});
  }, 3000);
}

async function handleKeyDown(message) {
  const { action, context } = message;
  const settings = message.payload?.settings ?? {};
  try {
    if (MARKERS.has(action)) {
      await createMarker(context, MARKERS.get(action));
    } else if (action === ACTIONS.startRaid) {
      await startRaid(context, settings);
    } else if (action === ACTIONS.endRaid) {
      await endRaid(context, settings);
    } else if (action === ACTIONS.status) {
      await refreshStatus();
      showOk(context);
    }
  } catch (error) {
    console.error(`[TPA] ${action} failed:`, error);
    showAlert(context);
  }
}

async function handlePropertyInspector(message) {
  if (message.payload?.command !== "testConnection") return;
  try {
    const status = await loadStatus();
    propertyInspectorMessage(message.action, message.context, {
      command: "testConnectionResult",
      ok: true,
      message: status?.active_raid ? "Connected — raid active" : "Connected — agent online",
    });
  } catch (error) {
    propertyInspectorMessage(message.action, message.context, {
      command: "testConnectionResult",
      ok: false,
      message: error instanceof Error ? error.message : String(error),
    });
  }
}

streamDeck.onMessage = (text) => {
  let message;
  try {
    message = JSON.parse(text);
  } catch {
    return;
  }
  if (message.event === "didReceiveGlobalSettings") {
    globalSettings = { ...DEFAULT_SETTINGS, ...(message.payload?.settings ?? {}) };
    refreshStatus().catch(() => {});
  } else if (message.event === "willAppear") {
    if (message.action === ACTIONS.status) {
      statusContexts.add(message.context);
      refreshStatus().catch(() => {});
    }
  } else if (message.event === "willDisappear") {
    statusContexts.delete(message.context);
    recentPresses.delete(message.context);
  } else if (message.event === "keyDown") {
    handleKeyDown(message).catch(() => showAlert(message.context));
  } else if (message.event === "sendToPlugin") {
    handlePropertyInspector(message).catch(() => {});
  }
};

streamDeck.onClose = () => {
  if (statusPoll !== null) clearInterval(statusPoll);
  process.exit(1);
};

await streamDeck.connect();
send({ event: registerEvent, uuid: pluginUUID });
send({ event: "getGlobalSettings", context: pluginUUID });
startStatusPolling();
