(function installICuCropsSlowActivation(global) {
  "use strict";

  if (global.ICuCropsSlowActivation?.installed) {
    return;
  }

  // The press animation itself finishes in 90ms (see the :active /
  // .is-button-pressing rule in icucrops-ios-interactions.css). Holding the
  // click for 260ms meant every tap in the app waited ~170ms after the
  // animation had already settled, which is what made the shell feel laggy on
  // the Pi and on mobile. Match the animation instead of outrunning it.
  const ACTIVATION_DELAY_MS = 90;
  const ACTIVATION_SELECTOR = [
    "button",
    "a[href]",
    "input[type='button']",
    "input[type='submit']",
    "input[type='reset']",
    "[role='button']",
    "[data-action]",
    "[data-view]",
    "[data-tab]",
    "[data-mode]",
  ].join(",");
  const NATIVE_ACTIVATION_ACTIONS = new Set([
    "change-profile-photo",
    // Password visibility must react immediately. Delaying and replaying the
    // click made the eye button look broken over Pi remote-desktop sessions,
    // especially while the login request was still waiting on the backend.
    "toggle-password-visibility",
    // Irrigation controls command real pumps, and the actuator mode buttons
    // command the fan and grow light. Holding any of these for the press
    // animation made switching a row to automatic (or the fan to on) feel
    // broken on the Pi, so these all run natively instead.
    "set-irrigation-mode",
    "set-row-irrigation-mode",
    "toggle-auto-irrigation",
    "toggle-manual-irrigation",
    "toggle-row-manual-irrigation",
    "toggle-schedule-irrigation",
    "toggle-row-schedule-irrigation",
    "set-actuator-mode",
    // The advisory card's own buttons, for the same reason: confirming is what
    // actually opens the valve or starts the fan, and Cancel has to feel as
    // immediate as the button beside it.
    "confirm-control-advisory",
    "dismiss-control-advisory",
  ]);

  global.ICuCropsSlowActivation = {
    installed: true,
    delayMs: ACTIVATION_DELAY_MS,
  };

  document.addEventListener("click", handleActivation, true);
  document.addEventListener("pointerup", clearPressedTargets, true);
  document.addEventListener("pointercancel", clearPressedTargets, true);
  document.addEventListener("dragstart", clearPressedTargets, true);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearPressedTargets();
    }
  });
  global.addEventListener("blur", clearPressedTargets);
  global.addEventListener("pageshow", clearPressedTargets);

  function handleActivation(event) {
    if (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }

    const target = event.target instanceof Element
      ? event.target.closest(ACTIVATION_SELECTOR)
      : null;
    if (!(target instanceof HTMLElement) || shouldUseNativeActivation(target)) {
      return;
    }

    if (target.dataset.iosActivationReady === "true") {
      delete target.dataset.iosActivationReady;
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();

    if (target.dataset.iosActivationPending === "true") {
      return;
    }

    target.dataset.iosActivationPending = "true";
    target.classList.add("is-button-pressing");
    const exitSurface = exitSurfaceFor(target);
    exitSurface?.classList.add("is-default-surface-exiting");

    global.setTimeout(() => {
      delete target.dataset.iosActivationPending;
      target.classList.remove("is-button-pressing");

      if (!target.isConnected || isDisabled(target)) {
        exitSurface?.classList.remove("is-default-surface-exiting");
        return;
      }

      target.dataset.iosActivationReady = "true";
      target.dataset.smoothActivationReady = "true";
      target.click();

      global.setTimeout(() => {
        delete target.dataset.iosActivationReady;
        delete target.dataset.smoothActivationReady;
        if (exitSurface?.isConnected) {
          exitSurface.classList.remove("is-default-surface-exiting");
        }
      }, 0);
    }, prefersReducedMotion() ? 0 : ACTIVATION_DELAY_MS);
  }

  function shouldUseNativeActivation(target) {
    const action = String(target.dataset.action || "").trim();
    return isDisabled(target)
      || NATIVE_ACTIVATION_ACTIONS.has(action)
      || target.matches("select, option, input[type='file'], input[type='checkbox'], input[type='radio']")
      || Boolean(target.closest("label")?.querySelector("input[type='file'], input[type='checkbox'], input[type='radio']"));
  }

  function clearPressedTargets() {
    document.querySelectorAll(".is-button-pressing").forEach((target) => {
      target.classList.remove("is-button-pressing");
    });
  }

  function isDisabled(target) {
    return target.matches(":disabled, [disabled], [aria-disabled='true']");
  }

  function exitSurfaceFor(target) {
    const action = String(target.dataset.action || "").trim();
    const label = String(target.getAttribute("aria-label") || "").trim();
    const exitsSurface = /^(?:close|cancel|back|dismiss)(?:-|$)/i.test(action)
      || /^(?:close|cancel|back|dismiss)\b/i.test(label);
    if (!exitsSurface) {
      return null;
    }

    return target.closest(".overlay, .settings-menu-shell, .toast, #auth-panel-body");
  }

  function prefersReducedMotion() {
    return global.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
  }
})(window);
