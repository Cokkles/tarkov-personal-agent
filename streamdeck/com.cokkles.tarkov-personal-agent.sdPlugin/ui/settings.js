const PLUGIN_UUID = "com.cokkles.tarkov-personal-agent";
const START_ACTION = `${PLUGIN_UUID}.start-raid`;
const END_ACTION = `${PLUGIN_UUID}.end-raid`;

let socket;
let inspectorContext;
let actionUuid;
let actionSettings = {};
let globalSettings = {
  baseUrl: "http://127.0.0.1:8765",
  token: "",
};
let loading = true;
let saveTimer;

const element = (id) => document.getElementById(id);

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
  }
}

function setConnectionResult(message, ok = null) {
  const target = element("connectionResult");
  target.textContent = message;
  target.className = `status${ok === true ? " success" : ok === false ? " error" : ""}`;
}

function populate() {
  loading = true;
  element("baseUrl").value = globalSettings.baseUrl || "http://127.0.0.1:8765";
  element("token").value = globalSettings.token || "";
  element("mapName").value = actionSettings.mapName || "";
  element("characterType").value = actionSettings.characterType || "Scav";
  element("primaryObjective").value = actionSettings.primaryObjective || "";
  element("secondaryObjective").value = actionSettings.secondaryObjective || "";
  element("result").value = actionSettings.result || "";
  element("startRaidFields").hidden = actionUuid !== START_ACTION;
  element("endRaidFields").hidden = actionUuid !== END_ACTION;
  loading = false;
}

function collectGlobalSettings() {
  return {
    baseUrl: element("baseUrl").value.trim() || "http://127.0.0.1:8765",
    token: element("token").value,
  };
}

function collectActionSettings() {
  if (actionUuid === START_ACTION) {
    return {
      mapName: element("mapName").value.trim(),
      characterType: element("characterType").value,
      primaryObjective: element("primaryObjective").value.trim(),
      secondaryObjective: element("secondaryObjective").value.trim(),
    };
  }
  if (actionUuid === END_ACTION) {
    return { result: element("result").value };
  }
  return actionSettings;
}

function saveSettings() {
  if (loading || !inspectorContext) return;
  globalSettings = collectGlobalSettings();
  actionSettings = collectActionSettings();
  send({
    event: "setGlobalSettings",
    context: inspectorContext,
    payload: globalSettings,
  });
  send({
    event: "setSettings",
    context: inspectorContext,
    payload: actionSettings,
  });
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveSettings, 250);
}

for (const input of document.querySelectorAll("input, select")) {
  input.addEventListener("input", scheduleSave);
  input.addEventListener("change", scheduleSave);
}

element("testConnection").addEventListener("click", () => {
  saveSettings();
  setConnectionResult("Testing…");
  send({
    event: "sendToPlugin",
    action: actionUuid,
    context: inspectorContext,
    payload: { command: "testConnection" },
  });
});

window.connectElgatoStreamDeckSocket = (port, uuid, registerEvent, _info, actionInfoText) => {
  inspectorContext = uuid;
  const info = JSON.parse(actionInfoText);
  actionUuid = info.action;
  actionSettings = info.payload?.settings || {};
  populate();

  socket = new WebSocket(`ws://127.0.0.1:${port}`);
  socket.onopen = () => {
    send({ event: registerEvent, uuid });
    send({ event: "getGlobalSettings", context: uuid });
  };
  socket.onmessage = (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    if (message.event === "didReceiveGlobalSettings") {
      globalSettings = { ...globalSettings, ...(message.payload?.settings || {}) };
      populate();
    } else if (
      message.event === "sendToPropertyInspector" &&
      message.payload?.command === "testConnectionResult"
    ) {
      setConnectionResult(
        message.payload.message || (message.payload.ok ? "Connected" : "Connection failed"),
        Boolean(message.payload.ok),
      );
    }
  };
  socket.onerror = () => setConnectionResult("Stream Deck settings connection failed", false);
};
