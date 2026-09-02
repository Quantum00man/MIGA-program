"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const factors = {Hz: 1, kHz: 1e3, MHz: 1e6};
const editors = [];
let state = null;
let busy = false;
let loading = true;
let serverOffline = false;
const fmt = value => Number(value).toLocaleString("en-US", {maximumSignificantDigits: 9});
const compact = value => value >= 1e6 ? `${fmt(value / 1e6)} MHz` : value >= 1e3 ? `${fmt(value / 1e3)} kHz` : `${fmt(value)} Hz`;
const toVpp = (value, unit) => unit === "Vrms" ? value * 2 * Math.sqrt(2) : unit === "dBm" ? 2 * Math.sqrt(2 * 50 * .001 * 10 ** (value / 10)) : value;
const fromVpp = (value, unit) => unit === "Vrms" ? value / (2 * Math.sqrt(2)) : unit === "dBm" ? 10 * Math.log10(value * value / (8 * 50 * .001)) : value;

async function api(path, method = "GET", data) {
  const response = await fetch(`/api${path}`, {method, headers: {"Content-Type": "application/json"}, ...(data === undefined ? {} : {body: JSON.stringify(data)})});
  let body;
  try { body = await response.json(); } catch { throw new Error("The server returned an invalid reply. Check that the application is running."); }
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map(item => `${item.loc.slice(1).join(" / ")}: ${item.msg.replace("Value error, ", "")}`).join(" ") : body.detail;
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return body;
}

function showError(message, target = $("#global-error")) {
  target.textContent = message;
  target.hidden = !message;
}

async function action(work, errorTarget = $("#global-error")) {
  if (busy) return;
  busy = true;
  showError("");
  showError("", errorTarget);
  renderStatus();
  try { await work(); }
  catch (error) {
    showError(error instanceof TypeError ? "The application is unreachable. Check the server, then reload this page." : error.message, errorTarget);
    try { state = await api("/state"); } catch { if (state) state.connected = false; }
  } finally { busy = false; renderStatus(); }
}

class ChannelEditor {
  constructor(number) {
    this.number = number;
    this.mode = "off";
    this.dirty = false;
    this.previousUnits = {};
    const template = $("#channel-template").innerHTML.replaceAll("-N", `-${number}`).replaceAll("Channel N", `Channel ${number}`).replace(">N<", `>${number}<`);
    const shell = document.createElement("div");
    shell.innerHTML = template;
    this.root = shell.firstElementChild;
    $("#channels").append(this.root);
    this.form = $("form", this.root);
    this.error = $(".channel-error", this.root);
    this.fields = Object.fromEntries([...this.root.querySelectorAll("[data-field]")].map(el => [el.dataset.field, el]));
    this.load({frequency_hz: 10000, amplitude: 1, amplitude_unit: "Vpp", phase_deg: 0, modulation: {mode: "off", frequency_hz: 1000, depth_percent: 50, deviation_hz: 2000}});
    this.form.addEventListener("input", () => this.changed());
    this.form.addEventListener("change", event => {
      const field = event.target.dataset.field;
      if (field && field.endsWith("_unit")) this.convertUnit(field);
      this.changed();
    });
    this.root.querySelectorAll("[data-mod]").forEach(button => button.addEventListener("click", () => { this.mode = button.dataset.mod; this.changed(); }));
    this.form.addEventListener("submit", event => {
      event.preventDefault();
      const problem = this.validate();
      if (problem) { showError(problem, this.error); return; }
      const payload = this.payload();
      action(async () => {
        state = await api(`/channels/${number}/settings`, "PUT", payload);
        this.load(state.channels[number - 1].settings);
        this.dirty = false;
      }, this.error);
    });
    $(".output-on", this.root).addEventListener("click", () => this.output(true));
    $(".output-off", this.root).addEventListener("click", () => this.output(false));
  }
  setFrequency(field, value) {
    const unit = value >= 1e6 ? "MHz" : value >= 1e3 ? "kHz" : "Hz";
    this.fields[field].value = Number((value / factors[unit]).toPrecision(16));
    this.fields[`${field}_unit`].value = unit;
    this.previousUnits[`${field}_unit`] = unit;
  }
  load(values) {
    this.loadedSignature = JSON.stringify(values);
    this.setFrequency("frequency", values.frequency_hz);
    this.setFrequency("mod_frequency", values.modulation.frequency_hz);
    this.setFrequency("deviation", values.modulation.deviation_hz);
    this.fields.amplitude.value = values.amplitude;
    this.fields.amplitude_unit.value = values.amplitude_unit;
    this.previousUnits.amplitude_unit = values.amplitude_unit;
    this.fields.phase.value = values.phase_deg;
    this.fields.depth.value = values.modulation.depth_percent;
    this.mode = values.modulation.mode;
    this.updateHints();
  }
  convertUnit(key) {
    const field = key.replace("_unit", "");
    const oldUnit = this.previousUnits[key], newUnit = this.fields[key].value;
    const input = this.fields[field];
    if (input.value !== "" && Number.isFinite(Number(input.value))) {
      const converted = key === "amplitude_unit" ? fromVpp(toVpp(Number(input.value), oldUnit), newUnit) : Number(input.value) * factors[oldUnit] / factors[newUnit];
      if (Number.isFinite(converted)) input.value = Number(converted.toPrecision(key === "amplitude_unit" ? 12 : 16));
    }
    this.previousUnits[key] = newUnit;
  }
  payload() {
    const f = this.fields;
    return {frequency_hz: Number(f.frequency.value) * factors[f.frequency_unit.value], amplitude: Number(f.amplitude.value), amplitude_unit: f.amplitude_unit.value,
      phase_deg: Number(f.phase.value), modulation: {mode: this.mode,
        frequency_hz: Number(f.mod_frequency.value) * factors[f.mod_frequency_unit.value], depth_percent: Number(f.depth.value), deviation_hz: Number(f.deviation.value) * factors[f.deviation_unit.value]}};
  }
  changed() { this.dirty = true; showError("", this.error); this.updateHints(); renderStatus(); }
  validate() {
    const required = ["frequency", "amplitude", "phase", ...(this.mode === "off" ? [] : ["mod_frequency", this.mode === "am" ? "depth" : "deviation"])];
    if (required.some(key => this.fields[key].value.trim() === "")) return "Fill in all active fields before applying.";
    const p = this.payload(), m = p.modulation;
    if (![p.frequency_hz, p.amplitude, p.phase_deg, m.frequency_hz, m.depth_percent, m.deviation_hz].every(Number.isFinite)) return "Enter finite numbers for all parameters.";
    if (p.frequency_hz < 1e-6 || p.frequency_hz > 160e6) return "Frequency must be between 1 µHz and 160 MHz.";
    if (p.phase_deg < -360 || p.phase_deg > 360) return "Phase offset must be between -360 and +360 degrees.";
    if (this.mode === "am" && p.frequency_hz > 50e6) return "AM is available only at carrier frequencies up to 50 MHz.";
    if (m.frequency_hz < 1e-6 || m.frequency_hz > 10e6) return "Modulation frequency must be between 1 µHz and 10 MHz.";
    if (m.depth_percent < 0 || m.depth_percent > 100) return "AM depth must be between 0 and 100%.";
    if (m.deviation_hz < 0 || m.deviation_hz > 80e6) return "FM deviation must be between 0 and 80 MHz.";
    const maxDeviation = Math.min(p.frequency_hz, 160e6 - p.frequency_hz, 80e6);
    if (this.mode === "fm" && m.deviation_hz > maxDeviation) return `For this carrier, FM deviation must not exceed ${compact(maxDeviation)}.`;
    const peak = p.frequency_hz + (this.mode === "fm" ? m.deviation_hz : 0);
    const max = peak <= 50e6 ? 10 : peak <= 100e6 ? 5 : 2.5;
    const vpp = toVpp(p.amplitude, p.amplitude_unit);
    if (vpp < .01 - 1e-10 || vpp > max + 1e-10) return `Amplitude must equal 0.01 to ${max} Vpp into 50 Ω for this frequency range.`;
    return "";
  }
  updateHints() {
    const p = this.payload();
    this.fields.frequency.min = String(1e-6 / factors[this.fields.frequency_unit.value]);
    this.fields.mod_frequency.min = String(1e-6 / factors[this.fields.mod_frequency_unit.value]);
    this.root.querySelectorAll("[data-mod]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.mod === this.mode)));
    $(".mod-off", this.root).hidden = this.mode !== "off";
    $(".mod-fields", this.root).hidden = this.mode === "off";
    $(".depth-field", this.root).hidden = this.mode !== "am";
    $(".deviation-field", this.root).hidden = this.mode !== "fm";
    $(".frequency-hint", this.root).textContent = this.mode === "am" ? "1 µHz to 50 MHz with AM" : "1 µHz to 160 MHz";
    const vpp = toVpp(p.amplitude, p.amplitude_unit);
    $(".amplitude-hint", this.root).textContent = `50 Ω load · 0 V offset${p.amplitude_unit !== "Vpp" && Number.isFinite(vpp) ? ` · ${fmt(vpp)} Vpp equivalent` : ""}`;
    $(".mod-hint", this.root).textContent = this.mode === "am" ? "Modulation: 1 µHz–10 MHz · Depth: 0–100%" : `Modulation: 1 µHz–10 MHz · Max deviation: ${compact(Math.max(0, Math.min(p.frequency_hz, 160e6 - p.frequency_hz, 80e6)))}`;
  }
  output(enabled) {
    action(async () => { state = await api(`/channels/${this.number}/output`, "PUT", {enabled}); }, this.error);
  }
  render() {
    const current = state?.channels[this.number - 1];
    if (!this.dirty && current?.settings && JSON.stringify(current.settings) !== this.loadedSignature) this.load(current.settings);
    const connected = Boolean(state?.connected);
    const output = connected ? current?.output_enabled : null;
    const badge = $(".output-badge", this.root);
    badge.textContent = output === true ? "Output on" : output === false ? "Output off" : "Unknown";
    badge.className = `status output-badge ${output === true ? "connected" : output === null ? "unknown" : ""}`;
    const on = $(".output-on", this.root), off = $(".output-off", this.root);
    on.setAttribute("aria-pressed", String(output === true)); off.setAttribute("aria-pressed", String(output === false));
    on.disabled = busy || !connected || !current?.settings || this.dirty;
    off.disabled = busy || !connected;
    on.title = this.dirty ? "Apply your pending changes before enabling output." : !current?.settings ? "Apply channel settings before enabling output." : "Enable this channel's output";
    this.root.querySelectorAll("input,select,[data-mod]").forEach(el => { el.disabled = busy || loading; });
    this.fields.mod_frequency.disabled ||= this.mode === "off";
    this.fields.mod_frequency_unit.disabled ||= this.mode === "off";
    this.fields.depth.disabled ||= this.mode !== "am";
    this.fields.deviation.disabled ||= this.mode !== "fm";
    this.fields.deviation_unit.disabled ||= this.mode !== "fm";
    $(".apply", this.root).disabled = busy || !connected;
    const edit = $(".edit-state", this.root);
    edit.textContent = this.dirty ? "Unapplied changes" : current?.settings ? (state.mode === "demo" ? "Simulated settings" : "Commands accepted") : "Apply to configure";
    edit.classList.toggle("dirty", this.dirty);
    const settings = current?.settings;
    $(".accepted-summary", this.root).textContent = settings ? `${compact(settings.frequency_hz)} · ${fmt(settings.amplitude_vpp)} Vpp · ${fmt(settings.phase_deg)}° · ${settings.modulation.mode.toUpperCase()}` : "Current instrument settings are unknown";
  }
}

function renderStatus() {
  editors.forEach(editor => editor.render());
  if (!state) return;
  const connected = state.connected, demo = state.mode === "demo";
  const badge = $("#connection-status");
  badge.textContent = busy ? "Working…" : connected ? demo ? "Demo active" : "Connected" : "Disconnected";
  badge.className = `status ${connected ? "connected" : ""}`;
  $("#identity").textContent = state.identity || "No instrument connected";
  $("#mode-notice").classList.toggle("lan", !demo);
  $("#mode-notice strong").textContent = demo ? "Demo Mode" : "LAN instrument";
  $("#mode-notice span").textContent = demo ? "Changes are simulated. No instrument is connected." : "Displayed values are last accepted commands, not hardware readback. Disconnect leaves outputs unchanged.";
  $("#state-source").textContent = demo ? "Simulation only" : "Last accepted commands · 50 Ω";
  $("#mode").disabled = busy;
  $("#host").disabled = busy || $("#mode").value === "demo";
  $("#port").disabled = busy || $("#mode").value === "demo";
  $("#test-connection").disabled = busy;
  $("#connect").disabled = busy;
  $("#disconnect").disabled = busy || !connected;
  $("#disconnect").hidden = !connected;
  $("#refresh").disabled = busy || !connected;
  $("#event-count").textContent = `${state.events.length} ${state.events.length === 1 ? "event" : "events"}`;
  const list = $("#events"); list.replaceChildren();
  for (const event of state.events.slice(0, 12)) {
    const li = document.createElement("li"), time = document.createElement("time"), text = document.createElement("span");
    time.dateTime = event.time; time.textContent = new Date(event.time).toLocaleTimeString("en-GB"); text.textContent = event.message;
    li.className = event.kind; li.append(time, text); list.append(li);
  }
  if (!state.events.length) { const li = document.createElement("li"); li.textContent = "Apply a setting to see activity here."; list.append(li); }
}

function connectionPayload() {
  return {mode: $("#mode").value, host: $("#host").value.trim(), port: Number($("#port").value), timeout_s: state?.connection.timeout_s || 3};
}

$("#mode").addEventListener("change", renderStatus);
$("#connection-form").addEventListener("submit", event => {
  event.preventDefault();
  const settings = connectionPayload();
  action(async () => {
    $("#connection-feedback").textContent = "Connecting…";
    if (state?.connected) state = await api("/disconnect", "POST");
    state = await api("/connection", "PUT", settings);
    state = await api("/connect", "POST");
    $("#connection-feedback").textContent = state.mode === "demo" ? "Demo session ready" : "Instrument identity verified";
  }).finally(() => { if (!state?.connected) $("#connection-feedback").textContent = "Connection not established"; });
});
$("#test-connection").addEventListener("click", () => {
  const settings = connectionPayload();
  action(async () => {
    $("#connection-feedback").textContent = "Testing…";
    const result = await api("/connection/test", "POST", settings);
    $("#connection-feedback").textContent = result.mode === "demo" ? "Demo available · no network test" : `Verified: ${result.identity}`;
  }).finally(() => { if ($("#connection-feedback").textContent === "Testing…") $("#connection-feedback").textContent = "Connection test failed"; });
});
$("#disconnect").addEventListener("click", () => action(async () => { state = await api("/disconnect", "POST"); $("#connection-feedback").textContent = "Disconnected"; }));
$("#refresh").addEventListener("click", () => action(async () => { state = await api("/refresh", "POST"); $("#connection-feedback").textContent = "Connection checked"; }));
$("#help-toggle").addEventListener("click", () => {
  const help = $("#help"); help.hidden = !help.hidden;
  $("#help-toggle").setAttribute("aria-expanded", String(!help.hidden));
  if (!help.hidden) help.scrollIntoView({behavior: "auto", block: "start"});
});

editors.push(new ChannelEditor(1), new ChannelEditor(2));
renderStatus();
(async () => {
  try {
    state = await api("/state");
    $("#mode").value = state.connection.mode; $("#host").value = state.connection.host; $("#port").value = state.connection.port;
    state.channels.forEach((channel, i) => { if (channel.settings) editors[i].load(channel.settings); });
    if (state.config_warning) showError(state.config_warning);
  } catch { showError("Cannot reach the controller. Start the Python server and reload this page."); }
  loading = false; renderStatus();
})();

// Poll only the local command cache. Never overwrite unsent edits or send hardware queries.
setInterval(async () => {
  if (busy || loading || document.hidden) return;
  try {
    const fresh = await api("/state");
    if (!busy) {
      state = fresh;
      if (serverOffline) { showError(""); serverOffline = false; }
      renderStatus();
    }
  } catch {
    if (!busy && state) {
      serverOffline = true; state.connected = false;
      showError("The controller server is unreachable. Output state is unknown. Check the server connection.");
      renderStatus();
    }
  }
}, 5000);
