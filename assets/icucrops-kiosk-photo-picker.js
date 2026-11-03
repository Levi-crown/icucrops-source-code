// In-app replacement for Chromium's native file dialog, used by the Raspberry
// Pi kiosk only. The native dialog exposes the whole filesystem -- root, /media
// and every home folder -- from a touch panel that stands in the open, so on
// the kiosk the profile photo is chosen from one server-side folder instead and
// the dialog is never opened at all. See /api/kiosk/photos in main.py for the
// directory this reads and the rules it enforces.
(function attachKioskPhotoPicker(global) {
  const LIST_ENDPOINT = "/api/kiosk/photos";
  const THUMBNAIL_CONCURRENCY = 3;
  const STYLE_ID = "icucrops-kiosk-photo-picker-style";

  let activeSession = null;

  // Colours here are deliberately neutral greys and currentColor: the dark
  // theme is a pile of blanket !important rules keyed on existing class names,
  // so anything that sets its own palette needs a dark partner rule to match.
  // Borrowing the modal's inherited colour keeps this readable in both themes
  // and at the kiosk's 800x480 viewport.
  const STYLE_TEXT = [
    ".kiosk-photo-picker__body{display:flex;flex-direction:column;gap:14px;}",
    ".kiosk-photo-picker__grid{display:grid;gap:10px;",
    "grid-template-columns:repeat(auto-fill,minmax(104px,1fr));",
    "max-height:min(46vh,320px);overflow-y:auto;padding:2px;}",
    ".kiosk-photo-picker__tile{position:relative;display:flex;flex-direction:column;",
    "gap:6px;padding:6px;border-radius:14px;border:1px solid rgba(127,127,127,0.38);",
    "background:rgba(127,127,127,0.14);color:inherit;font:inherit;cursor:pointer;",
    "text-align:left;}",
    ".kiosk-photo-picker__tile:disabled{opacity:0.45;cursor:not-allowed;}",
    ".kiosk-photo-picker__tile:focus-visible{outline:2px solid currentColor;outline-offset:2px;}",
    ".kiosk-photo-picker__frame{aspect-ratio:1/1;border-radius:10px;overflow:hidden;",
    "background:rgba(127,127,127,0.22);display:flex;align-items:center;justify-content:center;}",
    ".kiosk-photo-picker__frame img{width:100%;height:100%;object-fit:cover;display:block;}",
    ".kiosk-photo-picker__name{font-size:11px;line-height:1.25;word-break:break-word;opacity:0.85;}",
    ".kiosk-photo-picker__status{font-size:13px;line-height:1.4;opacity:0.85;",
    "padding:18px 6px;text-align:center;}",
    ".kiosk-photo-picker__hint{font-size:12px;line-height:1.45;opacity:0.75;}",
  ].join("");

  function isEnabled() {
    return global.ICuCropsPiMode === true;
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = STYLE_TEXT;
    document.head.appendChild(style);
  }

  function authHeaders() {
    const headers = new Headers({ Accept: "application/json" });
    const session = global.ICuCropsAuth?.readSession?.();
    if (session?.accessToken) {
      headers.set("Authorization", "Bearer " + session.accessToken);
    }
    return headers;
  }

  async function fetchLibrary() {
    const response = await fetch(LIST_ENDPOINT, {
      cache: "no-store",
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error("Photo library request failed (" + response.status + ").");
    }
    return response.json();
  }

  async function fetchPhotoFile(entry) {
    const photoUrl = LIST_ENDPOINT + "/" + encodeURIComponent(entry.name);
    const response = await fetch(photoUrl, {
      cache: "no-store",
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error("Photo request failed (" + response.status + ").");
    }

    const blob = await response.blob();
    return new File([blob], entry.name, {
      type: blob.type || "image/png",
      lastModified: (Number(entry.modified) || 0) * 1000,
    });
  }

  function formatSize(bytes) {
    const value = Number(bytes) || 0;
    if (value >= 1024 * 1024) {
      return (value / (1024 * 1024)).toFixed(1) + " MB";
    }
    return Math.max(1, Math.round(value / 1024)) + " KB";
  }

  function close(result) {
    if (!activeSession) {
      return;
    }

    const session = activeSession;
    activeSession = null;
    session.objectUrls.forEach((url) => URL.revokeObjectURL(url));
    document.removeEventListener("keydown", session.onKeyDown, true);
    session.overlay.remove();
    session.previousFocus?.focus?.();
    session.resolve(result || null);
  }

  function buildOverlay() {
    const overlay = document.createElement("div");
    overlay.className = "overlay overlay--center overlay--dialog kiosk-photo-picker-overlay";
    overlay.innerHTML = [
      '<div class="modal modal--sm kiosk-photo-picker" role="dialog" aria-modal="true"',
      ' aria-labelledby="kiosk-photo-picker-title">',
      '<div class="modal__body kiosk-photo-picker__body">',
      "<div>",
      '<h3 class="section-title" id="kiosk-photo-picker-title">Choose a Profile Photo</h3>',
      '<p class="section-copy kiosk-photo-picker__hint" data-picker-hint>Loading the photo folder...</p>',
      "</div>",
      '<div class="kiosk-photo-picker__grid" data-picker-grid hidden></div>',
      '<p class="kiosk-photo-picker__status" data-picker-status>Loading photos...</p>',
      '<div class="modal__actions">',
      '<button class="button button--secondary button--full" type="button" data-picker-cancel>',
      "Cancel",
      "</button>",
      "</div>",
      "</div>",
      "</div>",
    ].join("");

    // The app routes every click through one delegated [data-action] listener;
    // keeping the picker's own clicks from bubbling stops a stray backdrop
    // handler from closing the settings modal underneath it.
    overlay.addEventListener("click", (event) => {
      event.stopPropagation();
      if (event.target === overlay) {
        close(null);
      }
    });

    return overlay;
  }

  async function loadThumbnails(pending, session) {
    const queue = pending.slice();

    const worker = async () => {
      while (queue.length && activeSession === session) {
        const item = queue.shift();
        try {
          const file = await fetchPhotoFile(item.entry);
          if (activeSession !== session) {
            return;
          }

          const objectUrl = URL.createObjectURL(file);
          session.objectUrls.push(objectUrl);
          const image = document.createElement("img");
          image.alt = item.entry.name;
          image.decoding = "async";
          image.src = objectUrl;
          item.frame.replaceChildren(image);
          item.tile.disabled = false;
          item.tile.addEventListener("click", () => close(file));
        } catch (error) {
          item.frame.textContent = "!";
          item.tile.disabled = true;
        }
      }
    };

    const workerCount = Math.min(THUMBNAIL_CONCURRENCY, queue.length);
    await Promise.all(Array.from({ length: workerCount }, worker));
  }

  function renderEntries(payload, session) {
    const { overlay } = session;
    const grid = overlay.querySelector("[data-picker-grid]");
    const status = overlay.querySelector("[data-picker-status]");
    const hint = overlay.querySelector("[data-picker-hint]");
    const folder = String(payload?.folder || "Pictures");
    const photos = Array.isArray(payload?.photos) ? payload.photos : [];

    hint.textContent = "Only the " + folder + " folder on this device is available here.";

    if (!photos.length) {
      grid.hidden = true;
      status.hidden = false;
      status.textContent = payload?.available === false
        ? "The " + folder + " folder was not found on this device."
        : "The " + folder + " folder is empty. Copy an image into it to use it as a profile photo.";
      return [];
    }

    const pending = [];
    photos.forEach((entry) => {
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = "kiosk-photo-picker__tile";
      tile.disabled = true;

      const frame = document.createElement("div");
      frame.className = "kiosk-photo-picker__frame";

      const name = document.createElement("span");
      name.className = "kiosk-photo-picker__name";
      name.textContent = entry.tooLarge
        ? entry.name + " (" + formatSize(entry.bytes) + " - too large)"
        : entry.name;

      tile.append(frame, name);
      grid.appendChild(tile);

      if (!entry.tooLarge) {
        pending.push({ entry, frame, tile });
      }
    });

    grid.hidden = false;
    status.hidden = true;
    return pending;
  }

  function open() {
    if (activeSession) {
      return Promise.resolve(null);
    }

    ensureStyle();
    const overlay = buildOverlay();

    return new Promise((resolve) => {
      const session = {
        overlay,
        resolve,
        objectUrls: [],
        previousFocus: document.activeElement instanceof HTMLElement ? document.activeElement : null,
        onKeyDown(event) {
          if (event.key === "Escape") {
            event.stopPropagation();
            close(null);
          }
        },
      };
      activeSession = session;

      const cancelButton = overlay.querySelector("[data-picker-cancel]");
      cancelButton.addEventListener("click", () => close(null));
      document.addEventListener("keydown", session.onKeyDown, true);
      document.body.appendChild(overlay);
      cancelButton.focus?.();

      void (async () => {
        try {
          const payload = await fetchLibrary();
          if (activeSession !== session) {
            return;
          }

          const pending = renderEntries(payload, session);
          if (pending.length) {
            await loadThumbnails(pending, session);
          }
        } catch (error) {
          if (activeSession !== session) {
            return;
          }

          const grid = overlay.querySelector("[data-picker-grid]");
          const status = overlay.querySelector("[data-picker-status]");
          grid.hidden = true;
          status.hidden = false;
          status.textContent = "The photo library is unavailable on this device right now.";
        }
      })();
    });
  }

  global.ICuCropsKioskPhotoPicker = { isEnabled, open };
})(window);
