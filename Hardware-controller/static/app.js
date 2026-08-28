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
let lastOverviewAt = 0;
const dirtyEdfaDevices = new Set();
const dirtyPsuDevices = new Set();

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

function stateClassFromText(text, fallback = "unknown") {
    const normalized = String(text || fallback).toUpperCase();
    if (normalized === "ON") {
        return "state-on";
    }
    if (normalized === "OFF") {
        return "state-off";
    }
    return "state-unknown";
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
    const laserLocks = Object.values(runtime.laser_locks || {});

    document.getElementById("summary-grid").innerHTML = buildSummaryCards([
        { label: "EDFA Systems", value: edfaDevices.length },
        { label: "Power Supplies", value: psuDevices.length },
        { label: "Laser Locks", value: laserLocks.length || 4 },
        { label: "Online EDFA", value: summarizeDevices(edfaDevices, (device) => device.reachable === true) },
        { label: "Online PSU", value: summarizeDevices(psuDevices, (device) => device.reachable === true) },
        { label: "Active Laser Locks", value: laserLocks.filter((channel) => channel.status === "LOCK_ACTIVE").length },
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

function laserStatusClass(status) {
    const normalized = String(status || "IDLE").toUpperCase();
    if (normalized === "LOCK_ACTIVE") {
        return "success";
    }
    if (["ERROR", "DISCONNECTED", "DELOCKED"].includes(normalized)) {
        return "danger";
    }
    if (["CONNECTING", "INITIALIZING", "SCANNING", "ANALYZING", "ACQUIRING", "VERIFYING", "STALE"].includes(normalized)) {
        return "warning";
    }
    return "neutral";
}

function laserStatusLabel(status) {
    return String(status || "IDLE").replaceAll("_", " ");
}

function renderLaserLockSummary(system, channels) {
    const values = Object.values(channels || {});
    document.getElementById("laser-lock-summary-grid").innerHTML = buildSummaryCards([
        { label: "Controller", value: system && system.ip ? escapeHtml(system.ip) : "Not configured" },
        { label: "Fixed Channels", value: values.length || 4 },
        { label: "Active Locks", value: values.filter((channel) => channel.status === "LOCK_ACTIVE").length },
        { label: "Live Connections", value: values.filter((channel) => channel.connected).length },
    ]);
}

function populateLaserLockForm(system) {
    const form = document.getElementById("laser-lock-form");
    if (!form || form.contains(document.activeElement)) {
        return;
    }
    form.elements.name.value = system.name || "MIGA2 Laser Lock";
    form.elements.ip.value = system.ip || "";
    form.elements.port.value = system.port || 23;
    form.elements.timeout_sec.value = system.timeout_sec || 3;
    form.elements.notes.value = system.notes || "";
}

function renderLaserLockChannels(channels) {
    const container = document.getElementById("laser-lock-channel-grid");
    const expandedChannels = new Set(
        Array.from(container.querySelectorAll(".laser-output[open]"))
            .map((details) => details.closest("[data-laser-channel]")?.dataset.laserChannel)
            .filter(Boolean)
    );
    const orderedKeys = ["master", "slave_2d", "slave_3d", "repump"];
    container.innerHTML = orderedKeys.map((key) => {
        const channel = channels[key] || {
            key,
            label: key,
            status: "IDLE",
            command: "--",
            recent_output: [],
        };
        const progress = channel.scan_progress === null || channel.scan_progress === undefined
            ? "--"
            : `${channel.scan_progress}%`;
        const pllError = channel.pllerror === null || channel.pllerror === undefined
            ? "--"
            : `${Number(channel.pllerror).toFixed(6)} V`;
        const pidOut = channel.pid_out === null || channel.pid_out === undefined
            ? "--"
            : Number(channel.pid_out).toFixed(6);
        const masterMetrics = `
            <div><span class="meta-label">Scan Attempt</span><div class="metric-value">${
                channel.scan_index === null || channel.scan_index === undefined
                    ? "--"
                    : `${escapeHtml(channel.scan_index)} / ${escapeHtml(channel.scan_total ?? "--")}`
            }</div></div>
            <div><span class="meta-label">Scan Progress</span><div class="metric-value">${escapeHtml(progress)}</div></div>
            <div><span class="meta-label">Absorption</span><div class="metric-value">${
                channel.absorption === null || channel.absorption === undefined
                    ? "--"
                    : `${Number(channel.absorption).toFixed(6)} V`
            }</div></div>
            <div><span class="meta-label">Selected Peak</span><div class="metric-value">${escapeHtml(channel.selected_peak_ctrl ?? "--")}</div></div>
            <div><span class="meta-label">Lock Absorption</span><div class="metric-value">${
                channel.lock_absorption === null || channel.lock_absorption === undefined
                    ? "--"
                    : `${Number(channel.lock_absorption).toFixed(6)} V`
            }</div></div>
            <div><span class="meta-label">Controller Output</span><div class="metric-value">${
                channel.controller_output === null || channel.controller_output === undefined
                    ? "--"
                    : Number(channel.controller_output).toFixed(6)
            }</div></div>
            <div><span class="meta-label">Lock Check Count</span><div class="metric-value">${escapeHtml(channel.lock_check_count ?? "--")}</div></div>
            <div><span class="meta-label">Delock Events</span><div class="metric-value">${escapeHtml(channel.delock_count ?? 0)}</div></div>
            <div><span class="meta-label">Last Delock Jump</span><div class="metric-value">${
                channel.delock_from === null || channel.delock_from === undefined
                    ? "--"
                    : `${Number(channel.delock_from).toFixed(4)} → ${Number(channel.delock_to).toFixed(4)} V`
            }</div></div>
            <div><span class="meta-label">Last Update</span><div class="metric-value metric-time">${escapeHtml(channel.last_update || "--")}</div></div>
        `;
        const slaveMetrics = `
            <div><span class="meta-label">Scan</span><div class="metric-value">${escapeHtml(progress)}</div></div>
            <div><span class="meta-label">PLL Error</span><div class="metric-value">${escapeHtml(pllError)}</div></div>
            <div><span class="meta-label">PID Output</span><div class="metric-value">${escapeHtml(pidOut)}</div></div>
            <div><span class="meta-label">Control</span><div class="metric-value">${escapeHtml(channel.ctrltemp ?? "--")}</div></div>
            <div><span class="meta-label">Lock Control</span><div class="metric-value">${escapeHtml(channel.lockctrl ?? "--")}</div></div>
            <div><span class="meta-label">Last Update</span><div class="metric-value metric-time">${escapeHtml(channel.last_update || "--")}</div></div>
        `;
        const output = (channel.recent_output || []).slice(-18).join("\n") || "No output received yet.";

        return `
            <article class="laser-lock-card" data-laser-channel="${escapeHtml(key)}">
                <div class="laser-lock-card-header">
                    <div>
                        <div class="device-title-row">
                            <span class="status-dot ${laserStatusClass(channel.status)}"></span>
                            <h3>${escapeHtml(channel.label)}</h3>
                        </div>
                        <div class="device-subtitle">${escapeHtml(channel.command)}</div>
                    </div>
                    <span class="state-badge ${laserStatusClass(channel.status)}">${escapeHtml(laserStatusLabel(channel.status))}</span>
                </div>

                <div class="laser-metrics">
                    ${key === "master" ? masterMetrics : slaveMetrics}
                </div>

                <div class="device-actions">
                    <button class="inline-button" data-action="laser-lock-start" data-channel-key="${escapeHtml(key)}">Start Lock</button>
                    <button class="inline-button" data-action="laser-lock-relock" data-channel-key="${escapeHtml(key)}">Relock</button>
                </div>

                <details class="laser-output">
                    <summary>Recent device output</summary>
                    <pre>${escapeHtml(output)}</pre>
                </details>
                ${channel.last_error ? `<div class="laser-error">${escapeHtml(channel.last_error)}</div>` : ""}
            </article>
        `;
    }).join("");
    container.querySelectorAll("[data-laser-channel]").forEach((card) => {
        if (expandedChannels.has(card.dataset.laserChannel)) {
            card.querySelector(".laser-output")?.setAttribute("open", "");
        }
    });
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
    if (dirtyEdfaDevices.size > 0 && container.children.length > 0) {
        return;
    }
    if (!devices.length) {
        container.innerHTML = '<div class="empty-state">No EDFA systems are configured yet.</div>';
        return;
    }

    container.innerHTML = devices.map((device) => {
        const runtime = getEdfaRuntimeStatus(device);
        const scheduleDays = device.schedule.days || [];
        const channelTiles = (device.channels || []).map((channel) => {
            const channelStateText = channel.assumed_on ? "ON" : "OFF";
            return `
                <div class="channel-tile ${stateClassFromText(channelStateText)}">
                    <div class="channel-tile-header">
                        <span class="channel-name">${escapeHtml(channel.key)}</span>
                        ${stateBadgeFromText(channelStateText)}
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
            `;
        }).join("");

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
                            <span class="panel-note">Each channel card now uses a full-state surface. Green means ON, red means OFF.</span>
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
                        <div class="schedule-apply-row">
                            <span class="panel-note">Schedule changes take effect after they are applied.</span>
                            <button class="action-button" data-action="edfa-save-schedule" data-device-id="${device.id}">Apply Schedule</button>
                        </div>
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
    if (dirtyPsuDevices.size > 0 && container.children.length > 0) {
        return;
    }
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
                <div class="psu-channel-tile ${stateClassFromText(channelState)}">
                    <div class="psu-channel-header">
                        <span class="channel-name">CH${channel}</span>
                        ${stateBadgeFromText(channelState)}
                    </div>
                    <div class="device-actions">
                        <button class="inline-button" data-action="psu-channel-on" data-device-id="${device.id}" data-channel="${channel}">Turn ON</button>
                        <button class="inline-button inline-danger" data-action="psu-channel-off" data-device-id="${device.id}" data-channel="${channel}">Turn OFF</button>
                    </div>
                    <div class="schedule-tile">
                        <div class="schedule-tile-title-row">
                            <h5 class="schedule-tile-title">Channel Schedule</h5>
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
                            <span class="panel-note">Edit the channel schedules, then apply them with the button below.</span>
                        </div>
                        <div class="psu-channel-grid">${channelTiles}</div>
                        <div class="schedule-apply-row">
                            <span class="panel-note">Schedule changes are saved locally and used by the background scheduler after they are applied.</span>
                            <button class="action-button" data-action="psu-save-schedules" data-device-id="${device.id}">Apply Channel Schedules</button>
                        </div>
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
    renderLaserLockSummary(
        overviewPayload.state.laser_lock_system || {},
        overviewPayload.runtime.laser_locks || {}
    );
    renderEdfaDevices(overviewPayload.state.edfa_devices || []);
    renderPsuDevices(overviewPayload.state.psu_devices || []);
    populateLaserLockForm(overviewPayload.state.laser_lock_system || {});
    renderLaserLockChannels(overviewPayload.runtime.laser_locks || {});
    renderEventLog(overviewPayload.runtime.events || []);
    lastOverviewAt = Date.now();
}

function startPolling() {
    window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(() => {
        const laserTabActive = document.getElementById("tab-laser-lock").classList.contains("is-active");
        if (laserTabActive || Date.now() - lastOverviewAt >= 25000) {
            loadOverview();
        }
    }, 2000);
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

    if (form.id === "laser-lock-form") {
        const formData = new FormData(form);
        await fetchJson("/api/laser-lock/system", {
            method: "PUT",
            body: {
                name: formData.get("name"),
                ip: formData.get("ip"),
                port: Number(formData.get("port")),
                timeout_sec: Number(formData.get("timeout_sec")),
                notes: formData.get("notes"),
            },
        });
        showMessage("Laser lock controller address saved.");
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
        await fetchJson("/api/edfa/template/apply", {
            method: "POST",
            body: {
                device_ids: [],
                channels: [],
                schedule: {
                    enabled: document.getElementById("template-schedule-enabled").checked,
                    days: collectTemplateWeekdays(),
                    on_time: document.getElementById("template-on-time").value.trim(),
                    off_time: document.getElementById("template-off-time").value.trim(),
                },
            },
        });
        showMessage("EDFA schedule applied to all devices.");
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

        if (target.id === "disconnect-all-telnet-button") {
            if (!window.confirm(
                "Disconnect every EDFA and laser locking Telnet connection? "
                + "Active foreground laser lock sessions may stop."
            )) {
                return;
            }
            const result = await fetchJson("/api/telnet/disconnect-all", { method: "POST" });
            const disconnected = result.data?.laser_channels_disconnected?.length || 0;
            showMessage(`All Telnet connections are closed. Laser sessions closed: ${disconnected}.`);
            await loadOverview();
            return;
        }

        if (target.id === "laser-lock-probe") {
            await fetchJson("/api/laser-lock/probe", { method: "POST" });
            showMessage("Laser lock controller is reachable.");
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

        if (action === "laser-lock-start") {
            await fetchJson(`/api/laser-lock/channels/${channelKey}/start`, { method: "POST" });
            showMessage(`${channelKey} lock session started.`);
        } else if (action === "laser-lock-relock") {
            if (!window.confirm(`Interrupt and relock ${channelKey}?`)) {
                return;
            }
            await fetchJson(`/api/laser-lock/channels/${channelKey}/relock`, { method: "POST" });
            showMessage(`${channelKey} relock started.`);
        } else if (action === "edfa-save") {
            await fetchJson(`/api/edfa/devices/${deviceId}`, { method: "PUT", body: readEdfaCardPayload(card) });
            dirtyEdfaDevices.delete(deviceId);
            showMessage("EDFA configuration saved.");
        } else if (action === "edfa-save-schedule") {
            await fetchJson(`/api/edfa/devices/${deviceId}`, { method: "PUT", body: readEdfaCardPayload(card) });
            dirtyEdfaDevices.delete(deviceId);
            showMessage("EDFA schedule applied.");
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
            dirtyPsuDevices.delete(deviceId);
            showMessage("PSU configuration saved.");
        } else if (action === "psu-save-schedules") {
            await fetchJson(`/api/psu/devices/${deviceId}`, { method: "PUT", body: readPsuCardPayload(card) });
            dirtyPsuDevices.delete(deviceId);
            showMessage("PSU channel schedules applied.");
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
    document.getElementById("laser-lock-form").addEventListener("submit", (event) => handleFormSubmit(event).catch((error) => showMessage(error.message, "error")));
    document.getElementById("password-form").addEventListener("submit", (event) => handleFormSubmit(event).catch((error) => showMessage(error.message, "error")));
    document.getElementById("edfa-template-form").addEventListener("submit", (event) => handleFormSubmit(event).catch((error) => showMessage(error.message, "error")));
    document.body.addEventListener("click", (event) => {
        handleClick(event).catch((error) => showMessage(error.message, "error"));
    });
    document.body.addEventListener("input", (event) => {
        const card = event.target.closest(".device-card");
        if (card?.dataset.deviceType === "edfa") {
            dirtyEdfaDevices.add(card.dataset.deviceId);
        } else if (card?.dataset.deviceType === "psu") {
            dirtyPsuDevices.add(card.dataset.deviceId);
        }
    });
    document.body.addEventListener("change", (event) => {
        const card = event.target.closest(".device-card");
        if (card?.dataset.deviceType === "edfa") {
            dirtyEdfaDevices.add(card.dataset.deviceId);
        } else if (card?.dataset.deviceType === "psu") {
            dirtyPsuDevices.add(card.dataset.deviceId);
        }
    });
}

async function initialize() {
    renderWeekdayCheckboxes("template-weekdays", "template", [0, 1, 2, 3, 4]);
    bindTabNavigation();
    bindFormsAndButtons();
    connectWebSocket();
    startPolling();
    await loadOverview();
}

initialize().catch((error) => {
    showMessage(error.message, "error");
});
