(function registerSettingsContactSection(global) {
  const registry = global.settingsSectionRegistry || (global.settingsSectionRegistry = {});

  const GUIDE_STEPS = [
    {
      icon: "dashboard",
      title: "Read the Dashboard First",
      summary: "The dashboard is the fastest place to understand current row status before opening detailed pages.",
      location: "Dashboard view",
      objective: "Get a quick picture of the farm before checking anything deeper.",
      actions: [
        "Open Dashboard and review active rows, warning indicators, and the live sensor graph.",
        "Check whether any row health or tank summary looks abnormal.",
        "Use the dashboard as your first stop every time you log in.",
      ],
      checks: [
        "Warnings usually mean that a row needs attention.",
        "Graph trends show whether readings are stable or changing.",
        "Tank summaries help explain irrigation-related changes.",
      ],
      tip: "A quick dashboard check saves time before jumping into detailed views.",
    },
    {
      icon: "history",
      title: "Use History to Review Events",
      summary: "History helps you understand what happened earlier instead of relying only on the latest reading.",
      location: "History view",
      objective: "Compare current conditions with earlier readings and activity.",
      actions: [
        "Open History to inspect recent readings, warnings, and recorded actions.",
        "Compare old values with the latest dashboard values to spot repeated problems.",
        "Review past activity after irrigation or major changes in row condition.",
      ],
      checks: [
        "Recurring warnings usually need closer monitoring.",
        "History confirms whether a reading shift is temporary or persistent.",
        "Recent records are useful after any farm action.",
      ],
      tip: "Use History whenever a current warning does not make sense at first glance.",
    },
    {
      icon: "sprout",
      title: "Follow Cultivation Progress",
      summary: "Cultivation shows the crop cycle, active row condition, and expected harvest progress.",
      location: "Cultivation view",
      objective: "Track whether the planted crop is progressing normally.",
      actions: [
        "Open Cultivation to review the active crop assigned to each row.",
        "Check the growth progress, row health, and expected harvest timing.",
        "Use cultivation status together with dashboard and history readings for better decisions.",
      ],
      checks: [
        "A healthy row should align with stable sensor readings.",
        "Low row health should be checked against recent history and graph trends.",
        "Harvest timing should match the actual crop stage.",
      ],
      tip: "Cultivation is easier to understand when you compare it with the dashboard graph.",
    },
    {
      icon: "bell",
      title: "Watch Notifications",
      summary: "Notifications give fast attention points when the system detects an important update or recent event.",
      location: "Notification panel",
      objective: "Notice important system events without scanning every page manually.",
      actions: [
        "Open the notification panel from the header when a new alert appears.",
        "Read recent updates before making changes to rows or cultivation decisions.",
        "Use notifications as a shortcut, then confirm details on the related page.",
      ],
      checks: [
        "Notifications are useful for recent changes, not full history.",
        "Important alerts should still be checked in History or Dashboard.",
        "Do not rely on alerts alone when the row condition is unclear.",
      ],
      tip: "Use notifications for quick awareness, then verify with the actual data page.",
    },
    {
      icon: "user",
      title: "Manage Your Own Settings",
      summary: "Settings lets you maintain your profile and reopen this tutorial whenever you need guidance.",
      location: "Settings modal",
      objective: "Keep your account details updated and know where to return for help.",
      actions: [
        "Open Settings to update your profile information and password when needed.",
        "Use the Guide section again if you need a walkthrough of the core pages.",
        "Review the About section if you need project context or system background.",
      ],
      checks: [
        "Profile changes should be confirmed after saving.",
        "Password updates should be kept private and current.",
        "The guide is meant to be revisited whenever you forget a workflow.",
      ],
      tip: "This tutorial works best as a quick refresher when you have not used the system in a while.",
    },
  ];

  function normalizeIndex(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed)) {
      return 0;
    }
    return Math.max(0, Math.min(GUIDE_STEPS.length - 1, parsed));
  }

  function currentGuideStep() {
    return GUIDE_STEPS[normalizeIndex(state.activeGuideStep)];
  }

  function guideStepButtonsTemplate(activeIndex) {
    return GUIDE_STEPS.map((step, index) => `
      <button
        class="guide-step-button ${index === activeIndex ? "is-active" : ""}"
        type="button"
        data-action="guide-jump-step"
        data-step="${index}"
      >
        <span class="guide-step-button__index">${String(index + 1).padStart(2, "0")}</span>
        <span class="guide-step-button__body">
          <strong>${escapeHtml(step.title)}</strong>
          <span>${escapeHtml(step.location)}</span>
        </span>
      </button>
    `).join("");
  }

  function guideListTemplate(items) {
    return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  }

  function guideHighlightsTemplate(step) {
    return `
      <div class="guide-highlight-grid">
        <article class="glass-card card guide-highlight-card">
          <p class="contact-card__eyebrow">Where to open</p>
          <h4 class="section-title">${escapeHtml(step.location)}</h4>
          <p class="section-copy">${escapeHtml(step.summary)}</p>
        </article>
        <article class="glass-card card guide-highlight-card">
          <p class="contact-card__eyebrow">Main goal</p>
          <h4 class="section-title">${escapeHtml(step.objective)}</h4>
          <p class="section-copy">${escapeHtml(step.tip)}</p>
        </article>
      </div>
    `;
  }

  function guideCardTemplate(activeIndex) {
    const step = currentGuideStep();
    const isFirst = activeIndex === 0;
    const isLast = activeIndex === GUIDE_STEPS.length - 1;
    return `
      <article class="glass-card card guide-card">
        <div class="guide-card__header">
          <div class="guide-card__title">
            <span class="spot-icon">${icon(step.icon)}</span>
            <div>
              <p class="contact-card__eyebrow">Step ${activeIndex + 1} of ${GUIDE_STEPS.length}</p>
              <h3 class="section-title">${escapeHtml(step.title)}</h3>
              <p class="section-copy">${escapeHtml(step.summary)}</p>
            </div>
          </div>
          <span class="chip">Full Tutorial</span>
        </div>

        ${guideHighlightsTemplate(step)}

        <div class="guide-card__body">
          <div class="guide-card__section">
            <p class="guide-card__section-title">What to do</p>
            <ul class="guide-card__list">
              ${guideListTemplate(step.actions)}
            </ul>
          </div>
          <div class="guide-card__section">
            <p class="guide-card__section-title">What to check</p>
            <ul class="guide-card__list guide-card__list--soft">
              ${guideListTemplate(step.checks)}
            </ul>
          </div>
        </div>

        <div class="guide-card__footer">
          <button class="button button--secondary" type="button" data-action="guide-prev-step" ${isFirst ? "disabled" : ""}>
            Back
          </button>
          <div class="guide-card__progress">
            <span>${escapeHtml(`Tutorial ${activeIndex + 1}/${GUIDE_STEPS.length}`)}</span>
            <div class="guide-card__progress-bar" aria-hidden="true">
              <span style="width: ${(((activeIndex + 1) / GUIDE_STEPS.length) * 100).toFixed(0)}%"></span>
            </div>
          </div>
          <button class="button button--primary" type="button" data-action="${isLast ? "guide-jump-step" : "guide-next-step"}" ${isLast ? 'data-step="0"' : ""}>
            ${isLast ? "Start Again" : "Next"}
          </button>
        </div>
      </article>
    `;
  }

  registry.guide = {
    path: "./settings-contact.html",
    render(template) {
      const activeIndex = normalizeIndex(state.activeGuideStep);
      const heroText = `Tutorial step ${activeIndex + 1} of ${GUIDE_STEPS.length} for using the ICuCrops user dashboard.`;
      return replaceTemplateTokens(template, {
        INFO_ICON: icon("info"),
        GUIDE_CHIPS: GUIDE_STEPS.map((step) => `<span class="chip">${escapeHtml(step.location)}</span>`).join(""),
        GUIDE_PROGRESS_TEXT: escapeHtml(heroText),
        GUIDE_STEP_BUTTONS: guideStepButtonsTemplate(activeIndex),
        GUIDE_ACTIVE_CARD: guideCardTemplate(activeIndex),
      });
    },
  };

  global.updateGuideStepView = function updateGuideStepView() {
    const guidePage = document.querySelector(".modal--settings .guide-page");
    const guideContent = guidePage?.querySelector(".guide-content");
    if (!(guidePage instanceof HTMLElement) || !(guideContent instanceof HTMLElement)) {
      return false;
    }

    const activeIndex = normalizeIndex(state.activeGuideStep);
    const stepButtons = Array.from(guidePage.querySelectorAll(".guide-step-button"));
    const currentActiveIndex = stepButtons.findIndex((button) => button.classList.contains("is-active"));
    if (currentActiveIndex === activeIndex) {
      return true;
    }
    const previousIndex = currentActiveIndex >= 0 ? currentActiveIndex : activeIndex;
    guidePage.dataset.activeGuideStep = String(activeIndex);

    stepButtons.forEach((button, index) => {
      const isActive = index === activeIndex;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-current", isActive ? "step" : "false");
    });

    guideContent.innerHTML = guideCardTemplate(activeIndex);
    const progressCopy = guidePage.querySelector(".guide-hero__progress");
    if (progressCopy) {
      progressCopy.textContent = `Tutorial step ${activeIndex + 1} of ${GUIDE_STEPS.length} for using the ICuCrops user dashboard.`;
    }

    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
    const offset = activeIndex >= previousIndex ? "0.45rem" : "-0.45rem";
    if (!reduceMotion && typeof guideContent.animate === "function") {
      guideContent.animate(
        [
          { opacity: 0.82, transform: `translateY(${offset})` },
          { opacity: 1, transform: "translateY(0)" },
        ],
        {
          duration: document.documentElement.classList.contains("pi-kiosk") ? 130 : 180,
          easing: "cubic-bezier(0.22, 1, 0.36, 1)",
        },
      );
    }

    return true;
  };

  global.normalizeGuideStep = normalizeIndex;
  global.settingsGuideTemplate = function settingsGuideTemplate() {
    return renderExternalTemplate("guide");
  };

  global.settingsContactTemplate = function settingsContactTemplate() {
    return renderExternalTemplate("guide");
  };
})(window);
