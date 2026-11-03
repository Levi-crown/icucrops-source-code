const MOBILE_DRAWER_OPEN_CLASS = "is-mobile-drawer-open";
const MOBILE_WEB_NAV_LABELS = {
  dashboard: "Dash",
  history: "History",
  sensors: "Sensors",
  irrigation: "Water",
  cultivation: "Grow",
  reports: "Reports",
  "manage-account": "Account",
};

document.addEventListener("DOMContentLoaded", initMobileWebShell);

function initMobileWebShell() {
  const shell = {
    body: document.body,
    sidebarNav: document.getElementById("sidebar-nav"),
    menuButton: document.getElementById("mobile-menu-button"),
    drawerBackdrop: document.getElementById("mobile-drawer-backdrop"),
    bottomNav: document.getElementById("mobile-bottom-nav"),
  };

  if (!(shell.body instanceof HTMLElement) || !(shell.sidebarNav instanceof HTMLElement) || !(shell.bottomNav instanceof HTMLElement)) {
    return;
  }

  enforceHeaderActionParity();
  closeDrawer(shell);

  shell.menuButton?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    toggleDrawer(shell);
  });

  shell.drawerBackdrop?.addEventListener("click", () => {
    closeDrawer(shell);
  });

  document.addEventListener("pointerdown", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    if (!shell.body.classList.contains(MOBILE_DRAWER_OPEN_CLASS)) {
      return;
    }

    if (target.closest(".sidebar") || target.closest("#mobile-menu-button")) {
      return;
    }

    closeDrawer(shell);
  }, true);

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    if (target.closest("#mobile-menu-button")) {
      return;
    }

    const sidebarViewButton = target.closest(".sidebar [data-view]");
    if (sidebarViewButton) {
      event.preventDefault();
      event.stopPropagation();
      activateMobileView(sidebarViewButton, shell);
      return;
    }

    if (target.closest(".sidebar [data-action]")) {
      window.setTimeout(() => closeDrawer(shell), 0);
      return;
    }

    if (
      target.closest("#mobile-bottom-nav [data-view]")
      || (
        shell.body.classList.contains(MOBILE_DRAWER_OPEN_CLASS)
        && !target.closest(".sidebar")
      )
    ) {
      const bottomNavButton = target.closest("#mobile-bottom-nav [data-view]");
      if (bottomNavButton) {
        event.preventDefault();
        event.stopPropagation();
        activateMobileView(bottomNavButton, shell);
        return;
      }
      closeDrawer(shell);
    }
  }, true);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer(shell);
    }
  });

  window.addEventListener("hashchange", () => {
    closeDrawer(shell);
    window.requestAnimationFrame(() => syncBottomNav(shell.sidebarNav, shell.bottomNav));
  });
  window.addEventListener("pageshow", () => {
    enforceHeaderActionParity();
    closeDrawer(shell);
    syncBottomNav(shell.sidebarNav, shell.bottomNav);
  });

  const navObserver = new MutationObserver(() => {
    syncBottomNav(shell.sidebarNav, shell.bottomNav);
  });

  navObserver.observe(shell.sidebarNav, {
    attributes: true,
    attributeFilter: ["class", "aria-current"],
    childList: true,
    subtree: true,
  });

  // A phone or tablet can be wider than the old compact breakpoint after an
  // orientation change. Keep the selected mobile shell stable; redirecting on
  // width created a mobile -> desktop -> mobile loop on iPad landscape.
  const syncOrientationLayout = () => {
    closeDrawer(shell);
    window.requestAnimationFrame(enforceHeaderActionParity);
    window.requestAnimationFrame(() => syncBottomNav(shell.sidebarNav, shell.bottomNav));
  };
  window.addEventListener("orientationchange", syncOrientationLayout, { passive: true });
  window.visualViewport?.addEventListener("resize", syncOrientationLayout, { passive: true });

  syncBottomNav(shell.sidebarNav, shell.bottomNav);
  syncDrawerBackdrop(shell);
  window.requestAnimationFrame(enforceHeaderActionParity);
  window.requestAnimationFrame(() => closeDrawer(shell));
  window.setTimeout(enforceHeaderActionParity, 60);
  window.setTimeout(() => closeDrawer(shell), 60);
  window.setTimeout(enforceHeaderActionParity, 240);
  window.setTimeout(() => closeDrawer(shell), 240);
}

function activateMobileView(button, shell) {
  const view = String(button?.getAttribute?.("data-view") || "").trim();
  if (!view) {
    return;
  }

  setBottomNavActive(shell.bottomNav, view);
  closeDrawer(shell);

  // Keep the mobile shell functional even if the main app's delegated click
  // handler is delayed or replaced during a route transition.
  const targetHash = view === "dashboard" ? "#/" : `#/${view}`;
  window.setTimeout(() => {
    if (typeof window.navigateTo === "function") {
      window.navigateTo(view);
      return;
    }
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    }
  }, 0);
}

function enforceHeaderActionParity() {
  const topbar = document.querySelector(".topbar");
  const actions = document.querySelector(".topbar__actions");
  const buttons = document.querySelectorAll(".topbar .theme-toggle-button.icon-button, .topbar .notification-button.icon-button");

  const compactHeader = window.innerWidth <= 380;
  const controlSize = compactHeader ? "2.08rem" : "2.3rem";
  const actionGap = compactHeader ? "0.22rem" : "0.42rem";

  if (topbar instanceof HTMLElement) {
    topbar.style.setProperty("grid-template-columns", `${controlSize} minmax(0, 1fr) max-content`, "important");
  }

  if (actions instanceof HTMLElement) {
    actions.style.setProperty("width", "auto", "important");
    actions.style.setProperty("min-width", "0", "important");
    actions.style.setProperty("flex", "0 0 auto", "important");
    actions.style.setProperty("display", "grid", "important");
    actions.style.setProperty("grid-auto-flow", "column", "important");
    actions.style.setProperty("grid-auto-columns", controlSize, "important");
    actions.style.setProperty("align-items", "center", "important");
    actions.style.setProperty("justify-content", "flex-end", "important");
    actions.style.setProperty("gap", actionGap, "important");
  }

  buttons.forEach((button) => {
    if (!(button instanceof HTMLElement)) {
      return;
    }

    button.style.setProperty("width", controlSize, "important");
    button.style.setProperty("height", controlSize, "important");
    button.style.setProperty("min-width", controlSize, "important");
    button.style.setProperty("flex", `0 0 ${controlSize}`, "important");
    button.style.setProperty("padding", "0", "important");
    button.style.setProperty("border-radius", "0.82rem", "important");
    button.style.setProperty("display", "grid", "important");
    button.style.setProperty("place-items", "center", "important");

    const iconWrap = button.querySelector(".nav-button__icon");
    if (iconWrap instanceof HTMLElement) {
      iconWrap.style.setProperty("width", "1.62rem", "important");
      iconWrap.style.setProperty("height", "1.62rem", "important");
      iconWrap.style.setProperty("flex", "0 0 1.62rem", "important");
      iconWrap.style.setProperty("background", "transparent", "important");
      iconWrap.style.setProperty("border", "0", "important");
      iconWrap.style.setProperty("box-shadow", "none", "important");
    }

    const icon = button.querySelector(".icon");
    if (icon instanceof SVGElement) {
      icon.style.setProperty("width", "1.12rem", "important");
      icon.style.setProperty("height", "1.12rem", "important");
      icon.style.setProperty("stroke-width", "2.1", "important");
    }
  });
}

function syncBottomNav(sidebarNav, bottomNav) {
  const navButtons = Array.from(sidebarNav.querySelectorAll("[data-view]"));
  const navColumnCount = Math.max(navButtons.length, 1);

  bottomNav.hidden = navButtons.length === 0;
  bottomNav.style.setProperty("--mobile-bottom-nav-columns", String(navColumnCount));

  const desired = navButtons.map((button) => {
    const view = button.getAttribute("data-view") || "";
    return {
      view,
      iconMarkup: button.querySelector(".nav-button__icon")?.innerHTML || "",
      label: MOBILE_WEB_NAV_LABELS[view] || extractNavButtonLabel(button),
      active: button.classList.contains("is-active"),
    };
  });

  // Patch existing buttons in place whenever possible instead of rebuilding
  // via innerHTML. A rebuild replaces the DOM node mid-tap, which cancels the
  // background-color transition started by setBottomNavActive() and briefly
  // exposes the transparent/glass base state (a white flash before green).
  const existing = Array.from(bottomNav.children);
  const structureMatches =
    existing.length === desired.length
    && existing.every((el, index) => el.getAttribute("data-view") === desired[index].view);

  if (structureMatches) {
    existing.forEach((el, index) => {
      const item = desired[index];
      el.classList.toggle("is-active", item.active);
      if (item.active) {
        el.setAttribute("aria-current", "page");
      } else {
        el.removeAttribute("aria-current");
      }

      const iconEl = el.querySelector(".mobile-bottom-nav__icon");
      if (iconEl instanceof HTMLElement && iconEl.innerHTML !== item.iconMarkup) {
        iconEl.innerHTML = item.iconMarkup;
      }

      const labelEl = el.querySelector(".mobile-bottom-nav__label");
      if (labelEl instanceof HTMLElement && labelEl.textContent !== item.label) {
        labelEl.textContent = item.label;
      }
    });
    return;
  }

  bottomNav.innerHTML = desired
    .map((item) => {
      const activeClass = item.active ? " is-active" : "";

      return `
        <button class="mobile-bottom-nav__button${activeClass}" type="button" data-view="${escapeHtml(item.view)}" ${activeClass ? 'aria-current="page"' : ""}>
          <span class="mobile-bottom-nav__icon" aria-hidden="true">${item.iconMarkup}</span>
          <span class="mobile-bottom-nav__label">${escapeHtml(item.label)}</span>
        </button>
      `;
    })
    .join("");
}

function setBottomNavActive(bottomNav, activeView) {
  if (!(bottomNav instanceof HTMLElement)) {
    return;
  }

  bottomNav.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.getAttribute("data-view") === activeView;
    button.classList.toggle("is-active", active);
    if (active) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  });
}

function extractNavButtonLabel(button) {
  const spans = button.querySelectorAll("span");
  const label = spans.length > 1 ? spans[spans.length - 1].textContent : button.textContent;
  return (label || "").replace(/\s+/g, " ").trim();
}

function closeDrawer(shell) {
  shell.body.classList.remove(MOBILE_DRAWER_OPEN_CLASS);
  syncDrawerBackdrop(shell);
}

function openDrawer(shell) {
  shell.body.classList.add(MOBILE_DRAWER_OPEN_CLASS);
  syncDrawerBackdrop(shell);
}

function toggleDrawer(shell) {
  if (shell.body.classList.contains(MOBILE_DRAWER_OPEN_CLASS)) {
    closeDrawer(shell);
    return;
  }

  openDrawer(shell);
}

function syncDrawerBackdrop(shell) {
  if (!(shell.drawerBackdrop instanceof HTMLElement)) {
    return;
  }

  const isOpen = shell.body.classList.contains(MOBILE_DRAWER_OPEN_CLASS);
  shell.drawerBackdrop.hidden = !isOpen;
  shell.menuButton?.setAttribute("aria-expanded", String(isOpen));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
