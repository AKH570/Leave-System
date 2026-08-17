(function () {
    "use strict";

    const script = document.currentScript;
    const timeout = Number(JSON.parse(document.getElementById("session-timeout-seconds").textContent));
    const warning = Number(JSON.parse(document.getElementById("session-warning-seconds").textContent));
    const refreshUrl = script.dataset.refreshUrl;
    const logoutUrl = script.dataset.logoutUrl;
    const modalElement = document.getElementById("sessionTimeoutModal");
    const countdown = document.getElementById("sessionTimeoutCountdown");
    const stayButton = document.getElementById("sessionStayLoggedIn");
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    let expiresAt = Date.now() + timeout * 1000;
    let lastRefresh = Date.now();
    let refreshPending = false;

    function csrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    async function refreshSession(force) {
        // Throttle high-frequency activity while keeping server/client deadlines equal.
        if (refreshPending || (!force && Date.now() - lastRefresh < 30000)) return;
        refreshPending = true;
        try {
            const response = await fetch(refreshUrl, {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    "X-CSRFToken": csrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                }
            });
            if (!response.ok) {
                window.location.replace(logoutUrl);
                return;
            }
            lastRefresh = Date.now();
            expiresAt = lastRefresh + timeout * 1000;
            modal.hide();
        } finally {
            refreshPending = false;
        }
    }

    function onActivity() {
        refreshSession(false);
    }

    ["mousemove", "mousedown", "keydown", "scroll", "touchstart"].forEach(function (eventName) {
        window.addEventListener(eventName, onActivity, { passive: true });
    });

    stayButton.addEventListener("click", function () {
        refreshSession(true);
    });

    window.setInterval(function () {
        const remaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
        if (remaining <= warning) {
            const minutes = Math.floor(remaining / 60);
            const seconds = String(remaining % 60).padStart(2, "0");
            countdown.textContent = minutes + ":" + seconds;
            modal.show();
        }
        if (remaining === 0) {
            window.location.replace(logoutUrl + "?expired=1");
        }
    }, 1000);

    // A Back/forward-cache restore must revalidate authentication immediately.
    window.addEventListener("pageshow", function (event) {
        if (event.persisted) refreshSession(true);
    });
}());
