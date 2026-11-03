(function setupICuCropsRealtimeSync(global) {
  "use strict";

  // This endpoint only returns a tiny in-memory version map. The Pi talks to
  // localhost, so it can check four times per second and repaint an MQTT
  // reading without a visible wait. Desktop/mobile keep the lighter one-second
  // cadence because those requests may cross the internet.
  const POLL_INTERVAL_MS = 1000;
  // Ceiling for the failure backoff below: far enough apart to let a busy
  // backend finish what it is doing, close enough that recovery is quick.
  const POLL_BACKOFF_MAX_MS = 15000;
  const PI_POLL_INTERVAL_MS = 250;
  const ALL_SCOPES = [
    "users",
    "profile",
    "cultivations",
    "sensors",
    "irrigation",
    "notifications",
  ];
  const REFRESHERS = {
    users: "refreshUsers",
    profile: "refreshProfile",
    cultivations: "refreshCultivations",
    sensors: "refreshSensors",
    irrigation: "refreshIrrigation",
    notifications: "refreshNotifications",
  };
  const VIEW_SCOPES = {
    dashboard: new Set(["cultivations", "sensors", "irrigation"]),
    cultivation: new Set(["cultivations", "sensors"]),
    sensors: new Set(["sensors", "cultivations"]),
    irrigation: new Set(["irrigation", "sensors", "cultivations"]),
    history: new Set(["notifications"]),
    "manage-users": new Set(["users"]),
    "manage-account": new Set(["profile", "users"]),
  };

  const SELF_MUTATION_SUPPRESS_MS = 4000;

  let knownVersions = null;
  let pollTimer = 0;
  let pollBusy = false;
  let applyBusy = false;
  let warnedUnavailable = false;
  let pollFailureStreak = 0;
  let nextPollAllowedAt = 0;
  const pendingScopes = new Set();
  const recentLocalMutations = new Map();

  // Called by app.js right after a successful save/update/delete so the very
  // next poll tick doesn't treat the app's own write as a remote change and
  // re-render a second time on top of the save's own optimistic render.
  // suppressMs defaults to SELF_MUTATION_SUPPRESS_MS but can be shortened for
  // scopes that other users/devices are more likely to touch concurrently.
  const markLocalMutation = (scope, suppressMs = SELF_MUTATION_SUPPRESS_MS) => {
    const normalized = String(scope || "").trim().toLowerCase();
    if (normalized) {
      recentLocalMutations.set(normalized, { at: Date.now(), suppressMs });
    }
  };

  const start = () => {
    global.clearInterval(pollTimer);
    const intervalMs = global.ICuCropsPiMode === true ? PI_POLL_INTERVAL_MS : POLL_INTERVAL_MS;
    pollTimer = global.setInterval(poll, intervalMs);
    global.setTimeout(poll, 250);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    global.addEventListener("focus", () => void poll({ immediate: true }), { passive: true });
    document.addEventListener("focusout", flushAfterEditing);
  };

  const hasAuthenticatedSession = () => Boolean(global.ICuCropsAuth?.readSession?.()?.accessToken);

  const normalizeVersions = (value) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return {};
    }
    return Object.fromEntries(
      Object.entries(value)
        .map(([scope, revision]) => [String(scope || "").trim().toLowerCase(), String(revision || "").trim()])
        .filter(([scope, revision]) => scope && revision),
    );
  };

  const changedScopesBetween = (previous, next) => {
    const scopes = new Set([...Object.keys(previous), ...Object.keys(next)]);
    const changed = [...scopes].filter((scope) => previous[scope] !== next[scope]);
    return changed.includes("system") ? ALL_SCOPES : changed.filter((scope) => ALL_SCOPES.includes(scope));
  };

  async function poll({ immediate = false } = {}) {
    if (pollBusy || applyBusy || document.hidden || !hasAuthenticatedSession()) {
      return;
    }

    // Once a second is right for a healthy backend and wrong for a struggling
    // one. Building a report saturates the hosted function, and every failed
    // poll during it was retried a second later, which kept the backend busy
    // with version checks while the export it was waiting on tried to finish.
    // Back off after repeated failures and come straight back on the first
    // success, so a passing outage cannot be sustained by this poller.
    //
    // Coming back to the tab is the one case that must not wait out a backoff:
    // the page may have been away for minutes and is showing stale numbers, and
    // the person is looking at it right now. Those callers pass immediate.
    if (!immediate && pollFailureStreak > 0 && Date.now() < nextPollAllowedAt) {
      return;
    }

    const requestJson = global.ICuCropsAuth?.requestJson;
    if (typeof requestJson !== "function") {
      return;
    }

    pollBusy = true;
    try {
      const response = await requestJson("/api/realtime/versions", { timeoutMs: 5000 });
      const nextVersions = normalizeVersions(response?.versions);
      warnedUnavailable = false;
      pollFailureStreak = 0;
      nextPollAllowedAt = 0;

      if (knownVersions === null) {
        knownVersions = nextVersions;
        // Hydration and the first version request run in parallel. A Pi sync
        // can land between them: hydration may have read the old empty rows,
        // while this request sees the new fingerprint as its baseline. Refresh
        // the visible surface once so that race cannot strand a stale page.
        const activeView = typeof global.viewFromHash === "function"
          ? global.viewFromHash()
          : String(global.location.hash || "").replace(/^#\/?/, "") || "dashboard";
        const initialScopes = VIEW_SCOPES[activeView] || new Set(ALL_SCOPES);
        initialScopes.forEach((scope) => pendingScopes.add(scope));
        await flushPendingScopes();
        return;
      }

      const now = Date.now();
      const changedScopes = changedScopesBetween(knownVersions, nextVersions).filter((scope) => {
        const mutation = recentLocalMutations.get(scope);
        return !(mutation && now - mutation.at < mutation.suppressMs);
      });
      knownVersions = nextVersions;
      changedScopes.forEach((scope) => pendingScopes.add(scope));
      await flushPendingScopes();
    } catch (error) {
      pollFailureStreak += 1;
      nextPollAllowedAt = Date.now() + Math.min(
        POLL_BACKOFF_MAX_MS,
        POLL_INTERVAL_MS * (2 ** Math.min(pollFailureStreak, 4)),
      );
      if (!warnedUnavailable && error?.status !== 401) {
        warnedUnavailable = true;
        console.warn("Realtime updates are temporarily unavailable; normal fallback refresh remains active.", error);
      }
    } finally {
      pollBusy = false;
    }
  }

  function hasFocusedEditor() {
    const active = document.activeElement;
    return active instanceof Element && Boolean(active.closest(
      "input:not([type='button']):not([type='submit']):not([type='checkbox']):not([type='radio']), select, textarea, [contenteditable='true']",
    ));
  }

  function flushAfterEditing() {
    global.setTimeout(() => {
      if (!hasFocusedEditor()) {
        void flushPendingScopes();
      }
    }, 80);
  }

  async function flushPendingScopes() {
    if (applyBusy || !pendingScopes.size || hasFocusedEditor()) {
      return;
    }

    applyBusy = true;
    const scopes = [...pendingScopes];
    pendingScopes.clear();
    try {
      // Notification history can involve a larger database/cache response.
      // Never keep sensor or irrigation controls waiting for that secondary
      // work; render farm state first and hydrate alerts in a separate task.
      const immediateScopes = scopes.filter((scope) => scope !== "notifications");
      const refreshJobs = immediateScopes
        .map((scope) => ({ scope, refresh: global[REFRESHERS[scope]] }))
        .filter((job, index, list) => (
          typeof job.refresh === "function"
          && list.findIndex((candidate) => candidate.refresh === job.refresh) === index
        ))
        .map(({ scope, refresh }) => refresh({
          render: false,
          // A change-driven refresh only needs what changed. The catalog and the
          // thirty-day history behind the graphs cannot be patched into a card
          // anyway, and the dashboard re-seeds them on its own interval. This
          // was gated on the kiosk, which left the hosted dashboards -- the ones
          // actually paying to transfer it -- asking for the full payload every
          // time a reading landed.
          ...(scope === "sensors" ? { live: true } : {}),
        }));
      await Promise.allSettled(refreshJobs);
      renderChangedSurfaces(immediateScopes);
      global.dispatchEvent(new CustomEvent("icucrops:realtime-synced", { detail: { scopes: immediateScopes } }));

      if (scopes.includes("notifications")) {
        global.setTimeout(async () => {
          const refresh = global[REFRESHERS.notifications];
          if (typeof refresh === "function") {
            await Promise.resolve(refresh({ render: false })).catch(() => {});
          }
          renderChangedSurfaces(["notifications"]);
          global.dispatchEvent(new CustomEvent("icucrops:realtime-synced", {
            detail: { scopes: ["notifications"] },
          }));
        }, 0);
      }
    } finally {
      applyBusy = false;
      if (pendingScopes.size && !hasFocusedEditor()) {
        global.setTimeout(() => void flushPendingScopes(), 0);
      }
    }
  }

  function renderChangedSurfaces(scopes) {
    const changed = new Set(scopes);
    const activeView = typeof global.viewFromHash === "function"
      ? global.viewFromHash()
      : String(global.location.hash || "").replace(/^#\/?/, "") || "dashboard";
    const relevantScopes = VIEW_SCOPES[activeView] || new Set(ALL_SCOPES);
    const shouldRenderPage = [...changed].some((scope) => relevantScopes.has(scope));

    if (["users", "profile", "notifications"].some((scope) => changed.has(scope))) {
      global.renderHeader?.();
    }

    let dashboardPatched = false;
    if (shouldRenderPage && activeView === "dashboard" && typeof global.reconcileDashboardLiveState === "function") {
      dashboardPatched = Boolean(global.reconcileDashboardLiveState({
        sensorsChanged: changed.has("sensors"),
        cultivationsChanged: changed.has("cultivations"),
      }));
    }

    let sensorsPatched = false;
    if (shouldRenderPage && activeView === "sensors" && typeof global.reconcileSensorsLiveState === "function") {
      sensorsPatched = Boolean(global.reconcileSensorsLiveState());
    }

    let cultivationPatched = false;
    if (shouldRenderPage && activeView === "cultivation" && typeof global.reconcileCultivationLiveState === "function") {
      cultivationPatched = Boolean(global.reconcileCultivationLiveState({
        cultivationsChanged: changed.has("cultivations"),
      }));
    }

    if (shouldRenderPage && !dashboardPatched && !sensorsPatched && !cultivationPatched) {
      global.renderPage?.();
    }
    if (shouldRenderPage || ["users", "profile", "notifications"].some((scope) => changed.has(scope))) {
      global.renderOverlays?.();
    }
  }

  function handleVisibilityChange() {
    if (!document.hidden) {
      void poll({ immediate: true });
    }
  }

  global.icuCropsRealtimeSync = { markLocalMutation };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})(window);
