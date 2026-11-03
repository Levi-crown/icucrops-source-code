(function attachICuCropsAuth(global) {
  // Kept for reading sessions written by older builds, and for clearing them.
  // Nothing writes to it any more -- see roleSessionKey().
  const SESSION_KEY = "icucrops.auth.session";
  // One stored session per role, because a browser can legitimately hold two.
  //
  // Both roles used to share SESSION_KEY, so signing in as an admin
  // overwrote a user session that was still perfectly valid. The user shell's
  // own guard then read role "admin", decided the session was not its own, and
  // called clearSession() -- which is why signing in on the laptop as an admin
  // signed the phone's user account out, and why a second tab at a different
  // account level did the same. The server never rejected anything: the
  // browser threw the session away by itself.
  const ADMIN_SESSION_KEY = "icucrops.auth.session.admin";
  const USER_SESSION_KEY = "icucrops.auth.session.user";
  // Per TAB, not per browser -- this is sessionStorage, and the distinction is
  // the whole point.
  //
  // It used to live in localStorage, which made every tab of a browser look
  // like one device to the server. Two consequences, both wrong:
  //
  //   A second tab signing into the same account did not sign the first one
  //   out, because same_client matched. "One device at a time" quietly meant
  //   "one browser at a time", and two tabs could drive the farm controls at
  //   once -- the thing the rule exists to prevent.
  //
  //   And when a genuinely different device signed in, every tab of the first
  //   browser was superseded together, so it looked as though both devices had
  //   been signed out rather than just the older one.
  //
  // sessionStorage is per tab AND survives a reload, which is exactly the
  // distinction needed: F5 keeps this id and stays the same session, while a
  // new tab gets a fresh one and supersedes the old. A duplicated tab inherits
  // the value, so it reads as the same session until it logs in again -- which
  // is the nearest thing to a reload it could be.
  const CLIENT_ID_KEY = "icucrops.auth.clientId.v1";
  const API_BASE_KEY = "icucrops.auth.apiBase";
  const ADMIN_AUTH_KEY = "arugula.isAuthenticated";
  const ADMIN_HASH_KEY = "arugula.postLoginHash";
  const USER_AUTH_KEY = "arugula.user.isAuthenticated";
  const USER_HASH_KEY = "arugula.user.postLoginHash";
  // These localStorage caches mirror per-account controls for fast local
  // reads, but are not namespaced per user id. Clear them on logout so a
  // fresh login on a shared device never briefly shows the previous
  // account's sensor-control/irrigation-row selection. Theme and dashboard
  // graph range are device display preferences, so auth cleanup must never
  // erase them. Rewriting a valid session must preserve every cache here too:
  // profile hydration also calls writeSession().
  const ACCOUNT_SCOPED_LOCAL_CACHE_KEYS = [
    "icucrops.sensorControls.v1",
    "icucrops.irrigation.selectedRow.v1",
  ];
  const PROTECTED_HISTORY_BOUNDARY = "icucropsProtectedHistoryBoundary";
  const PROTECTED_HISTORY_ACTIVE = "icucropsProtectedHistoryActive";
  const DEFAULT_FALLBACK_PORT = "8080";
  const DEFAULT_REQUEST_TIMEOUT_MS = 10000;
  const PASSWORD_POLICY_MESSAGE = "Password must be 8–64 characters and include uppercase, lowercase, number, and special character.";
  // Sign-in and password-reset requests reach Firebase, and the backend caps
  // each of those calls at ICUCROPS_FIREBASE_REQUEST_TIMEOUT_SECONDS (5s by
  // default) before falling back to the local snapshot -- so it can spend
  // several seconds and still return a perfectly good answer. Measured on the
  // Pi against asia-southeast1, one lookup ran 0.6s-5.5s depending on the link.
  // The 10s default sat inside that range and aborted work that was about to
  // succeed, reporting "The server took too long to respond" for what was
  // really a wrong password. Worse, the attempt had already been counted, so
  // retrying after a timeout silently burned the 5-attempt lockout budget.
  const AUTH_REQUEST_TIMEOUT_MS = 30000;
  let protectedHistoryGuardInstalled = false;
  let activeSessionGuardConfig = null;
  let accountInUseNoticeShown = false;

  function isValidNewPassword(value) {
    const password = String(value || "");
    const characterCount = Array.from(password).length;
    return characterCount >= 8
      && characterCount <= 64
      && /\p{Lu}/u.test(password)
      && /\p{Ll}/u.test(password)
      && /\p{N}/u.test(password)
      && /[^\p{L}\p{N}\s]/u.test(password);
  }

  function normalizeRole(value) {
    const role = String(value || "").trim().toLowerCase();
    return role === "admin" ? "admin" : "user";
  }

  function roleLabel(role) {
    return normalizeRole(role) === "admin" ? "Administrator" : "User";
  }

  function roleAuthKey(role) {
    return normalizeRole(role) === "admin" ? ADMIN_AUTH_KEY : USER_AUTH_KEY;
  }

  function roleHashKey(role) {
    return normalizeRole(role) === "admin" ? ADMIN_HASH_KEY : USER_HASH_KEY;
  }

  function roleSessionKey(role) {
    return normalizeRole(role) === "admin" ? ADMIN_SESSION_KEY : USER_SESSION_KEY;
  }

  function safeGetItem(key) {
    try {
      return global.sessionStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function safeSetItem(key, value) {
    try {
      global.sessionStorage.setItem(key, value);
    } catch (error) {
      return false;
    }

    return true;
  }

  function safeRemoveItem(key) {
    try {
      global.sessionStorage.removeItem(key);
    } catch (error) {
      return false;
    }

    return true;
  }

  function authClientId() {
    try {
      const existing = String(global.sessionStorage.getItem(CLIENT_ID_KEY) || "").trim();
      if (/^[A-Za-z0-9_-]{16,128}$/.test(existing)) {
        return existing;
      }

      let generated = "";
      if (typeof global.crypto?.randomUUID === "function") {
        generated = global.crypto.randomUUID().replace(/-/g, "_");
      } else if (typeof global.crypto?.getRandomValues === "function") {
        const bytes = new Uint8Array(24);
        global.crypto.getRandomValues(bytes);
        generated = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
      }
      if (!generated) {
        generated = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}_${Math.random().toString(36).slice(2)}`;
      }
      global.sessionStorage.setItem(CLIENT_ID_KEY, generated);
      return generated;
    } catch (error) {
      return "";
    }
  }

  // Which stored session to read.
  //
  // `preferredRole` is the role the caller is acting as -- a shell asking for
  // its own session. Without it, a browser holding both an admin and a user
  // session has no way to say which one it means, and the guard in
  // protectSessionHistory() would read the wrong one and sign that shell out.
  //
  // With no preference (the login screen, and anything that just wants "is
  // anyone signed in"), the most recently authenticated session wins, which is
  // what a single-session browser has always seen.
  function storedSessionRaw(preferredRole) {
    if (preferredRole) {
      const scoped = safeGetItem(roleSessionKey(preferredRole));
      if (scoped) {
        return scoped;
      }
      // A session written by a build before the keys were split. Only usable
      // if it is actually this role's, or the caller gets someone else's.
      const legacy = safeGetItem(SESSION_KEY);
      if (legacy) {
        try {
          if (normalizeRole(JSON.parse(legacy)?.role) === normalizeRole(preferredRole)) {
            return legacy;
          }
        } catch (error) {
          return null;
        }
      }
      return null;
    }

    const candidates = [
      safeGetItem(ADMIN_SESSION_KEY),
      safeGetItem(USER_SESSION_KEY),
      safeGetItem(SESSION_KEY),
    ].filter(Boolean);
    let newest = null;
    let newestTime = -Infinity;
    for (const candidate of candidates) {
      try {
        const time = Date.parse(JSON.parse(candidate)?.authenticatedAt || "") || 0;
        if (time >= newestTime) {
          newestTime = time;
          newest = candidate;
        }
      } catch (error) {
        // A malformed entry is simply not a candidate.
      }
    }
    return newest;
  }

  function readSession(preferredRole) {
    const raw = storedSessionRaw(preferredRole);
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        const role = normalizeRole(parsed?.role);
        const accessToken = String(parsed?.accessToken || "").trim();
        const expiresAt = String(parsed?.expiresAt || "").trim();
        const expiryTime = Date.parse(expiresAt);
        if (!accessToken || !Number.isFinite(expiryTime) || expiryTime <= Date.now()) {
          // Only this role's entry. clearSession() here would also throw away
          // the other role's session, which has its own token and expiry and
          // may be perfectly valid -- exactly the cross-account sign-out this
          // split exists to stop.
          clearRoleSession(role);
          return null;
        }
        return {
          id: String(parsed?.id || ""),
          displayName: String(parsed?.displayName || "").trim(),
          email: String(parsed?.email || "").trim().toLowerCase(),
          role,
          roleLabel: roleLabel(role),
          profilePhotoUrl: String(parsed?.profilePhotoUrl || "").trim(),
          authenticatedAt: String(parsed?.authenticatedAt || ""),
          accessToken,
          expiresAt,
        };
      } catch (error) {
        // Unparseable. Drop the entry that produced it, not every session.
        if (preferredRole) {
          clearRoleSession(preferredRole);
        } else {
          clearSession();
        }
      }
    }

    // Nothing stored for the role asked about. That is not a reason to end the
    // OTHER role's session, which is why this is scoped when a role was named.
    if (preferredRole) {
      clearRoleSession(preferredRole);
    } else {
      clearSession();
    }
    return null;
  }

  function writeSession(session) {
    let existing = {};
    // This role's own previous entry, so profile hydration can carry the
    // existing token forward without ever reading the other role's.
    const existingRaw = safeGetItem(roleSessionKey(session?.role))
      || safeGetItem(SESSION_KEY);
    if (existingRaw) {
      try {
        existing = JSON.parse(existingRaw) || {};
      } catch (error) {
        existing = {};
      }
    }
    const role = normalizeRole(session?.role);
    const payload = {
      // Carried forward from the stored entry the same way the token and its
      // expiry are, and for the same reason: a caller that is updating one
      // field must not be able to erase the others.
      //
      // syncAuthenticatedProfileSession() passes `user?.id || session.id`, so a
      // /api/profile answer that omits id -- which is what a failing or
      // read-only database returns -- used to write "" here over a session
      // whose token was still perfectly valid. The id is what every profile
      // route is keyed on (/api/profile/<user_id>, and both password OTP
      // routes), so losing it broke Save Profile, Change Password and the OTP
      // together while the dashboard itself stayed signed in. That is exactly
      // the "Logged-in account could not be detected" warning: the session is
      // there, only its id is gone.
      id: String(session?.id || existing?.id || ""),
      displayName: String(session?.displayName || "").trim(),
      email: String(session?.email || "").trim().toLowerCase(),
      role,
      roleLabel: roleLabel(role),
      profilePhotoUrl: String(session?.profilePhotoUrl || "").trim(),
      authenticatedAt: String(session?.authenticatedAt || new Date().toISOString()),
      accessToken: String(session?.accessToken || existing?.accessToken || "").trim(),
      expiresAt: String(session?.expiresAt || existing?.expiresAt || "").trim(),
    };

    if (!payload.accessToken || !payload.expiresAt) {
      // Only this role's entry: a half-written session for one role says
      // nothing about the other role's, which may be signed in and valid.
      clearRoleSession(role);
      return null;
    }

    // Overwrite in place. This used to clear every credential key first, which
    // left the session absent for the moment between the two calls -- and any
    // request that read it in that gap went out with no Authorization header
    // and came back 401, which the caller then treated as an expired session.
    // Profile hydration calls this on a valid session, so the window opened
    // during ordinary use: downloading a report was simply the reliable way to
    // have another request in flight at the same time.
    safeSetItem(roleSessionKey(role), JSON.stringify(payload));
    safeSetItem(roleAuthKey(role), "true");
    // The legacy shared entry is retired as soon as anything writes, so the
    // migration path in storedSessionRaw() cannot later hand back a stale
    // session belonging to whichever role happened to write it last.
    safeRemoveItem(SESSION_KEY);
    // The other role's keys are deliberately left alone. Clearing them here is
    // what signed a user out when an admin signed in on the same browser: two
    // roles can be held at once, each with its own token, and each is only
    // ended by its own logout or its own expiry.
    return payload;
  }

  // End one role's session and leave the other's alone. Used everywhere the
  // reason for clearing applies to a single role -- its token expired, its
  // shell logged out -- which is almost everywhere.
  function clearRoleSession(role) {
    const normalized = normalizeRole(role);
    safeRemoveItem(roleSessionKey(normalized));
    safeRemoveItem(roleAuthKey(normalized));
    safeRemoveItem(roleHashKey(normalized));
    // The legacy shared entry belongs to whichever role wrote it; drop it only
    // when it is this role's, or signing one role out would strand the other.
    const legacy = safeGetItem(SESSION_KEY);
    if (legacy) {
      try {
        if (normalizeRole(JSON.parse(legacy)?.role) === normalized) {
          safeRemoveItem(SESSION_KEY);
        }
      } catch (error) {
        safeRemoveItem(SESSION_KEY);
      }
    }
    // Account-scoped local caches are not namespaced per user, so they must go
    // with any sign-out or the next account briefly sees the previous one's
    // control selection.
    for (const key of ACCOUNT_SCOPED_LOCAL_CACHE_KEYS) {
      try {
        global.localStorage.removeItem(key);
      } catch (error) {
        // Ignore storage access failures (e.g. private browsing).
      }
    }
  }

  // The role this page is acting as, when one is known. Falls back to the
  // whole-browser clear so a page with no guard configured still signs out.
  function clearActiveRoleSession() {
    if (activeSessionGuardConfig?.role) {
      clearRoleSession(activeSessionGuardConfig.role);
      return;
    }
    clearSession();
  }

  function clearSessionCredentials() {
    safeRemoveItem(SESSION_KEY);
    safeRemoveItem(ADMIN_SESSION_KEY);
    safeRemoveItem(USER_SESSION_KEY);
    safeRemoveItem(ADMIN_AUTH_KEY);
    safeRemoveItem(USER_AUTH_KEY);
    safeRemoveItem(ADMIN_HASH_KEY);
    safeRemoveItem(USER_HASH_KEY);
  }

  function clearSession() {
    // Leave a breadcrumb for the one bug that keeps coming back: the session
    // disappearing with no visible cause. This records who ended it and where
    // from, in localStorage so it survives the redirect to the login page.
    // Read it with: JSON.parse(localStorage.getItem("icucrops.auth.lastClear"))
    try {
      global.localStorage.setItem("icucrops.auth.lastClear", JSON.stringify({
        at: new Date().toISOString(),
        url: String(global.location?.href || ""),
        by: new Error("session cleared").stack || "",
      }));
    } catch (error) {
      // Diagnostics must never be the thing that breaks sign-out.
    }

    clearSessionCredentials();
    for (const key of ACCOUNT_SCOPED_LOCAL_CACHE_KEYS) {
      try {
        global.localStorage.removeItem(key);
      } catch (error) {
        // Ignore storage access failures (e.g. private browsing).
      }
    }
  }

  function isProtectedShellUrl(value) {
    let targetUrl;
    try {
      targetUrl = new URL(value, global.location?.href || undefined);
    } catch (error) {
      return false;
    }

    if (targetUrl.origin !== global.location?.origin) {
      return false;
    }

    const pathname = targetUrl.pathname.replace(/\/+$/, "").toLowerCase();
    return (
      /\/(?:administrator|user)(?:\/index\.html)?$/.test(pathname)
      || /\/raspberry_pi\/index\.html$/.test(pathname)
    );
  }

  function redirectToLoginPath(loginPath) {
    try {
      const loginUrl = new URL(String(loginPath || "/auth/index.html").trim(), global.location.href);
      const currentUrl = new URL(global.location.href);
      loginUrl.search = currentUrl.search;
      loginUrl.searchParams.set("logout", "1");
      loginUrl.hash = "";
      global.location.replace(loginUrl.toString());
    } catch (error) {
      global.location.href = String(loginPath || "/auth/index.html").trim();
    }
  }

  // What the browser will say about the device it runs on, for the "Opened
  // on" line another device sees when this login signs it out. Chromium's
  // client hints give an Android phone's exact model (SM-A155F) and every
  // platform's version; Safari and Firefox give none, and no browser gives a
  // computer's name. Never waits long: a login must not stall on a courtesy.
  async function readLoginDeviceHints() {
    const data = global.navigator?.userAgentData;
    if (!data || typeof data.getHighEntropyValues !== "function") {
      return null;
    }
    try {
      const hints = await Promise.race([
        data.getHighEntropyValues(["model", "platformVersion"]),
        new Promise((resolve) => global.setTimeout(() => resolve(null), 400)),
      ]);
      if (!hints || typeof hints !== "object") {
        return null;
      }
      return {
        model: String(hints.model || "").slice(0, 60),
        platform: String(hints.platform || data.platform || "").slice(0, 30),
        platformVersion: String(hints.platformVersion || "").slice(0, 30),
        mobile: hints.mobile === true || data.mobile === true,
      };
    } catch (error) {
      return null;
    }
  }

  function showAccountInUseNotice(payload) {
    if (accountInUseNoticeShown || !global.document?.body) {
      return;
    }
    accountInUseNoticeShown = true;
    // The server superseded one account's session. The other role signed in on
    // this browser is a different account and was not superseded.
    if (activeSessionGuardConfig?.role) {
      clearRoleSession(activeSessionGuardConfig.role);
    } else {
      clearSession();
    }

    const loginPath = String(activeSessionGuardConfig?.loginPath || "/auth/index.html").trim();
    const doc = global.document;

    const overlay = doc.createElement("div");
    overlay.className = "icucrops-session-taken";
    overlay.setAttribute("role", "alertdialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "icucrops-session-taken-title");
    overlay.setAttribute("aria-describedby", "icucrops-session-taken-copy");

    // The palette comes from the app's own tokens rather than fixed hex, so the
    // card follows the farm's theme instead of flashing white over a dark
    // dashboard. The fallbacks after each var() are what the login page uses
    // before its stylesheet has loaded, and on the Pi if a sheet is missing.
    const style = doc.createElement("style");
    style.textContent = `
      .icucrops-session-taken {
        position: fixed;
        inset: 0;
        z-index: 2147483647;
        display: grid;
        place-items: center;
        padding: 1.25rem;
        background: color-mix(in srgb, var(--green-900, #0b2f21) 62%, transparent);
        font-family: inherit;
      }
      @supports not (background: color-mix(in srgb, red 50%, transparent)) {
        .icucrops-session-taken { background: rgba(11, 47, 33, 0.62); }
      }
      .icucrops-session-taken__card {
        width: 100%;
        max-width: 24rem;
        box-sizing: border-box;
        padding: 1.75rem 1.5rem 1.5rem;
        border-radius: var(--radius-lg, 22px);
        border: 1px solid var(--line, rgba(27, 97, 64, 0.16));
        background: var(--surface-strong, #ffffff);
        color: var(--text, #102118);
        box-shadow: var(--shadow-strong, 0 12px 26px rgba(14, 61, 43, 0.1));
        /* Centred, which is what every other confirm dialog in the app does.
           This one was left-aligned, and because the badge is a block-level
           grid it sat hard against the left edge with the heading and copy
           ragged beside it -- the odd one out on both the phone and the
           desktop. */
        text-align: center;
      }
      .icucrops-session-taken__badge {
        display: grid;
        place-items: center;
        width: 2.75rem;
        height: 2.75rem;
        /* auto on the sides, so the badge follows the centred text above it.
           text-align has no effect on a block-level element's own box. */
        margin: 0 auto 1rem;
        border-radius: var(--radius-sm, 12px);
        color: var(--green-600, #1c8050);
        background: color-mix(in srgb, var(--green-600, #1c8050) 12%, transparent);
      }
      @supports not (background: color-mix(in srgb, red 50%, transparent)) {
        .icucrops-session-taken__badge { background: rgba(28, 128, 80, 0.12); }
      }
      .icucrops-session-taken__badge svg {
        width: 1.375rem;
        height: 1.375rem;
        fill: none;
        stroke: currentColor;
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
      }
      .icucrops-session-taken__title {
        margin: 0 0 0.5rem;
        font-size: 1.125rem;
        font-weight: 700;
        line-height: 1.3;
        letter-spacing: -0.01em;
      }
      .icucrops-session-taken__copy {
        margin: 0 auto 1.25rem;
        /* Centred prose wants a measure. Without one the last line of a
           three-line paragraph sits alone under the full width and reads as
           unbalanced rather than deliberate. */
        max-width: 19rem;
        font-size: 0.9rem;
        line-height: 1.55;
        color: var(--text-soft, #52665a);
      }
      .icucrops-session-taken__note {
        display: block;
        margin-top: 0.6rem;
        font-size: 0.82rem;
        color: var(--text-soft, #52665a);
      }
      .icucrops-session-taken__device {
        display: grid;
        gap: 0.2rem;
        margin: 0 0 1.25rem;
        padding: 0.75rem 0.9rem;
        border-radius: var(--radius-sm, 12px);
        border: 1px solid var(--line, rgba(27, 97, 64, 0.16));
        background: color-mix(in srgb, var(--green-600, #1c8050) 8%, transparent);
      }
      @supports not (background: color-mix(in srgb, red 50%, transparent)) {
        .icucrops-session-taken__device { background: rgba(28, 128, 80, 0.08); }
      }
      .icucrops-session-taken__device-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-soft, #52665a);
      }
      .icucrops-session-taken__device-name {
        font-size: 0.98rem;
        font-weight: 700;
        line-height: 1.35;
        color: var(--text, #102118);
        overflow-wrap: anywhere;
      }
      .icucrops-session-taken__device-time {
        font-size: 0.82rem;
        color: var(--text-soft, #52665a);
      }
      .icucrops-session-taken__action {
        width: 100%;
        appearance: none;
        border: 0;
        border-radius: var(--radius-sm, 12px);
        padding: 0.8rem 1.5rem;
        font: inherit;
        font-size: 0.95rem;
        font-weight: 600;
        /* White on the light theme's --green-600 measures 4.94:1. The dark
           theme lifts that same token to a much brighter green, where white
           falls to 2.15:1 and fails WCAG AA, so the dark side takes the near
           black ground instead and measures 8.83:1. */
        color: #ffffff;
        background: var(--green-600, #1c8050);
        cursor: pointer;
        -webkit-tap-highlight-color: transparent;
        transition: transform 150ms cubic-bezier(0.16, 1, 0.3, 1), background-color 150ms ease;
      }
      .icucrops-session-taken__action:hover { background: var(--green-700, #15583c); }
      html[data-theme="dark"] .icucrops-session-taken__action { color: var(--bg, #07130d); }
      html[data-theme="dark"] .icucrops-session-taken__action:hover {
        background: var(--green-500, #42bd63);
      }
      .icucrops-session-taken__action:active { transform: translateY(1px); }
      .icucrops-session-taken__action:focus-visible {
        outline: 2px solid var(--green-600, #1c8050);
        outline-offset: 2px;
      }
      /* The 800x480 kiosk panel: the card must not run past the screen. */
      @media (max-height: 520px) {
        .icucrops-session-taken__card { padding: 1.25rem 1.15rem 1.1rem; }
        .icucrops-session-taken__badge { width: 2.25rem; height: 2.25rem; margin: 0 auto 0.7rem; }
        .icucrops-session-taken__copy { margin-bottom: 0.9rem; }
        .icucrops-session-taken__device { margin-bottom: 0.9rem; padding: 0.55rem 0.8rem; }
      }
      @media (prefers-reduced-motion: reduce) {
        .icucrops-session-taken__action { transition: none; }
      }
    `;

    const card = doc.createElement("div");
    card.className = "icucrops-session-taken__card";

    const badge = doc.createElement("div");
    badge.className = "icucrops-session-taken__badge";
    badge.setAttribute("aria-hidden", "true");
    // The app's own lock glyph, not an emoji: it inherits the theme's colour
    // and renders identically on the kiosk, which has no emoji font.
    badge.innerHTML = '<svg viewBox="0 0 24 24">'
      + '<rect x="4" y="11" width="16" height="10" rx="2"></rect>'
      + '<path d="M8 11V8a4 4 0 0 1 8 0v3"></path>'
      + "</svg>";

    const title = doc.createElement("h2");
    title.className = "icucrops-session-taken__title";
    title.id = "icucrops-session-taken-title";
    // Plain words, and the reason before the rule.
    //
    // The old copy said "This account is signed in elsewhere", then explained
    // itself in one 34-word sentence that used "signed in" four times and
    // ended on "take back control", which reads as a fight with whoever is
    // using the farm right now -- usually a colleague, and often the same
    // person on their phone. What someone needs here is what happened, why,
    // and what to do, in that order.
    title.textContent = "You have been signed out";

    const copy = doc.createElement("p");
    copy.className = "icucrops-session-taken__copy";
    copy.id = "icucrops-session-taken-copy";
    copy.textContent = "This account was opened on another device. "
      + "ICuCrops allows one device at a time, so two people cannot work the "
      + "farm controls at once.";

    const note = doc.createElement("span");
    note.className = "icucrops-session-taken__note";
    note.textContent = "Sign in again to continue on this device.";
    copy.appendChild(note);

    const action = doc.createElement("button");
    action.className = "icucrops-session-taken__action";
    action.type = "button";
    action.textContent = "Sign in again";

    // Which device took over, when the server could name it: a colleague on
    // the farm kiosk and an unknown phone call for very different reactions.
    const takenBy = payload?.device && typeof payload.device === "object" ? payload.device : null;
    const takenByLabel = String(takenBy?.label || "").trim();
    let device = null;
    if (takenByLabel) {
      device = doc.createElement("div");
      device.className = "icucrops-session-taken__device";
      const deviceLabel = doc.createElement("span");
      deviceLabel.className = "icucrops-session-taken__device-label";
      deviceLabel.textContent = "Opened on";
      const deviceName = doc.createElement("span");
      deviceName.className = "icucrops-session-taken__device-name";
      deviceName.textContent = takenByLabel;
      device.appendChild(deviceLabel);
      device.appendChild(deviceName);
      const signedInAt = new Date(String(takenBy?.signedInAt || ""));
      if (!Number.isNaN(signedInAt.getTime())) {
        const deviceTime = doc.createElement("span");
        deviceTime.className = "icucrops-session-taken__device-time";
        deviceTime.textContent = signedInAt.toLocaleString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
          hour: "numeric",
          minute: "2-digit",
        });
        device.appendChild(deviceTime);
      }
    }

    card.appendChild(badge);
    card.appendChild(title);
    card.appendChild(copy);
    if (device) {
      card.appendChild(device);
    }
    card.appendChild(action);
    overlay.appendChild(style);
    overlay.appendChild(card);
    doc.body.appendChild(overlay);

    action.addEventListener("click", () => redirectToLoginPath(loginPath));
    // The card is the only thing left on the page, so focus must not be able to
    // wander back behind it into a dashboard the session no longer owns.
    overlay.addEventListener("keydown", (event) => {
      if (event.key === "Tab") {
        event.preventDefault();
        action.focus();
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        redirectToLoginPath(loginPath);
      }
    });
    action.focus();
  }

  function protectSessionHistory(config = {}) {
    const expectedRole = normalizeRole(config.role);
    const loginPath = String(config.loginPath || "/auth/index.html").trim();
    activeSessionGuardConfig = { role: expectedRole, loginPath };
    let redirecting = false;

    // Ask for THIS shell's role. Reading whatever session happened to be
    // stored is what made an admin sign-in look, to the user shell, like the
    // user's session had gone -- and the shell then cleared it and redirected.
    const hasExpectedSession = () => readSession(expectedRole)?.role === expectedRole;
    const redirectToLogin = () => {
      if (redirecting) {
        return;
      }

      redirecting = true;
      // Only this shell's role: whatever sent this shell to the login page
      // says nothing about the other role's session in the same browser.
      clearRoleSession(expectedRole);
      redirectToLoginPath(loginPath);
    };

    if (!hasExpectedSession()) {
      redirectToLogin();
      return false;
    }

    if (protectedHistoryGuardInstalled) {
      return true;
    }
    protectedHistoryGuardInstalled = true;

    try {
      const currentState = global.history.state || {};
      if (currentState[PROTECTED_HISTORY_BOUNDARY]) {
        redirectToLogin();
        return false;
      }

      if (!currentState[PROTECTED_HISTORY_ACTIVE]) {
        global.history.replaceState(
          { ...currentState, [PROTECTED_HISTORY_BOUNDARY]: true },
          "",
          global.location.href,
        );
        global.history.pushState(
          { [PROTECTED_HISTORY_ACTIVE]: true },
          "",
          global.location.href,
        );
      }
    } catch (error) {
      // Session validation and the Navigation API guard still protect browsers
      // that do not permit history state changes in their current context.
    }

    global.addEventListener("popstate", (event) => {
      if (event.state?.[PROTECTED_HISTORY_BOUNDARY] || !hasExpectedSession()) {
        redirectToLogin();
      }
    });

    global.addEventListener("pageshow", (event) => {
      // Restoring the page is not a reason to end the session on its own. The
      // page comes back from the bfcache after the browser's own download
      // hand-off, and hash routing pushes entries that carry no state of ours,
      // so requiring the ACTIVE marker here signed people out for saving a
      // report. Only the boundary entry -- the one behind the shell, reached by
      // going back out of it -- and an actually missing session should.
      if (!hasExpectedSession() || global.history.state?.[PROTECTED_HISTORY_BOUNDARY]) {
        redirectToLogin();
      }
    });

    global.navigation?.addEventListener?.("navigate", (event) => {
      // A download is not a navigation away from the shell. Saving a report
      // points an anchor at a blob: URL, and the Navigation API reports that
      // as a navigate event whose destination is blob:<origin>/<uuid> -- same
      // origin, but a path that is a UUID, so the shell test below rejected it
      // and signed the user out for downloading their own report. The browser
      // stays on the page in these cases; only a real move off the shell should
      // end the session.
      if (event.downloadRequest !== null && event.downloadRequest !== undefined) {
        return;
      }

      const destinationUrl = event.destination?.url;
      if (!destinationUrl || /^blob:/i.test(destinationUrl)) {
        return;
      }

      if (!isProtectedShellUrl(destinationUrl)) {
        // Leaving this shell ends this shell's role, not the whole browser.
        clearRoleSession(expectedRole);
      }
    });

    return true;
  }

  function rememberPostLoginHash(role, hash) {
    if (!hash) {
      return;
    }

    safeSetItem(roleHashKey(role), hash);
  }

  function takePostLoginHash(role) {
    const key = roleHashKey(role);
    const hash = safeGetItem(key) || "#/";
    safeRemoveItem(key);
    return hash;
  }

  function maskEmail(email) {
    const normalized = String(email || "").trim().toLowerCase();
    const parts = normalized.split("@");
    if (parts.length !== 2) {
      return normalized;
    }

    const [localPart, domain] = parts;
    if (localPart.length <= 2) {
      return `${localPart.slice(0, 1)}*@${domain}`;
    }

    return `${localPart.slice(0, 2)}${"*".repeat(Math.max(2, localPart.length - 2))}@${domain}`;
  }

  function candidateApiBases() {
    const candidates = [];
    const runtimeBase = String(global.ICuCropsRuntimeConfig?.apiBase || "").trim().replace(/\/+$/, "");
    const rememberedBase = String(safeGetItem(API_BASE_KEY) || "").trim().replace(/\/+$/, "");
    const currentOrigin = global.location?.origin
      ? global.location.origin.replace(/\/+$/, "")
      : "";
    const protocol = global.location?.protocol || "http:";
    const hostname = global.location?.hostname || "127.0.0.1";
    const fallbackPort = String(global.ICuCropsRuntimeConfig?.fallbackApiPort || DEFAULT_FALLBACK_PORT).trim();
    const canUseFallbackPort = isLocalApiHostname(hostname);
    const fallbackBase = fallbackPort && canUseFallbackPort && protocol === "http:"
      ? `${protocol}//${hostname}:${fallbackPort}`
      : "";

    if (runtimeBase) {
      candidates.push(runtimeBase);
    }
    // The origin the page was served from is always tried before a base
    // remembered from some earlier session. A remembered base is only ever a
    // hint, and a stale one is actively harmful: a base saved while on the farm
    // LAN (or a Pi address saved during setup) black-holes from anywhere else,
    // and because sign-in uses the 30s auth timeout, every attempt burned a
    // full 30s before the real origin was even tried. That is what made login
    // fail both offline and online -- the page and its API were reachable the
    // whole time, but the request was being sent somewhere else first.
    if (currentOrigin) {
      candidates.push(currentOrigin);
    }
    if (rememberedBase && rememberedBase !== currentOrigin) {
      candidates.push(rememberedBase);
    }
    if (fallbackBase) {
      candidates.push(fallbackBase);
    }

    return [...new Set(candidates.filter(Boolean))];
  }

  function isLocalApiHostname(hostname) {
    const normalized = String(hostname || "").trim().toLowerCase();
    if (!normalized) {
      return false;
    }

    if (
      normalized === "localhost"
      || normalized === "0.0.0.0"
      || normalized === "::1"
      || normalized === "[::1]"
      || normalized.endsWith(".local")
      || /^127(?:\.\d{1,3}){3}$/.test(normalized)
      || /^10(?:\.\d{1,3}){3}$/.test(normalized)
      || /^192\.168(?:\.\d{1,3}){2}$/.test(normalized)
    ) {
      return true;
    }

    const private172Match = normalized.match(/^172\.(\d{1,3})(?:\.\d{1,3}){2}$/);
    const private172Block = Number.parseInt(private172Match?.[1] || "", 10);
    return Number.isFinite(private172Block) && private172Block >= 16 && private172Block <= 31;
  }

  function buildRequestError(message, extras = {}) {
    const error = new Error(message);
    Object.assign(error, extras);
    return error;
  }

  function shouldTryNextCandidate(error) {
    const status = typeof error?.status === "number" ? error.status : 0;
    return (
      error?.code === "INVALID_API_RESPONSE"
      || !status
      || status === 404
      || status === 405
      || status === 501
    );
  }

  function rememberApiBase(base) {
    if (!base) {
      return;
    }

    safeSetItem(API_BASE_KEY, base);
  }

  // A remembered base was written on success but never withdrawn on failure, so
  // one bad save outlived the network that produced it and there was no way for
  // the app to recover on its own -- the user had to clear site data. Forgetting
  // it the moment it stops answering keeps the hint useful without letting it
  // become permanent.
  function forgetApiBase(base) {
    if (!base) {
      return;
    }

    const remembered = String(safeGetItem(API_BASE_KEY) || "").trim().replace(/\/+$/, "");
    if (remembered && remembered === base) {
      safeRemoveItem(API_BASE_KEY);
    }
  }

  // How far this browser's clock is from the server's, read off the Date
  // header of every response. Reading ages are measured against it: a desktop
  // whose clock ran 80 minutes slow saw every reading as arriving from the
  // future, called all of them stale, and emptied every card's bar -- while the
  // phone and the Pi, with correct clocks, showed the same data fine.
  let serverClockOffsetMs = 0;

  function noteServerClock(response) {
    const header = response?.headers?.get?.("date");
    const serverMs = header ? Date.parse(header) : Number.NaN;
    if (Number.isFinite(serverMs)) {
      serverClockOffsetMs = serverMs - Date.now();
    }
  }

  function serverNow() {
    return Date.now() + serverClockOffsetMs;
  }

  async function requestJson(path, options = {}) {
    const method = String(options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    const activeSession = readSession();
    if (activeSession?.accessToken) {
      headers.set("Authorization", `Bearer ${activeSession.accessToken}`);
    }
    const requestedTimeout = Number.parseInt(options.timeoutMs, 10);
    const timeoutMs = Number.isFinite(requestedTimeout) && requestedTimeout > 0
      ? requestedTimeout
      : DEFAULT_REQUEST_TIMEOUT_MS;

    const hasBody = Object.prototype.hasOwnProperty.call(options, "body");
    let body = options.body;
    if (hasBody && body !== undefined && body !== null && !(body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(body);
    }

    const candidates = candidateApiBases();
    let lastError = null;

    for (const base of candidates) {
      const requestUrl = new URL(path, `${base}/`).toString();
      const requestHeaders = new Headers(headers);

      const abortController = typeof AbortController === "function"
        ? new AbortController()
        : null;
      const externalSignal = options.signal;
      let timeoutId = 0;
      let requestTimedOut = false;
      const forwardExternalAbort = () => abortController?.abort(externalSignal?.reason);

      if (abortController) {
        if (externalSignal?.aborted) {
          forwardExternalAbort();
        } else {
          externalSignal?.addEventListener?.("abort", forwardExternalAbort, { once: true });
        }
        timeoutId = global.setTimeout(() => {
          requestTimedOut = true;
          abortController.abort();
        }, timeoutMs);
      }

      try {
        const response = await fetch(requestUrl, {
          method,
          headers: requestHeaders,
          body,
          cache: "no-store",
          signal: abortController?.signal || externalSignal,
        });
        noteServerClock(response);

        const contentType = String(response.headers.get("content-type") || "").toLowerCase();
        const rawText = await response.text();
        let payload = {};
        const hasJsonBody = contentType.includes("application/json");
        if (rawText && hasJsonBody) {
          try {
            payload = JSON.parse(rawText);
          } catch (error) {
            throw buildRequestError("API returned invalid JSON.", {
              status: response.status,
              base,
              code: "INVALID_API_RESPONSE",
            });
          }
        }

        if (response.ok && !hasJsonBody) {
          throw buildRequestError("API returned a non-JSON response.", {
            status: response.status,
            base,
            code: "INVALID_API_RESPONSE",
          });
        }

        if (response.ok) {
          rememberApiBase(base);
          return payload;
        }

        if (response.status === 401 && !String(path).startsWith("/api/auth/")) {
          if (payload?.code === "AUTH_SESSION_SUPERSEDED") {
            showAccountInUseNotice(payload);
          } else if (payload?.code === "AUTH_BACKEND_UNAVAILABLE") {
            // The backend could not read its records. That is not a rejected
            // session, and discarding the stored one would sign the farm out
            // over a passing outage. Older builds sent this as a bare 401, so
            // it is still recognised here by code rather than status alone.
          } else if (!hasJsonBody || !payload?.code) {
            // A 401 the API did not write. Under load the host answers with its
            // own empty or HTML 401 before the request ever reaches the auth
            // guard, and that is not a verdict on the session -- while a report
            // builds, the once-a-second realtime poll is nearly guaranteed to
            // catch one. Signing out on it ended the login mid-download even
            // though every download itself succeeded. The stored token is
            // signed and carries its own expiry, which readSession() enforces,
            // so keeping it costs nothing: a genuinely dead session still fails
            // the next attempt, with a code attached.
          } else {
            // A genuine rejection of the token this request carried, which
            // belongs to one role. The other role's session in this browser is
            // a different account and is not implicated by it.
            clearActiveRoleSession();
          }
        }

        const error = buildRequestError(
          payload.message || `Request failed with status ${response.status}.`,
          {
            status: response.status,
            payload,
            base,
          },
        );
        lastError = error;

        if (shouldTryNextCandidate(error)) {
          // A base that answers 404/405 for the API is serving something else
          // (a static host, a captive portal); stop preferring it next time.
          forgetApiBase(base);
          continue;
        }

        throw error;
      } catch (error) {
        const requestError = requestTimedOut
          ? buildRequestError("The server took too long to respond. Please try again.", {
            status: 0,
            base,
            code: "REQUEST_TIMEOUT",
          })
          : error;
        lastError = requestError;
        if (shouldTryNextCandidate(requestError)) {
          // This base did not answer, so it must not stay the remembered one.
          forgetApiBase(base);
          continue;
        }
        throw requestError;
      } finally {
        if (timeoutId) {
          global.clearTimeout(timeoutId);
        }
        externalSignal?.removeEventListener?.("abort", forwardExternalAbort);
      }
    }

    if (lastError instanceof Error) {
      throw lastError;
    }

    throw new Error("Backend request failed.");
  }

  function createLoginController(config = {}) {
    const init = () => {
      const forgotPasswordFlow = global.forgotPasswordFlow;
      const elements = {
        brand: document.querySelector(".login-panel__brand"),
        title: document.getElementById("auth-title"),
        copy: document.getElementById("auth-copy"),
        body: document.getElementById("auth-panel-body"),
      };
      if (!elements.body) {
        return;
      }

      const postLoginPaths = {
        admin: config.postLoginPaths?.admin || "./index.html",
        user: config.postLoginPaths?.user || "../user/index.html",
      };
      const showForgotPassword = config.showForgotPassword !== false;
      const loginViewContent = {
        title: config.loginTitle || "Login to ICuCrops",
        copy: config.loginCopy || "Access your farm dashboard and monitoring controls.",
      };
      let lockTimerId = 0;
      const state = {
        view: "login",
        loginEmail: "",
        loginPassword: "",
        recoveryEmail: "",
        otp: initialOtpCode(),
        newPassword: "",
        confirmPassword: "",
        notice: "",
        isSubmitting: false,
        challengeId: "",
        maskedEmail: "",
        expiresAt: "",
        lockedUntil: "",
        retryAfterSeconds: 0,
      };
      const helpers = {
        render,
        escapeHtml,
        getNoticeMarkup,
      };

      elements.body.addEventListener("click", handleClick);
      elements.body.addEventListener("submit", handleSubmit);
      elements.body.addEventListener("input", handleInput);
      elements.body.addEventListener("change", handleInput);
      elements.body.addEventListener("keydown", handleKeyDown);
      // Pasting the six digits from the email used to land entirely in the
      // first box, where maxlength kept one character and dropped the rest.
      elements.body.addEventListener("paste", handlePaste);
      window.addEventListener("pageshow", handlePageShow);

      forgotPasswordFlow?.preload?.();
      render();
      window.requestAnimationFrame(() => {
        syncRestoredFieldValues();
      });

      function render() {
        syncLockState();
        const content = getCurrentViewContent();
        if (elements.title) {
          elements.title.textContent = content.title;
        }
        if (elements.copy) {
          elements.copy.textContent = content.copy;
        }
        elements.body.innerHTML = renderView();
        syncPasswordToggleButtons(elements.body);
        syncBrandVisual();
        syncLockTimer();
      }

      function handlePageShow(event) {
        const currentUrl = new URL(window.location.href);
        const navigationEntry = window.performance?.getEntriesByType?.("navigation")?.[0];
        const restoredFromHistory = event.persisted || navigationEntry?.type === "back_forward";
        const shouldResetAfterLogout = currentUrl.searchParams.get("logout") === "1";

        if (shouldResetAfterLogout || restoredFromHistory) {
          resetLoginScreen({ clearLogoutFlag: shouldResetAfterLogout });
          return;
        }

        syncRestoredFieldValues();
      }

      function resetLoginScreen({ clearLogoutFlag = false } = {}) {
        state.view = "login";
        state.loginEmail = "";
        state.loginPassword = "";
        state.recoveryEmail = "";
        state.otp = initialOtpCode();
        state.newPassword = "";
        state.confirmPassword = "";
        state.notice = "";
        state.isSubmitting = false;
        state.challengeId = "";
        state.maskedEmail = "";
        state.expiresAt = "";
        state.lockedUntil = "";
        state.retryAfterSeconds = 0;
        clearLockTimer();

        if (clearLogoutFlag) {
          const cleanUrl = new URL(window.location.href);
          cleanUrl.searchParams.delete("logout");
          window.history.replaceState(window.history.state, "", cleanUrl.toString());
        }

        render();
      }

      function syncRestoredFieldValues() {
        if (state.view !== "login") {
          return;
        }

        const emailInput = document.getElementById("login-email");
        const passwordInput = document.getElementById("login-password");

        if (emailInput instanceof HTMLInputElement) {
          state.loginEmail = emailInput.value;
        }

        if (passwordInput instanceof HTMLInputElement) {
          state.loginPassword = passwordInput.value;
        }

        syncPasswordToggleButtons(elements.body);
        syncBrandVisual();
      }

      function getCurrentViewContent() {
        if (forgotPasswordFlow?.isForgotPasswordView?.(state.view)) {
          return forgotPasswordFlow.getViewContent(state.view);
        }

        return loginViewContent;
      }

      function renderView() {
        if (forgotPasswordFlow?.isForgotPasswordView?.(state.view)) {
          return forgotPasswordFlow.render(state, helpers);
        }

        const inputDisabled = state.isSubmitting || isLoginLocked();
        const linkDisabled = state.isSubmitting;

        return `
          ${getNoticeMarkup(state.notice)}
          <form class="login-form" id="login-form" novalidate>
            <label class="login-field" for="login-email">
              <span>Email</span>
              <input
                id="login-email"
                type="email"
                placeholder="Enter your Gmail address"
                value="${escapeHtml(state.loginEmail)}"
                ${inputDisabled ? "disabled" : ""}
              />
            </label>

            <label class="login-field" for="login-password">
              <span>Password</span>
              <div class="login-field__control">
                <input
                  id="login-password"
                  type="password"
                  placeholder="Enter your password"
                  value="${escapeHtml(state.loginPassword)}"
                  ${inputDisabled ? "disabled" : ""}
                />
                ${passwordToggleButtonMarkup("login-password")}
              </div>
            </label>

            ${showForgotPassword ? `
            <div class="login-actions">
              <button
                class="login-link"
                type="button"
                data-action="open-forgot-password"
                ${linkDisabled ? "disabled" : ""}
              >
                Forgot Password?
              </button>
            </div>` : ""}

            <button class="login-button" type="submit" data-action="submit-login" ${inputDisabled ? "disabled" : ""}>
              ${state.isSubmitting ? "Logging in..." : (isLoginLocked() ? "Locked for 5 Minutes" : "Log In")}
            </button>
          </form>
        `;
      }

      function handleClick(event) {
        const button = event.target.closest("[data-action]");
        if (!button) {
          return;
        }

        if (button.dataset.action === "toggle-password-visibility") {
          event.preventDefault();
          togglePasswordVisibility(button.dataset.target);
          return;
        }

        if (button.dataset.action === "submit-login" && button.closest("#login-form")) {
          event.preventDefault();
          void submitLogin();
          return;
        }

        if (forgotPasswordFlow?.handleAction?.(button.dataset.action, state, helpers)) {
          return;
        }
      }

      function handleSubmit(event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
          return;
        }

        event.preventDefault();

        if (forgotPasswordFlow?.handleSubmit?.(form.id, state, helpers)) {
          return;
        }

        if (form.id === "login-form") {
          void submitLogin();
        }
      }

      function handleInput(event) {
        const target = event.target;
        if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLSelectElement)) {
          return;
        }

        if (forgotPasswordFlow?.handleInput?.(target, state, helpers)) {
          syncBrandVisual();
          return;
        }

        switch (target.id) {
          case "login-email":
            state.loginEmail = target.value;
            break;
          case "login-password":
            state.loginPassword = target.value;
            break;
          default:
            return;
        }

        if (state.notice && !isLoginLocked()) {
          state.notice = "";
        }
        syncBrandVisual();
      }

      function handleKeyDown(event) {
        if (forgotPasswordFlow?.handleKeyDown?.(event, state, helpers)) {
          return;
        }
      }

      function handlePaste(event) {
        if (forgotPasswordFlow?.handleOtpPaste?.(event, state, helpers)) {
          render();
        }
      }

      async function submitLogin() {
        if (isLoginLocked()) {
          state.notice = createLockNotice();
          render();
          return;
        }

        const email = state.loginEmail.trim().toLowerCase();
        const password = state.loginPassword;

        if (!email || !password) {
          state.notice = "Please enter your Gmail address and password.";
          render();
          return;
        }

        if (!isValidGmailAddress(email)) {
          state.notice = "Use a valid Gmail address first.";
          render();
          return;
        }

        state.isSubmitting = true;
        state.notice = "";
        render();

        try {
          const device = await readLoginDeviceHints();
          const response = await requestJson("/api/auth/login", {
            method: "POST",
            timeoutMs: AUTH_REQUEST_TIMEOUT_MS,
            body: {
              email,
              password,
              clientId: authClientId(),
              device,
            },
          });
          const user = response.user || {};
          const secureSession = response.session || {};
          clearLockState();
          const session = writeSession({
            id: user.id,
            displayName: user.displayName,
            email: user.email,
            role: user.role,
            accessToken: secureSession.accessToken,
            expiresAt: secureSession.expiresAt,
          });
          if (!session) {
            throw new Error("The server did not return a valid secure session.");
          }
          redirectAfterLogin(session.role);
        } catch (error) {
          if (error?.payload && typeof error.payload === "object") {
            state.loginPassword = "";
            applyLoginAttemptFeedback(error.payload);
          } else {
            state.notice = extractRequestMessage(
              error,
              "Backend is not reachable. Start the Python server first.",
            );
          }
        } finally {
          state.isSubmitting = false;
          if (state.view === "login") {
            render();
          }
        }
      }

      function applyLoginAttemptFeedback(payload) {
        const message = extractPayloadMessage(payload, "Login failed.");
        const lockedUntil = String(payload?.lockedUntil || "").trim();
        const retryAfterSeconds = normalizeSeconds(payload?.retryAfterSeconds);
        const remainingAttempts = normalizeAttempts(payload?.remainingAttempts);

        if (lockedUntil && retryAfterSeconds > 0) {
          state.lockedUntil = lockedUntil;
          state.retryAfterSeconds = retryAfterSeconds;
          state.notice = createLockNotice(message);
          return;
        }

        clearLockState();
        if (remainingAttempts < 5) {
          state.notice = createFailureNotice(message, remainingAttempts);
          return;
        }

        state.notice = message;
      }

      function redirectAfterLogin(role) {
        const targetPath = normalizeRole(role) === "admin" ? postLoginPaths.admin : postLoginPaths.user;
        const nextHash = takePostLoginHash(role);
        const nextUrl = new URL(targetPath, window.location.href);
        nextUrl.search = window.location.search;
        nextUrl.hash = nextHash;
        window.location.replace(nextUrl.toString());
      }

      function getNoticeMarkup(notice) {
        if (!notice) {
          return "";
        }

        if (typeof notice === "string") {
          return `<div class="login-feedback" role="alert">${escapeHtml(notice)}</div>`;
        }

        const tone = String(notice?.tone || "info").trim().toLowerCase();
        const badge = String(notice?.badge || "").trim();
        const title = String(notice?.title || "").trim();
        const message = String(notice?.message || "").trim();
        const meta = String(notice?.meta || "").trim();
        const toneClass = tone ? ` login-feedback--${escapeHtml(tone)}` : "";

        return `
          <div class="login-feedback${toneClass}" role="alert">
            ${badge ? `<p class="login-feedback__badge">${escapeHtml(badge)}</p>` : ""}
            ${title ? `<p class="login-feedback__title">${escapeHtml(title)}</p>` : ""}
            ${message ? `<p class="login-feedback__message">${escapeHtml(message)}</p>` : ""}
            ${meta ? `<p class="login-feedback__meta" id="login-feedback-meta">${escapeHtml(meta)}</p>` : ""}
          </div>
        `;
      }

      function createFailureNotice(message, remainingAttempts) {
        return {
          tone: "danger",
          badge: "Account Security",
          title: "Login attempt recorded",
          message,
          meta: `${remainingAttempts} attempt(s) remaining before a 5-minute lock.`,
        };
      }

      function createLockNotice(message = "") {
        const secondsLeft = state.retryAfterSeconds > 0
          ? state.retryAfterSeconds
          : secondsUntil(state.lockedUntil);
        const normalizedSeconds = Math.max(0, secondsLeft);
        const countdown = formatCountdown(normalizedSeconds);

        return {
          tone: "danger",
          badge: "Account Locked",
          title: "Too many failed login attempts",
          message: message || "Login is temporarily locked.",
          meta: countdown ? `Try again in ${countdown}.` : "Try again after 5 minutes.",
        };
      }

      function syncLockState() {
        if (!state.lockedUntil) {
          state.retryAfterSeconds = 0;
          return;
        }

        const secondsLeft = secondsUntil(state.lockedUntil);
        if (secondsLeft <= 0) {
          clearLockState();
          if (isLockNotice(state.notice)) {
            state.notice = "";
          }
          return;
        }

        state.retryAfterSeconds = secondsLeft;
        if (isLockNotice(state.notice)) {
          state.notice = createLockNotice(extractNoticeMessage(state.notice));
        }
      }

      function clearLockState() {
        state.lockedUntil = "";
        state.retryAfterSeconds = 0;
        clearLockTimer();
      }

      function isLoginLocked() {
        return Boolean(state.lockedUntil)
          && secondsUntil(state.lockedUntil) > 0;
      }

      function syncLockTimer() {
        if (state.view !== "login" || !state.lockedUntil) {
          clearLockTimer();
          return;
        }

        if (lockTimerId) {
          return;
        }

        lockTimerId = window.setInterval(() => {
          const wasLocked = isLoginLocked();
          syncLockState();
          if (!wasLocked || !isLoginLocked()) {
            // A real state transition (lock just expired) needs the form
            // re-enabled, so a full render here is correct and only happens once.
            render();
            return;
          }

          if (isLockNotice(state.notice)) {
            state.notice = createLockNotice(extractNoticeMessage(state.notice));
          }

          // Routine per-second countdown tick: patch just the countdown text so the
          // login form (inputs, buttons, notice card) doesn't remount and blink every second.
          if (!updateLockCountdownInPlace()) {
            render();
          }
        }, 1000);
      }

      function updateLockCountdownInPlace() {
        if (!isLockNotice(state.notice)) {
          return false;
        }

        const metaElement = document.getElementById("login-feedback-meta");
        if (!metaElement) {
          return false;
        }

        metaElement.textContent = String(state.notice.meta || "");
        return true;
      }

      function clearLockTimer() {
        if (!lockTimerId) {
          return;
        }

        window.clearInterval(lockTimerId);
        lockTimerId = 0;
      }

      function isLockNotice(notice) {
        return Boolean(notice && typeof notice === "object" && notice.badge === "Account Locked");
      }

      function extractNoticeMessage(notice) {
        if (notice && typeof notice === "object" && notice.message) {
          return String(notice.message);
        }

        return "";
      }

      function extractPayloadMessage(payload, fallback) {
        if (payload && typeof payload === "object" && payload.message) {
          return String(payload.message);
        }

        return fallback;
      }

      function normalizeSeconds(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric) || numeric <= 0) {
          return 0;
        }

        return Math.max(0, Math.ceil(numeric));
      }

      function normalizeAttempts(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
          return 5;
        }

        return Math.max(0, Math.floor(numeric));
      }

      function secondsUntil(isoString) {
        const targetTime = Date.parse(String(isoString || ""));
        if (!Number.isFinite(targetTime)) {
          return 0;
        }

        return Math.max(0, Math.ceil((targetTime - Date.now()) / 1000));
      }

      function formatCountdown(totalSeconds) {
        const safeSeconds = Math.max(0, Number(totalSeconds) || 0);
        if (!safeSeconds) {
          return "";
        }

        const minutes = Math.floor(safeSeconds / 60);
        const seconds = safeSeconds % 60;
        return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
      }

      function passwordToggleButtonMarkup(targetId, disabled = false) {
        return `
          <button
            class="login-password-toggle"
            type="button"
            data-action="toggle-password-visibility"
            data-target="${targetId}"
            aria-label="Show password"
            ${disabled ? "disabled" : ""}
          >
            <span class="login-password-toggle__icon" data-password-icon aria-hidden="true"></span>
          </button>
        `;
      }

      function togglePasswordVisibility(targetId) {
        if (!targetId) {
          return;
        }

        const input = document.getElementById(targetId);
        if (!(input instanceof HTMLInputElement)) {
          return;
        }

        input.type = input.type === "password" ? "text" : "password";
        syncPasswordToggleButtons(elements.body);
        input.focus({ preventScroll: true });
        const valueLength = input.value.length;
        if (typeof input.setSelectionRange === "function") {
          input.setSelectionRange(valueLength, valueLength);
        }
      }

      function syncPasswordToggleButtons(root = elements.body) {
        if (!(root instanceof HTMLElement)) {
          return;
        }

        root.querySelectorAll("[data-action='toggle-password-visibility']").forEach((button) => {
          if (!(button instanceof HTMLButtonElement)) {
            return;
          }

          const targetId = button.dataset.target;
          const input = targetId ? document.getElementById(targetId) : null;
          if (!(input instanceof HTMLInputElement)) {
            return;
          }

          const visible = input.type === "text";
          button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
          const iconSlot = button.querySelector("[data-password-icon]");
          if (iconSlot) {
            iconSlot.innerHTML = authIconMarkup(visible ? "eye" : "eye-off");
          }
        });
      }

      function syncBrandVisual() {
        if (!(elements.brand instanceof HTMLElement)) {
          return;
        }

        elements.brand.classList.toggle("is-password-active", hasActivePasswordInput());
      }

      function hasActivePasswordInput() {
        if (state.view === "login") {
          return state.loginPassword.length > 0;
        }

        if (state.view === "reset-password") {
          return state.newPassword.length > 0 || state.confirmPassword.length > 0;
        }

        return false;
      }

      function authIconMarkup(name) {
        const paths = {
          eye: `
            <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"></path>
            <circle cx="12" cy="12" r="3"></circle>
          `,
          "eye-off": `
            <path d="m3 3 18 18"></path>
            <path d="M10.58 10.58a2 2 0 0 0 2.83 2.83"></path>
            <path d="M9.88 5.08A10.94 10.94 0 0 1 12 5c6 0 10 7 10 7a18.74 18.74 0 0 1-3.04 3.81"></path>
            <path d="M6.61 6.61A18.7 18.7 0 0 0 2 12s4 7 10 7a9.76 9.76 0 0 0 5.39-1.61"></path>
          `,
        };

        return `
          <svg
            class="auth-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            ${paths[name] || paths.eye}
          </svg>
        `;
      }

      function extractRequestMessage(error, fallback) {
        if (error && typeof error === "object" && "payload" in error && error.payload?.message) {
          return String(error.payload.message);
        }

        // A request that never reached the server has no message worth showing. The
        // browser's own wording for that is "Failed to fetch" (Safari says "Load
        // failed", Firefox "NetworkError"), which went straight into the notice and
        // told the user nothing about what had happened or what to do.
        if (
          error instanceof TypeError
          && /failed to fetch|networkerror|load failed/i.test(String(error.message || ""))
        ) {
          return fallback;
        }

        if (
          error
          && typeof error === "object"
          && "code" in error
          && String(error.code || "").toUpperCase() === "INVALID_API_RESPONSE"
        ) {
          return fallback;
        }

        if (error instanceof Error && error.message) {
          return error.message;
        }

        return fallback;
      }

      function isValidGmailAddress(value) {
        return /^[a-z0-9._%+-]+@gmail\.com$/i.test(String(value || "").trim());
      }

      function initialOtpCode() {
        return ["", "", "", "", "", ""];
      }

      function escapeHtml(value) {
        return String(value)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init, { once: true });
      return;
    }

    init();
  }


  async function requestBlob(path, options = {}) {
    // requestJson resolves the API base by trying each candidate in turn, and
    // a file download needs exactly the same resolution: the Pi, the hosted
    // site and a dev machine on another port all reach the backend by a
    // different one. It cannot reuse requestJson itself because that parses
    // every response as JSON, and a workbook is bytes.
    const method = String(options.method || "POST").toUpperCase();
    const headers = new Headers(options.headers || {});
    const activeSession = readSession();
    if (activeSession?.accessToken) {
      headers.set("Authorization", `Bearer ${activeSession.accessToken}`);
    }

    let body = options.body;
    if (body !== undefined && body !== null && !(body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(body);
    }

    const requestedTimeout = Number.parseInt(options.timeoutMs, 10);
    const timeoutMs = Number.isFinite(requestedTimeout) && requestedTimeout > 0
      ? requestedTimeout
      : DEFAULT_REQUEST_TIMEOUT_MS;

    let lastError = null;
    for (const base of candidateApiBases()) {
      const requestUrl = new URL(path, `${base}/`).toString();
      const abortController = typeof AbortController === "function" ? new AbortController() : null;
      let timeoutId = 0;
      let requestTimedOut = false;
      if (abortController) {
        timeoutId = global.setTimeout(() => {
          requestTimedOut = true;
          abortController.abort();
        }, timeoutMs);
      }

      // The timeout guards reaching the server, not draining the body. A report
      // is megabytes and streams in well after the headers arrive, so leaving
      // the timer armed across `response.blob()` aborted big downloads midway
      // -- and an abort raised there carries no status, so it was retried
      // against every other base before failing.
      const stopTimeout = () => {
        if (timeoutId) {
          global.clearTimeout(timeoutId);
          timeoutId = 0;
        }
      };

      try {
        const response = await fetch(requestUrl, {
          method,
          headers: new Headers(headers),
          body,
          cache: "no-store",
          signal: abortController?.signal,
        });

        stopTimeout();

        if (!response.ok) {
          let message = `Request failed with status ${response.status}.`;
          let payload = {};
          try {
            payload = (await response.json()) || {};
            message = payload?.message || message;
          } catch (error) {
            // A non-JSON error body leaves the status message above.
          }

          // A download must read a 401 exactly the way requestJson does. It
          // used to skip this entirely, so the two 401s that are not a real
          // expiry were treated as one: a passing backend outage, and the
          // report's own second request arriving while another tab held the
          // newer session. Both ended the login mid-download.
          if (response.status === 401 && !String(path).startsWith("/api/auth/")) {
            if (payload?.code === "AUTH_SESSION_SUPERSEDED") {
              showAccountInUseNotice(payload);
            } else if (payload?.code === "AUTH_BACKEND_UNAVAILABLE" || !payload?.code) {
              // The records could not be read, or the host answered a 401 of
              // its own that never reached the auth guard. Neither is a
              // rejected session, so it must survive -- the caller just
              // reports a failed download.
            } else {
              clearActiveRoleSession();
            }
          }

          const failure = buildRequestError(message, {
            status: response.status,
            payload,
            base,
          });
          // A wrong base answers 404/405; a real refusal must not be retried
          // against the next candidate.
          if (!shouldTryNextCandidate(failure)) {
            throw failure;
          }
          lastError = failure;
          forgetApiBase(base);
          continue;
        }

        // A 200 is not proof of a file. When the host kills the function mid
        // build (Vercel stops it at 60s) it answers with its own HTML error
        // page, and that used to be saved straight to disk as a .pdf that no
        // reader could open. Anything that is not a document is an error here.
        const responseType = String(response.headers.get("content-type") || "").toLowerCase();
        if (responseType.includes("text/html")) {
          const failure = buildRequestError(
            "The report did not finish building. Please try a shorter date range.",
            { status: response.status, base, code: "INVALID_API_RESPONSE" },
          );
          lastError = failure;
          forgetApiBase(base);
          continue;
        }

        rememberApiBase(base);
        const disposition = String(response.headers.get("content-disposition") || "");
        const headerName = String(response.headers.get("x-icucrops-filename") || "");
        const match = /filename="?([^"]+)"?/i.exec(disposition);
        return {
          blob: await response.blob(),
          filename: headerName || match?.[1] || "",
        };
      } catch (error) {
        const requestError = requestTimedOut
          ? buildRequestError("The report took too long to build. Please try a shorter date range.", {
            status: 0,
            base,
            code: "REQUEST_TIMEOUT",
          })
          : error;
        if (requestError?.status && !shouldTryNextCandidate(requestError)) {
          throw requestError;
        }
        lastError = requestError;
        forgetApiBase(base);
      } finally {
        stopTimeout();
      }
    }

    throw lastError || buildRequestError("The server could not be reached.");
  }

  global.ICuCropsAuth = {
    SESSION_KEY,
    roleAuthKey,
    roleHashKey,
    roleLabel,
    normalizeRole,
    readSession,
    writeSession,
    clearSession,
    // Ends one role's session only. Exported so a shell can sign itself out
    // without ending the other role signed in on the same browser.
    clearRoleSession,
    protectSessionHistory,
    rememberPostLoginHash,
    takePostLoginHash,
    maskEmail,
    requestJson,
    requestBlob,
    serverNow,
    AUTH_REQUEST_TIMEOUT_MS,
    PASSWORD_POLICY_MESSAGE,
    isValidNewPassword,
    createLoginController,
  };
})(window);
