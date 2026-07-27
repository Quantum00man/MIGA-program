const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const defaultEdfaTemplatePowers = {
    edfa0: "3",
    edfa1: "2.4",
    edfa2: "3",
    edfa3: "3",
};

const tabStorageKey = "hardware_controller_active_tab";

let overviewPayload = null;
let websocket = null;
let refreshTimer = null;
let websocketHeartbeat = null;
let refreshDebounce = null;

function showMessage(message, level = "success") {
    const bar = document.getElementById("message-bar");
    bar.textContent = message;
    bar.className = `message-bar ${level}`;
    window.clearTimeout(bar._timerId);
    bar._timerId = window.setTimeout(() => {
        bar.className = "message-bar hidden";
    }, 4200);
}

async function fetchJson(url, options = {}) {
    const settings = {
        ...options,
        headers: {
            ...(options.headers || {}),
        },
    };

    if (settings.body && typeof settings.body !== "string" && !(settings.body instanceof FormData)) {
        settings.headers["Content-Type"] = "application/json";
        settings.body = JSON.stringify(settings.body);
    }

    const response = await fetch(url, settings);
    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Authentication required.");
    }

    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Request failed.");
    }
    return payload;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}

function currentOrigin() {
    return window.location.origin;
}

function renderWeekdayCheckboxes(containerId, prefix, selectedDays = [0, 1, 2, 3, 4]) {
    const container = document.getElementById(containerId);
    container.innerHTML = weekdayLabels
        .map(
            (label, index) => `
                <label class="weekday-pill">
                    <input type="checkbox" data-role="${prefix}-weekday" value="${index}" ${selectedDays.includes(index) ? "checked" : ""}>
                    <span>${label}</span>
                </label>
            `
        )
        .join("");
}

function renderTemplatePowerInputs() {
    const container = document.getElementById("template-powers");
    container.innerHTML = Object.entries(defaultEdfaTemplatePowers)
        .map(
            ([key, value]) => `
                <label>
                    <span>${key}</span>
                    <input type="text" data-role="template-power" data-key="${key}" value="${escapeHtml(value)}">
                </label>
            `
        )
        .join("");
}

function collectTemplateWeekdays() {
    return Array.from(document.querySelectorAll('#template-weekdays [data-role="template-weekday"]:checked')).map((node) => Number(node.value));
}

function badgeClassFromBoolean(value, trueText, falseText, unknownText = "Unknown") {
    if (value === true) {
        return `<span class="device-badge success">${trueText}</span>`;
    }
    if (value === false) {
        return `<span class="device-badge danger">${falseText}</span>`;
    }
    return `<span class="device-badge warning">${unknownText}</span>`;
}

function stateBadgeFromText(text, fallback = "Unknown") {
    const normalized = String(text || fallback).toUpperCase();
    if (normalized === "ON") {
        return `<span class="state-badge success">ON</span>`;
    }
    if (normalized === "OFF") {
        return `<span class="state-badge danger">OFF</span>`;
    }
    return `<span class="state-badge warning">${normalized}</span>`;
}

function statusDotClass(status) {
    if (status === true) {
        return "success";
    }
    if (status === false) {
        return "danger";
    }
    return "warning";
}

function setActiveTab(tabId) {
    document.querySelectorAll(".tab-button").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.tabTarget === tabId);
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("is-active", panel.id === tabId);
    });
    window.localStorage.setItem(tabStorageKey, tabId);
}

function bindTabNavigation() {
    document.querySelectorAll(".tab-button").forEach((button) => {
        button.addEventListener("click", () => setActiveTab(button.dataset.tabTarget));
    });
    const stored = window.localStorage.getItem(tabStorageKey);
    if (stored && document.getElementById(stored)) {
        setActiveTab(stored);
    }
}

function buildSummaryCards(items) {
    return items
        .map(
            (item) => `
                <div class="summary-card">
                    <span class="label">${item.label}</span>
                    <div class="value">${item.value}</div>
                </div>
            `
        )
        .join("");
}

function summarizeDevices(devices, predicate) {
    return devices.filter(predicate).length;
}

function getEdfaRuntimeStatus(device) {
    const outputActive = (device.channels || []).some((channel) => channel.assumed_on);
    return {
        online: device.reachable,
        outputActive,
    };
}

function getPsuRuntimeStatus(device) {
    const states = device.channel_states || {};
    const outputActive = Object.values(states).some((value) => String(value).toUpperCase() === "ON");
    return {
        online: device.reachable,
        outputActive,
    };
}

function renderSummary(data) {
    const state = data.state;
    const runtime = data.runtime;
    const edfaDevices = state.edfa_devices || [];
    const psuDevices = state.psu_devices || [];

    document.getElementById("summary-grid").innerHTML = buildSummaryCards([
        { label: "EDFA Systems", value: edfaDevices.length },
        { label: "Power Supplies", value: psuDevices.length },
        { label: "Online EDFA", value: summarizeDevices(edfaDevices, (device) => device.reachable === true) },
        { label: "Online PSU", value: summarizeDevices(psuDevices, (device) => device.reachable === true) },
    ]);

    document.getElementById("service-meta").innerHTML = `
        <div class="meta-card"><span class="meta-label">Listening Origin</span><div class="meta-line">${currentOrigin()}</div></div>
        <div class="meta-card"><span class="meta-label">Last State Update</span><div class="meta-line">${escapeHtml(state.metadata.updated_at)}</div></div>
        <div class="meta-card"><span class="meta-label">Snapshot Time</span><div class="meta-line">${escapeHtml(runtime.generated_at)}</div></div>
    `;

    document.getElementById("origin-label").textContent = currentOrigin();
    document.getElementById("scheduler-indicator").textContent = runtime.scheduler.active ? "Scheduler: Active" : "Scheduler: Monitoring";
}

function renderEdfaSummary(devices) {
    document.getElementById("edfa-summary-grid").innerHTML = buildSummaryCards([
        { label: "Configured EDFA", value: devices.length },
        { label: "Online EDFA", value: summarizeDevices(devices, (device) => getEdfaRuntimeStatus(device).online === true) },
        { label: "Active Output Sets", value: summarizeDevices(devices, (device) => getEdfaRuntimeStatus(device).outputActive) },
        { label: "Scheduled Devices", value: summarizeDevices(devices, (device) => device.schedule && device.schedule.enabled) },
    ]);
}

function renderPsuSummary(devices) {
    document.getElementById("psu-summary-grid").innerHTML = buildSummaryCards([
        { label: "Configured PSU", value: devices.length },
        { label: "Online PSU", value: summarizeDevices(devices, (device) => getPsuRuntimeStatus(device).online === true) },
        { label: "Active Outputs", value: summarizeDevices(devices, (device) => getPsuRuntimeStatus(device).outputActive) },
        { label: "Scheduled Channels", value: summarizeDevices(devices, (device) => Object.values((device.schedule && device.schedule.channels) || {}).some((channel) => channel.enabled)) },
    ]);
}

function weekdayCheckboxGroup(selectedDays, rolePrefix) {
    return weekdayLabels
        .map(
            (label, index) => `
                <label class="weekday-pill">
                    <input type="checkbox" data-role="${rolePrefix}" value="${index}" ${selectedDays.includes(index) ? "checked" : ""}>
                    <span>${label}</span>
                </label>
            `
        )
        .join("");
}

function renderEdfaDevices(devices) {
    const container = document.getElementById("edfa-device-list");
    if (!devices.length) {
        container.innerHTML = '<div class="empty-state">No EDFA systems are configured yet.</div>';
        return;
    }

    container.innerHTML = devices.map((device) => {
        const runtime = getEdfaRuntimeStatus(device);
        const scheduleDays = device.schedule.days || [];
        const channelTiles = (device.channels || []).map((channel) => `
            <div class="channel-tile">
                <div class="channel-tile-header">
                    <span class="channel-name">${escapeHtml(channel.key)}</span>
                    ${stateBadgeFromText(channel.assumed_on ? "ON" : "OFF")}
                </div>
                <label>
                    <span>Power</span>
                    <input type="text" data-field="channel-power" data-key="${channel.key}" value="${escapeHtml(channel.power)}">
                </label>
                <div class="device-actions">
                    <button class="inline-button" data-action="edfa-channel-on" data-device-id="${device.id}" data-channel-key="${channel.key}">Turn ON</button>
                    <button class="inline-button inline-danger" data-action="edfa-channel-off" data-device-id="${device.id}" data-channel-key="${channel.key}">Turn OFF</button>
                </div>
            </div>
        `).join("");

        return `
            <article class="device-card" data-device-type="edfa" data-device-id="${device.id}">
                <div class="device-header">
                    <div>
                        <div class="device-title-row">
                            <span class="status-dot ${statusDotClass(runtime.outputActive)}"></span>
                            <h3>${escapeHtml(device.name)}</h3>
                        </div>
                        <div class="device-subtitle">${escapeHtml(device.ip)}:${escapeHtml(device.port)}</div>
                    </div>
                    <div class="info-badges">
                        ${badgeClassFromBoolean(runtime.online, "Network Online", "Network Offline")}
                        ${runtime.outputActive ? '<span class="device-badge success">Output Active</span>' : '<span class="device-badge danger">Output Off</span>'}
                    </div>
                </div>

                <div class="device-card-body">
                    <div class="device-card-section">
                        <div class="panel-title-row">
                            <h4>Connection and Device Parameters</h4>
                            <span class="panel-note">IP address and timing can be edited directly here.</span>
                        </div>
                        <div class="detail-grid">
                            <label><span>Name</span><input type="text" data-field="name" value="${escapeHtml(device.name)}"></label>
                            <label><span>IP Address</span><input type="text" data-field="ip" value="${escapeHtml(device.ip)}"></label>
                            <label><span>Port</span><input type="number" data-field="port" value="${escapeHtml(device.port)}"></label>
                            <label><span>Timeout (s)</span><input type="number" step="0.1" data-field="timeout_sec" value="${escapeHtml(device.timeout_sec)}"></label>
                            <label><span>Command Delay (s)</span><input type="number" step="0.1" data-field="command_delay_sec" value="${escapeHtml(device.command_delay_sec)}"></label>
                            <label><span>Notes</span><input type="text" data-field="notes" value="${escapeHtml(device.notes || "")}"></label>
                        </div>
                        <div class="device-actions">
                            <button class="inline-button" data-action="edfa-save" data-device-id="${device.id}">Save Configuration</button>
                            <button class="inline-button" data-action="edfa-probe" data-device-id="${device.id}">Probe Connection</button>
                            <button class="inline-button" data-action="edfa-all-on" data-device-id="${device.id}">Start This Device</button>
                            <button class="inline-button inline-danger" data-action="edfa-all-off" data-device-id="${device.id}">Shutdown This Device</button>
                            <button class="inline-button inline-danger" data-action="edfa-delete" data-device-id="${device.id}">Delete</button>
                        </div>
                    </div>

                    <div class="device-card-section">
                        <div class="panel-title-row">
                            <h4>Channel Control</h4>
                            <span class="panel-note">Green and red show the command-tracked output state for each channel.</span>
                        </div>
                        <div class="channel-grid">${channelTiles}</div>
                    </div>

                    <div class="device-card-section">
                        <div class="panel-title-row">
                            <h4>Weekly Schedule</h4>
                            <label class="selection-row">
                                <input type="checkbox" data-field="schedule-enabled" ${device.schedule.enabled ? "checked" : ""}>
                                <span>Enable schedule</span>
                            </label>
                        </div>
                        <div class="form-grid">
                            <label><span>Auto-ON</span><input type="text" data-field="schedule-on-time" value="${escapeHtml(device.schedule.on_time || "")}" placeholder="08:00"></label>
                            <label><span>Auto-OFF</span><input type="text" data-field="schedule-off-time" value="${escapeHtml(device.schedule.off_time || "")}" placeholder="18:00"></label>
                        </div>
                        <div class="weekday-row">${weekdayCheckboxGroup(scheduleDays, `edfa-weekday-${device.id}`)}</div>
                    </div>

                    <div class="device-card-section">
                        <div class="detail-grid">
                            <div><span class="meta-label">Last Action</span><div class="device-meta">${escapeHtml(device.last_action || "--")}</div></div>
                            <div><span class="meta-label">Last Contact</span><div class="device-meta">${escapeHtml(device.last_contact_at || "--")}</div></div>
                            <div><span class="meta-label">Last Error</span><div class="device-meta">${escapeHtml(device.last_error || "None")}</div></div>
                        </div>
                    </div>
                </div>
            </article>
        `;
    }).join("");
}

function renderPsuDevices(devices) {
    const container = document.getElementById("psu-device-list");
    if (!devices.length) {
        container.innerHTML = '<div class="empty-state">No power supply systems are configured yet.</div>';
        return;
    }

    container.innerHTML = devices.map((device) => {
        const runtime = getPsuRuntimeStatus(device);
        const channelSchedules = (device.schedule && device.schedule.channels) || {};
        const channelTiles = ["1", "2"].map((channel) => {
            const channelSchedule = channelSchedules[channel] || { enabled: false, days: [], on_time: "", off_time: "" };
            const channelState = (device.channel_states || {})[channel] || "unknown";

            return `
                <div class="psu-channel-tile">
                    <div class="psu-channel-header">
                        <span class="channel-name">CH${channel}</span>
                        ${stateBadgeFromText(channelState)}
                    </div>
                    <div class="device-actions">
                        <button class="inline-button" data-action="psu-channel-on" data-device-id="${device.id}" data-channel="${channel}">Turn ON</button>
                        <button class="inline-button inline-danger" data-action="psu-channel-off" data-device-id="${device.id}" data-channel="${channel}">Turn OFF</button>
                    </div>
                    <div class="schedule-tile">
                        <div class="panel-title-row">
                            <h4>Schedule</h4>
                            <label class="selection-row">
                                <input type="checkbox" data-field="schedule-enabled-${channel}" ${channelSchedule.enabled ? "checked" : ""}>
                                <span>Enable</span>
                            </label>
                        </div>
                        <div class="form-grid">
                            <label><span>Auto-ON</span><input type="text" data-field="schedule-on-time-${channel}" value="${escapeHtml(channelSchedule.on_time || "")}" placeholder="08:00"></label>
                            <label><span>Auto-OFF</span><input type="text" data-field="schedule-off-time-${channel}" value="${escapeHtml(channelSchedule.off_time || "")}" placeholder="18:00"></label>
                        </div>
                        <div class="weekday-row">${weekdayCheckboxGroup(channelSchedule.days || [], `psu-weekday-${device.id}-${channel}`)}</div>
                    </div>
                </div>
            `;
        }).join("");

        return `
            <article class="device-card" data-device-type="psu" data-device-id="${device.id}">
                <div class="device-header">
                    <div>
                        <div class="device-title-row">
                            <span class="status-dot ${statusDotClass(runtime.outputActive)}"></span>
                            <h3>${escapeHtml(device.name)}</h3>
                        </div>
                        <div class="device-subtitle">${escapeHtml(device.ip)}:${escapeHtml(device.port)}</div>
                    </div>
                    <div class="info-badges">
                        ${badgeClassFromBoolean(runtime.online, "Network Online", "Network Offline")}
                        ${runtime.outputActive ? '<span class="device-badge success">Output Active</span>' : '<span class="device-badge danger">Output Off</span>'}
                    </div>
                </div>

                <div class="device-card-body">
                    <div class="device-card-section">
                        <div class="panel-title-row">
                            <h4>Connection and Device Parameters</h4>
                            <span class="panel-note">Each PSU keeps its own IP address and timeout.</span>
                        </div>
                        <div class="detail-grid">
                            <label><span>Name</span><input type="text" data-field="name" value="${escapeHtml(device.name)}"></label>
                            <label><span>IP Address</span><input type="text" data-field="ip" value="${escapeHtml(device.ip)}"></label>
                            <label><span>Port</span><input type="number" data-field="port" value="${escapeHtml(device.port)}"></label>
                            <label><span>Timeout (s)</span><input type="number" step="0.1" data-field="timeout_sec" value="${escapeHtml(device.timeout_sec)}"></label>
                            <label><span>Notes</span><input type="text" data-field="notes" value="${escapeHtml(device.notes || "")}"></label>
                        </div>
                        <div class="device-actions">
                            <button class="inline-button" data-action="psu-save" data-device-id="${device.id}">Save Configuration</button>
                            <button class="inline-button" data-action="psu-probe" data-device-id="${device.id}">Probe And Read ID</button>
                            <button class="inline-button" data-action="psu-refresh" data-device-id="${device.id}">Refresh State</button>
                            <button class="inline-button" data-action="psu-independent" data-device-id="${device.id}">Set Independent Mode</button>
                            <button class="inline-button" data-action="psu-disconnect" data-device-id="${device.id}">Disconnect</button>
                            <button class="inline-button inline-danger" data-action="psu-delete" data-device-id="${device.id}">Delete</button>
                        </div>
                    </div>

                    <div class="device-card-section">
                        <div class="detail-grid">
                            <div><span class="meta-label">Instrument ID</span><div class="device-meta">${escapeHtml(device.idn || "--")}</div></div>
                            <div><span class="meta-label">CONFIG?</span><div class="device-meta">${escapeHtml(device.config_mode || "--")}</div></div>
                            <div><span class="meta-label">Last Action</span><div class="device-meta">${escapeHtml(device.last_action || "--")}</div></div>
                            <div><span class="meta-label">Last Error</span><div class="device-meta">${escapeHtml(device.last_error || "None")}</div></div>
                        </div>
                    </div>

                    <div class="device-card-section">
                        <div class="panel-title-row">
                            <h4>Channel Control and Schedule</h4>
                            <span class="panel-note">Green and red indicate the last readback state for each PSU channel.</span>
                        </div>
                        <div class="psu-channel-grid">${channelTiles}</div>
                    </div>
                </div>
            </article>
        `;
    }).join("");
}

function renderEventLog(events) {
    const container = document.getElementById("event-log");
    if (!events.length) {
        container.innerHTML = '<div class="empty-state">No events have been recorded in this session.</div>';
        return;
    }
    container.innerHTML = events
        .map(
            (event) => `
                <div class="event-item ${escapeHtml(event.level)}">
                    <div class="event-meta">
                        <span>${escapeHtml(event.category || "system")}</span>
                        <span>${escapeHtml(event.timestamp || "--")}</span>
                    </div>
                    <div class="event-message">${escapeHtml(event.message || "")}</div>
                </div>
            `
        )
        .join("");
}

function scheduleOverviewRefresh() {
    window.clearTimeout(refreshDebounce);
    refreshDebounce = window.setTimeout(loadOverview, 180);
}

function readEdfaCardPayload(card) {
    const deviceId = card.dataset.deviceId;
    const scheduleDays = Array.from(card.querySelectorAll(`[data-role="edfa-weekday-${deviceId}"]:checked`)).map((node) => Number(node.value));
    const channels = Array.from(card.querySelectorAll('[data-field="channel-power"]')).map((node) => ({
        key: node.dataset.key,
        power: node.value.trim(),
    }));

    return {
        name: card.querySelector('[data-field="name"]').value.trim(),
        ip: card.querySelector('[data-field="ip"]').value.trim(),
        port: Number(card.querySelector('[data-field="port"]').value),
        timeout_sec: Number(card.querySelector('[data-field="timeout_sec"]').value),
        command_delay_sec: Number(card.querySelector('[data-field="command_delay_sec"]').value),
        notes: card.querySelector('[data-field="notes"]').value.trim(),
        channels,
        schedule: {
            enabled: card.querySelector('[data-field="schedule-enabled"]').checked,
            days: scheduleDays,
            on_time: card.querySelector('[data-field="schedule-on-time"]').value.trim(),
            off_time: card.querySelector('[data-field="schedule-off-time"]').value.trim(),
        },
    };
}

function readPsuCardPayload(card) {
    const deviceId = card.dataset.deviceId;
    const buildChannelSchedule = (channel) => ({
        enabled: card.querySelector(`[data-field="schedule-enabled-${channel}"]`).checked,
        days: Array.from(card.querySelectorAll(`[data-role="psu-weekday-${deviceId}-${channel}"]:checked`)).map((node) => Number(node.value)),
        on_time: card.querySelector(`[data-field="schedule-on-time-${channel}"]`).value.trim(),
        off_time: card.querySelector(`[data-field="schedule-off-time-${channel}"]`).value.trim(),
    });

    return {
        name: card.querySelector('[data-field="name"]').value.trim(),
        ip: card.querySelector('[data-field="ip"]').value.trim(),
        port: Number(card.querySelector('[data-field="port"]').value),
        timeout_sec: Number(card.querySelector('[data-field="timeout_sec"]').value),
        notes: card.querySelector('[data-field="notes"]').value.trim(),
        schedule: {
            channels: {
                "1": buildChannelSchedule("1"),
                "2": buildChannelSchedule("2"),
            },
        },
    };
}

async function loadOverview() {
    const payload = await fetchJson("/api/overview");
    overviewPayload = payload.data;
    renderSummary(overviewPayload);
    renderEdfaSummary(overviewPayload.state.edfa_devices || []);
    renderPsuSummary(overviewPayload.state.psu_devices || []);
    renderEdfaDevices(overviewPayload.state.edfa_devices || []);
    renderPsuDevices(overviewPayload.state.psu_devices || []);
    renderEventLog(overviewPayload.runtime.events || []);
}

function startPolling() {
    window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(loadOverview, 25000);
}

function connectWebSocket() {
    if (websocket) {
        websocket.close();
    }
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    websocket = new WebSocket(`${scheme}://${window.location.host}/ws`);

    websocket.onopen = () => {
        document.getElementById("ws-indicator").textContent = "WS: Connected";
        window.clearInterval(websocketHeartbeat);
        websocketHeartbeat = window.setInterval(() => {
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send("ping");
            }
        }, 20000);
    };

    websocket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === "state") {
            scheduleOverviewRefresh();
            return;
        }
        if (payload.type === "event" && overviewPayload && overviewPayload.runtime) {
            overviewPayload.runtime.events = [payload, ...(overviewPayload.runtime.events || [])].slice(0, 80);
            renderEventLog(overviewPayload.runtime.events);
        }
    };

    websocket.onclose = () => {
        document.getElementById("ws-indicator").textContent = "WS: Reconnecting";
        window.clearInterval(websocketHeartbeat);
        window.setTimeout(connectWebSocket, 2500);
    };

    websocket.onerror = () => {
        document.getElementById("ws-indicator").textContent = "WS: Error";
    };
}

async function runPsuBatch(turnOn) {
    const devices = (overviewPayload && overviewPayload.state && overviewPayload.state.psu_devices) || [];
    if (!devices.length) {
        throw new Error("No PSU devices are configured.");
    }

    const failures = [];
    for (const device of devices) {
        for (const channel of ["1", "2"]) {
            try {
                await fetchJson(`/api/psu/devices/${device.id}/channels/${channel}/${turnOn ? "on" : "off"}`, {
                    method: "POST",
                });
            } catch (error) {
                failures.push(`${device.name} CH${channel}: ${error.message}`);
            }
        }
    }

    if (failures.length) {
        throw new Error(failures.join(" | "));
    }
}

async function handleFormSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;

    if (form.id === "add-edfa-form") {
        const formData = new FormData(form);
        await fetchJson("/api/edfa/devices", {
            method: "POST",
            body: {
                name: formData.get("name"),
                ip: formData.get("ip"),
                port: Number(formData.get("port")),
                timeout_sec: Number(formData.get("timeout_sec")),
                command_delay_sec: Number(formData.get("command_delay_sec")),
                notes: formData.get("notes"),
                channels: Object.entries(defaultEdfaTemplatePowers).map(([key, power]) => ({ key, power })),
            },
        });
        form.reset();
        form.querySelector('[name="port"]').value = "23";
        form.querySelector('[name="timeout_sec"]').value = "3";
        form.querySelector('[name="command_delay_sec"]').value = "1";
        showMessage("EDFA device added.");
        await loadOverview();
        return;
    }

    if (form.id === "add-psu-form") {
        const formData = new FormData(form);
        await fetchJson("/api/psu/devices", {
            method: "POST",
            body: {
                name: formData.get("name"),
                ip: formData.get("ip"),
                port: Number(formData.get("port")),
                timeout_sec: Number(formData.get("timeout_sec")),
                notes: formData.get("notes"),
            },
        });
        form.reset();
        form.querySelector('[name="port"]').value = "9221";
        form.querySelector('[name="timeout_sec"]').value = "3";
        showMessage("PSU device added.");
        await loadOverview();
        return;
    }

    if (form.id === "password-form") {
        const formData = new FormData(form);
        await fetchJson("/auth/password", {
            method: "POST",
            body: {
                current_password: formData.get("current_password"),
                new_password: formData.get("new_password"),
            },
        });
        form.reset();
        showMessage("Password updated.");
        return;
    }

    if (form.id === "edfa-template-form") {
        const channels = Array.from(document.querySelectorAll('[data-role="template-power"]')).map((node) => ({
            key: node.dataset.key,
            power: node.value.trim(),
        }));
        await fetchJson("/api/edfa/template/apply", {
            method: "POST",
            body: {
                device_ids: [],
                channels,
                schedule: {
                    enabled: document.getElementById("template-schedule-enabled").checked,
                    days: collectTemplateWeekdays(),
                    on_time: document.getElementById("template-on-time").value.trim(),
                    off_time: document.getElementById("template-off-time").value.trim(),
                },
            },
        });
        showMessage("EDFA preset applied to all devices.");
        await loadOverview();
    }
}

async function handleClick(event) {
    const target = event.target.closest("button");
    if (!target) {
        return;
    }

    try {
        if (target.id === "refresh-button") {
            await loadOverview();
            showMessage("State refreshed.");
            return;
        }

        if (target.id === "logout-button") {
            await fetchJson("/auth/logout", { method: "POST" });
            window.location.href = "/login";
            return;
        }

        if (target.id === "download-manual-button") {
            window.location.href = "/api/manual/download";
            return;
        }

        if (target.id === "edfa-batch-on") {
            await fetchJson("/api/edfa/batch/on", { method: "POST", body: { device_ids: [] } });
            showMessage("All EDFA devices received the ON command.");
            await loadOverview();
            return;
        }

        if (target.id === "edfa-batch-off") {
            await fetchJson("/api/edfa/batch/off", { method: "POST", body: { device_ids: [] } });
            showMessage("All EDFA devices received the shutdown command.");
            await loadOverview();
            return;
        }

        if (target.id === "psu-batch-on") {
            await runPsuBatch(true);
            showMessage("All PSU outputs received the ON command.");
            await loadOverview();
            return;
        }

        if (target.id === "psu-batch-off") {
            await runPsuBatch(false);
            showMessage("All PSU outputs received the OFF command.");
            await loadOverview();
            return;
        }

        const action = target.dataset.action;
        if (!action) {
            return;
        }

        const deviceId = target.dataset.deviceId;
        const channelKey = target.dataset.channelKey;
        const channel = target.dataset.channel;
        const card = target.closest(".device-card");

        if (action === "edfa-save") {
            await fetchJson(`/api/edfa/devices/${deviceId}`, { method: "PUT", body: readEdfaCardPayload(card) });
            showMessage("EDFA configuration saved.");
        } else if (action === "edfa-probe") {
            await fetchJson(`/api/edfa/devices/${deviceId}/probe`, { method: "POST" });
            showMessage("EDFA probe completed.");
        } else if (action === "edfa-all-on") {
            await fetchJson(`/api/edfa/devices/${deviceId}/all/on`, { method: "POST" });
            showMessage("EDFA device started.");
        } else if (action === "edfa-all-off") {
            await fetchJson(`/api/edfa/devices/${deviceId}/all/off`, { method: "POST" });
            showMessage("EDFA device shut down.");
        } else if (action === "edfa-delete") {
            if (!window.confirm("Remove this EDFA device from the controller?")) {
                return;
            }
            await fetchJson(`/api/edfa/devices/${deviceId}`, { method: "DELETE" });
            showMessage("EDFA device removed.");
        } else if (action === "edfa-channel-on") {
            const power = card.querySelector(`[data-field="channel-power"][data-key="${channelKey}"]`).value.trim();
            await fetchJson(`/api/edfa/devices/${deviceId}/channels/${channelKey}/on`, { method: "POST", body: { power } });
            showMessage(`${channelKey} turned ON.`);
        } else if (action === "edfa-channel-off") {
            await fetchJson(`/api/edfa/devices/${deviceId}/channels/${channelKey}/off`, { method: "POST" });
            showMessage(`${channelKey} turned OFF.`);
        } else if (action === "psu-save") {
            await fetchJson(`/api/psu/devices/${deviceId}`, { method: "PUT", body: readPsuCardPayload(card) });
            showMessage("PSU configuration saved.");
        } else if (action === "psu-probe") {
            await fetchJson(`/api/psu/devices/${deviceId}/probe`, { method: "POST" });
            showMessage("PSU probe completed.");
        } else if (action === "psu-refresh") {
            await fetchJson(`/api/psu/devices/${deviceId}/refresh`, { method: "POST" });
            showMessage("PSU state refreshed.");
        } else if (action === "psu-independent") {
            await fetchJson(`/api/psu/devices/${deviceId}/independent-mode`, { method: "POST" });
            showMessage("PSU independent mode applied.");
        } else if (action === "psu-disconnect") {
            await fetchJson(`/api/psu/devices/${deviceId}/disconnect`, { method: "POST" });
            showMessage("PSU session closed.");
        } else if (action === "psu-delete") {
            if (!window.confirm("Remove this PSU device from the controller?")) {
                return;
            }
            await fetchJson(`/api/psu/devices/${deviceId}`, { method: "DELETE" });
            showMessage("PSU device removed.");
        } else if (action === "psu-channel-on") {
            await fetchJson(`/api/psu/devices/${deviceId}/channels/${channel}/on`, { method: "POST" });
            showMessage(`PSU CH${channel} turned ON.`);
        } else if (action === "psu-channel-off") {
            await fetchJson(`/api/psu/devices/${deviceId}/channels/${channel}/off`, { method: "POST" });
            showMessage(`PSU CH${channel} turned OFF.`);
        }

        await loadOverview();
    } catch (error) {
        showMessage(error.message, "error");
    }
}

function bindFormsAndButtons() {
    document.getElementById("add-edfa-form").addEventListener("submit", (event) => handleFormSubmit(event).catch((error) => showMessage(error.message, "error")));
    document.getElementById("add-psu-form").addEventListener("submit", (event) => handleFormSubmit(event).catch((error) => showMessage(error.message, "error")));
    document.getElementById("password-form").addEventListener("submit", (event) => handleFormSubmit(event).catch((error) => showMessage(error.message, "error")));
    document.getElementById("edfa-template-form").addEventListener("submit", (event) => handleFormSubmit(event).catch((error) => showMessage(error.message, "error")));
    document.body.addEventListener("click", (event) => {
        handleClick(event).catch((error) => showMessage(error.message, "error"));
    });
}

async function initialize() {
    renderWeekdayCheckboxes("template-weekdays", "template", [0, 1, 2, 3, 4]);
    renderTemplatePowerInputs();
    bindTabNavigation();
    bindFormsAndButtons();
    connectWebSocket();
    startPolling();
    await loadOverview();
}

initialize().catch((error) => {
    showMessage(error.message, "error");
});
