(function registerSettingsContactSection(global) {
  const registry = global.settingsSectionRegistry || (global.settingsSectionRegistry = {});

  const GUIDE_STEPS = [
    {
      icon: "dashboard",
      title: "Start at the Dashboard",
      summary: "Use the dashboard as your control room before opening any row, sensor, or irrigation page.",
      location: "Dashboard view",
      objective: "Confirm the current farm condition in one pass.",
      actions: [
        "Check the IoT row cards to see which rows are active and which rows show warnings.",
        "Read the Live Sensor Graph to compare moisture, temperature, humidity, pH, and soil nutrient trends.",
        "Review the cultivation graph, row health, and tank levels before you make adjustments.",
      ],
      checks: [
        "Rows with warning pills need attention first.",
        "Tank levels should be checked before running irrigation actions.",
        "The dashboard gives the fastest summary when you first log in.",
      ],
      tip: "Start here every session so decisions are based on the latest readings.",
    },
    {
      icon: "activity",
      title: "Inspect Sensor Readings",
      summary: "Open the Sensors page when you need row-by-row details instead of just the dashboard summary.",
      location: "Sensors view",
      objective: "Verify whether a row needs watering, nutrient adjustment, or closer monitoring.",
      actions: [
        "Open the Sensors page and inspect moisture, temperature, humidity, pH, and soil nutrients for each row.",
        "Use the sensor detail cards to compare actual readings against expected operating ranges.",
        "Focus on values that look unstable, unusually low, or outside the normal range.",
      ],
      checks: [
        "Low moisture usually needs irrigation review.",
        "Unusual pH or soil nutrient values can indicate nutrient balance issues.",
        "Repeated abnormal readings should be checked again in History.",
      ],
      tip: "Do not trigger irrigation immediately without checking if the sensor pattern is consistent.",
    },
    {
      icon: "droplets",
      title: "Run Irrigation Carefully",
      summary: "The irrigation page is where you apply water or nutrient actions after checking sensor and tank status.",
      location: "Irrigation view",
      objective: "Apply the correct irrigation mode using current readings, not guesses.",
      actions: [
        "Open Irrigation and confirm which row or irrigation channel you are about to control.",
        "Review the mode, schedule, or manual action before turning irrigation on.",
        "Check water and solution tank levels so the action will complete as expected.",
      ],
      checks: [
        "Manual irrigation should only be used after reviewing the latest row readings.",
        "Automatic settings must match the actual crop and row condition.",
        "After irrigation, return to dashboard or sensors to confirm the change in readings.",
      ],
      tip: "Treat irrigation as a response to data, not as the first step.",
    },
    {
      icon: "sprout",
      title: "Manage Cultivation Batches",
      summary: "Cultivation is where you start crop cycles, assign rows, and follow progress until harvest.",
      location: "Cultivation view",
      objective: "Keep each row tied to the correct crop, timeline, and expected condition.",
      actions: [
        "Create or review the active cultivation assigned to a row.",
        "Confirm planting date, expected harvest date, and row placement before saving.",
        "Use cultivation progress and health indicators to track whether the row is on schedule.",
      ],
      checks: [
        "A row should match the crop batch currently planted there.",
        "If row health drops, compare cultivation progress with sensor values.",
        "Harvest timing should always be checked against the active batch details.",
      ],
      tip: "Keep row assignment accurate so the dashboard and cultivation panels stay reliable.",
    },
    {
      icon: "history",
      title: "Review History and Alerts",
      summary: "Use History and notifications when you need to understand what happened earlier, not just what is happening now.",
      location: "History view and alerts",
      objective: "Trace warnings, irrigation actions, and reading changes over time.",
      actions: [
        "Open History to review recent readings, activity logs, and system changes.",
        "Compare current warnings with older readings to see if the issue is temporary or recurring.",
        "Check notifications for important backend updates or recent farm events.",
      ],
      checks: [
        "Recurring warnings usually need a root-cause check.",
        "History is useful after irrigation to verify whether conditions improved.",
        "Older records help confirm whether a row trend is stable or declining.",
      ],
      tip: "When a reading looks suspicious, verify the pattern in History before acting again.",
    },
    {
      icon: "users",
      title: "Maintain User Access",
      summary: "Admins should keep accounts, roles, and settings organized so the dashboard stays usable for the whole team.",
      location: "Manage Account and Settings",
      objective: "Keep the system secure and make sure the right users have the right access.",
      actions: [
        "Open Manage Account to review active users and administrator access.",
        "Add, remove, or update users only when role changes are actually required.",
        "Use Settings for profile updates and this tutorial whenever you need a refresher.",
      ],
      checks: [
        "Only trusted users should have administrator access.",
        "Account changes should be reviewed before deleting a user.",
        "Profile updates should be confirmed after saving.",
      ],
      tip: "Administrative cleanup prevents access issues and confusion later.",
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
      const heroText = `Tutorial step ${activeIndex + 1} of ${GUIDE_STEPS.length} for managing the ICuCrops admin dashboard.`;
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
      progressCopy.textContent = `Tutorial step ${activeIndex + 1} of ${GUIDE_STEPS.length} for managing the ICuCrops admin dashboard.`;
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
