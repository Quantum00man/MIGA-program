function showMessage(message, level = "error") {
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
    if (settings.body && typeof settings.body !== "string") {
        settings.headers["Content-Type"] = "application/json";
        settings.body = JSON.stringify(settings.body);
    }
    const response = await fetch(url, settings);
    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Login failed.");
    }
    return payload;
}

async function verifyExistingSession() {
    try {
        const payload = await fetchJson("/auth/me");
        if (payload.authenticated) {
            window.location.href = "/";
        }
    } catch (error) {
        return;
    }
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    try {
        await fetchJson("/auth/login", {
            method: "POST",
            body: {
                password: formData.get("password"),
            },
        });
        window.location.href = "/";
    } catch (error) {
        showMessage(error.message, "error");
    }
});

verifyExistingSession();
