(function registerForgotPasswordFlow(global) {
  const templateBasePath = normalizeTemplateBasePath(
    global.ICuCropsLoginConfig?.forgotPasswordTemplateBasePath,
  );

  const templatePaths = {
    "forgot-email": `${templateBasePath}forgot-password-email.html`,
    "forgot-otp": `${templateBasePath}forgot-password-otp.html`,
    verified: `${templateBasePath}forgot-password-verified.html`,
    "reset-password": `${templateBasePath}forgot-password-reset.html`,
  };

  const viewContent = {
    "forgot-email": {
      title: "Forgot Password",
      copy: "Enter your Gmail address to receive your 6-digit verification code.",
    },
    "forgot-otp": {
      title: "OTP Verification",
      copy: "Type the 6-digit OTP sent to your email to continue resetting your password.",
    },
    verified: {
      title: "Verified",
      copy: "Your email has been verified successfully. You can now create a new password.",
    },
    "reset-password": {
      title: "Create New Password",
      copy: "Set your new password below. After saving, you will return to the login form.",
    },
  };

  const templateCache = new Map();

  global.forgotPasswordFlow = {
    preload,
    isForgotPasswordView,
    getViewContent,
    render,
    handleAction,
    handleSubmit,
    handleInput,
    handleKeyDown,
    handleOtpPaste,
  };

  function isForgotPasswordView(view) {
    return Object.prototype.hasOwnProperty.call(templatePaths, view);
  }

  function normalizeTemplateBasePath(value) {
    const basePath = String(value || "./").trim() || "./";
    return basePath.endsWith("/") ? basePath : `${basePath}/`;
  }

  function getViewContent(view) {
    return viewContent[view] || viewContent["forgot-email"];
  }

  async function preload() {
    await Promise.all(
      Object.entries(templatePaths).map(async ([view, path]) => {
        const template = await readTemplate(path);
        if (template) {
          templateCache.set(view, template);
        }
      }),
    );
  }

  function render(state, helpers) {
    const template = getTemplate(state.view);
    if (!template) {
      return `
        <div class="login-feedback" role="status">
          Unable to load the forgot password form right now.
        </div>
      `;
    }

    switch (state.view) {
      case "forgot-email":
        return replaceTokens(template, {
          NOTICE: helpers.getNoticeMarkup(state.notice),
          RECOVERY_EMAIL: helpers.escapeHtml(state.recoveryEmail),
        });
      case "forgot-otp":
        return replaceTokens(template, {
          NOTICE: helpers.getNoticeMarkup(state.notice),
          RECOVERY_EMAIL: helpers.escapeHtml(state.recoveryEmail),
          OTP_DISABLED: state.isSubmitting ? "disabled" : "",
          // Disabled only while a request is actually in flight. A cooldown
          // would be the backend's to impose; the request endpoint already
          // rate-limits, and hiding the button on a timer is what leaves
          // someone with an expired code and nothing to press.
          RESEND_DISABLED: state.isSubmitting ? "disabled" : "",
          RESEND_LABEL: state.isSubmitting ? "Sending..." : "Resend code",
          OTP_INPUTS: state.otp
            .map(
              (digit, index) => `
                <input
                  class="otp-input"
                  id="forgot-otp-${index}"
                  type="text"
                  inputmode="numeric"
                  maxlength="1"
                  value="${helpers.escapeHtml(digit)}"
                  ${state.isSubmitting ? "disabled" : ""}
                />
              `,
            )
            .join(""),
        });
      case "verified":
        return replaceTokens(template, {
          NOTICE: helpers.getNoticeMarkup(state.notice),
          RECOVERY_EMAIL: helpers.escapeHtml(state.recoveryEmail),
        });
      case "reset-password":
        return replaceTokens(template, {
          NOTICE: helpers.getNoticeMarkup(state.notice),
          NEW_PASSWORD: helpers.escapeHtml(state.newPassword),
          CONFIRM_PASSWORD: helpers.escapeHtml(state.confirmPassword),
        });
      default:
        return "";
    }
  }

  function handleAction(action, state, helpers) {
    switch (action) {
      case "open-forgot-password":
        if (state.view !== "login") {
          return false;
        }
        state.recoveryEmail = "";
        state.loginPassword = "";
        state.notice = "";
        state.challengeId = "";
        state.maskedEmail = "";
        state.expiresAt = "";
        state.otp = ["", "", "", "", "", ""];
        state.newPassword = "";
        state.confirmPassword = "";
        state.view = "forgot-email";
        helpers.render();
        return true;
      case "back-to-login":
        restoreLoginView(state, helpers);
        return true;
      case "back-to-email":
        state.notice = "";
        state.view = "forgot-email";
        helpers.render();
        return true;
      case "resend-otp":
        if (state.view !== "forgot-otp" || state.isSubmitting) {
          return true;
        }
        void resendOtp(state, helpers);
        return true;
      case "back-to-otp":
        state.notice = "";
        state.view = "forgot-otp";
        helpers.render();
        return true;
      case "back-to-verified":
        state.notice = "";
        state.view = "verified";
        helpers.render();
        return true;
      case "go-to-reset-password":
        state.notice = "";
        state.view = "reset-password";
        helpers.render();
        return true;
      default:
        return false;
    }
  }

  function handleSubmit(formId, state, helpers) {
    switch (formId) {
      case "forgot-email-form":
        void submitRecoveryEmail(state, helpers);
        return true;
      case "forgot-otp-form":
        void submitOtp(state, helpers);
        return true;
      case "reset-password-form":
        void submitResetPassword(state, helpers);
        return true;
      default:
        return false;
    }
  }

  function handleInput(target, state) {
    switch (target.id) {
      case "recovery-email":
        state.recoveryEmail = target.value;
        return true;
      case "reset-password":
        state.newPassword = target.value;
        return true;
      case "confirm-password":
        state.confirmPassword = target.value;
        return true;
      default:
        break;
    }

    if (/^forgot-otp-\d$/.test(target.id)) {
      const index = Number(target.id.split("-")[2]);
      const raw = target.value.replace(/\D/g, "");
      const value = raw.slice(0, 1);
      const wasEmpty = !state.otp[index];
      target.value = value;
      state.otp[index] = value;

      // A whole code arriving in one box -- autofill, or a phone keyboard
      // that pastes on suggestion tap -- used to keep one digit and drop the
      // rest silently.
      if (raw.length > 1) {
        for (let offset = 1; offset < raw.length && index + offset < state.otp.length; offset += 1) {
          const box = document.getElementById(`forgot-otp-${index + offset}`);
          state.otp[index + offset] = raw[offset];
          if (box) {
            box.value = raw[offset];
          }
        }
        const landing = Math.min(index + raw.length - 1, state.otp.length - 1);
        document.getElementById(`forgot-otp-${landing}`)?.focus();
        return true;
      }

      if (value && index < state.otp.length - 1) {
        const next = document.getElementById(`forgot-otp-${index + 1}`);
        next?.focus();
      } else if (!value && wasEmpty && index > 0) {
        // Backspace on an already-empty box: clear the one before it and move
        // there -- the same step handleKeyDown takes for a physical keyboard.
        //
        // This is the path the Raspberry Pi kiosk actually takes: the on-screen
        // keyboard writes straight to .value and dispatches "input", never a
        // keydown, so the Backspace handling below never runs there. A box
        // that held a digit is only cleared and keeps the caret. Stepping back
        // straight after clearing, as this used to, spent the first press on
        // an empty box only moving and parked the caret on a box that still
        // had its digit, so each press cleared one box off from the expected.
        const previous = document.getElementById(`forgot-otp-${index - 1}`);
        state.otp[index - 1] = "";
        if (previous) {
          previous.value = "";
          previous.focus();
        }
      }
      return true;
    }

    return false;
  }

  function handleKeyDown(event, state) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !/^forgot-otp-\d$/.test(target.id)) {
      return false;
    }

    const index = Number(target.id.split("-")[2]);

    if (event.key === "Backspace") {
      // Take the whole step here rather than letting the browser delete and
      // then moving on the NEXT press. Clearing six boxes used to need eleven
      // presses -- delete, move, delete, move -- which reads as the field
      // losing keystrokes.
      event.preventDefault();
      if (target.value) {
        target.value = "";
        state.otp[index] = "";
      } else if (index > 0) {
        const previous = document.getElementById(`forgot-otp-${index - 1}`);
        if (previous) {
          previous.value = "";
          state.otp[index - 1] = "";
          previous.focus();
        }
      }
      return true;
    }

    if (event.key === "Delete") {
      event.preventDefault();
      target.value = "";
      state.otp[index] = "";
      return true;
    }

    if (event.key === "ArrowLeft" && index > 0) {
      event.preventDefault();
      document.getElementById(`forgot-otp-${index - 1}`)?.focus();
      return true;
    }

    if (event.key === "ArrowRight" && index < state.otp.length - 1) {
      event.preventDefault();
      document.getElementById(`forgot-otp-${index + 1}`)?.focus();
      return true;
    }

    return true;
  }

  // Pasting the code from the email put all six digits in the first box, where
  // maxlength kept one and dropped the rest.
  function handleOtpPaste(event, state, helpers) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !/^forgot-otp-\d$/.test(target.id)) {
      return false;
    }

    const text = String(
      event.clipboardData?.getData("text") || "",
    ).replace(/\D/g, "");
    if (!text) {
      return false;
    }

    event.preventDefault();
    const start = Number(target.id.split("-")[2]);
    for (let offset = 0; offset < text.length && start + offset < state.otp.length; offset += 1) {
      const index = start + offset;
      state.otp[index] = text[offset];
      const box = document.getElementById(`forgot-otp-${index}`);
      if (box) {
        box.value = text[offset];
      }
    }

    const landing = Math.min(start + text.length, state.otp.length - 1);
    document.getElementById(`forgot-otp-${landing}`)?.focus();
    return true;
  }

  async function submitRecoveryEmail(state, helpers) {
    const email = state.recoveryEmail.trim().toLowerCase();

    if (!email) {
      state.notice = "Please enter your Gmail address first.";
      helpers.render();
      return;
    }

    if (!/^[a-z0-9._%+-]+@gmail\.com$/i.test(email)) {
      state.notice = "Use a valid Gmail address first.";
      helpers.render();
      return;
    }

    state.isSubmitting = true;
    state.notice = "Sending OTP. Please wait...";
    state.challengeId = "";
    state.maskedEmail = "";
    state.expiresAt = "";
    state.otp = ["", "", "", "", "", ""];
    state.view = "forgot-otp";
    helpers.render();

    try {
      const response = await global.ICuCropsAuth.requestJson("/api/auth/forgot-password/request-otp", {
        method: "POST",
        // This request waits on an outbound SMTP send, which measured ~10.5s
        // on the Pi -- just past the 10s default and so it aborted every
        // time with "The server took too long to respond" even though the
        // mail was on its way. Delivery, not the network, sets the floor here.
        timeoutMs: 45000,
        body: {
          email,
        },
      });

      state.recoveryEmail = email;
      state.challengeId = String(response.challengeId || "");
      state.maskedEmail = String(response.maskedEmail || "");
      state.expiresAt = String(response.expiresAt || "");
      state.otp = ["", "", "", "", "", ""];
      state.notice = String(response.message || "OTP sent successfully.");
    } catch (error) {
      state.view = "forgot-email";
      state.notice = extractRequestMessage(
        error,
        "Backend is not reachable. Start the Python server first.",
      );
    } finally {
      state.isSubmitting = false;
      helpers.render();
      if (state.view === "forgot-otp" && state.challengeId) {
        global.requestAnimationFrame(() => {
          document.getElementById("forgot-otp-0")?.focus();
        });
      }
    }
  }

  // Request another code without leaving the OTP step.
  //
  // submitRecoveryEmail() cannot be reused as-is: on failure it drops back to
  // the email view, which on a resend would throw away the step the person is
  // standing on and the address they already confirmed.
  async function resendOtp(state, helpers) {
    const email = String(state.recoveryEmail || "").trim().toLowerCase();
    if (!email) {
      // Nothing to resend to -- the only honest move is back to the email step.
      state.notice = "Enter your Gmail address again to receive a new code.";
      state.view = "forgot-email";
      helpers.render();
      return;
    }

    state.isSubmitting = true;
    state.notice = "Sending a new code. Please wait...";
    // The old challenge is dead the moment a new one is issued, so clear the
    // boxes rather than leaving digits that can only ever be rejected.
    state.otp = ["", "", "", "", "", ""];
    helpers.render();

    try {
      const response = await global.ICuCropsAuth.requestJson("/api/auth/forgot-password/request-otp", {
        method: "POST",
        // Same reasoning as the first send: this waits on an outbound SMTP
        // send, measured around 10.5s on the Pi.
        timeoutMs: 45000,
        body: {
          email,
        },
      });

      state.challengeId = String(response.challengeId || "");
      state.maskedEmail = String(response.maskedEmail || "");
      state.expiresAt = String(response.expiresAt || "");
      state.notice = String(response.message || "A new OTP has been sent.");
    } catch (error) {
      // Stay on the OTP step. The previous code may still be valid -- a failed
      // resend is not a reason to discard a challenge that could still work.
      state.notice = extractRequestMessage(
        error,
        "Could not send a new code. Check the connection and try again.",
      );
    } finally {
      state.isSubmitting = false;
      helpers.render();
      global.requestAnimationFrame(() => {
        document.getElementById("forgot-otp-0")?.focus();
      });
    }
  }

  async function submitOtp(state, helpers) {
    if (!state.challengeId) {
      state.notice = "Start the forgot password process again to receive a fresh OTP.";
      state.view = "forgot-email";
      helpers.render();
      return;
    }

    if (state.otp.some((digit) => !digit)) {
      state.notice = "Please complete the 6-digit OTP.";
      helpers.render();
      return;
    }

    state.isSubmitting = true;
    state.notice = "";
    helpers.render();

    try {
      const response = await global.ICuCropsAuth.requestJson("/api/auth/forgot-password/verify-otp", {
        method: "POST",
        // Reads the challenge back out of Firebase. Measured 1.3s-5.5s on the
        // Pi, so the 10s default was only ever two slow lookups from aborting.
        timeoutMs: global.ICuCropsAuth.AUTH_REQUEST_TIMEOUT_MS,
        body: {
          challengeId: state.challengeId,
          otp: state.otp.join(""),
        },
      });

      state.maskedEmail = String(response.maskedEmail || state.maskedEmail || "");
      state.notice = String(response.message || "OTP verified successfully.");
      state.view = "verified";
    } catch (error) {
      state.notice = extractRequestMessage(error, "OTP verification failed.");
    } finally {
      state.isSubmitting = false;
      helpers.render();
    }
  }

  async function submitResetPassword(state, helpers) {
    if (!state.challengeId) {
      state.notice = "Start the forgot password process again first.";
      state.view = "forgot-email";
      helpers.render();
      return;
    }

    if (!state.newPassword || !state.confirmPassword) {
      state.notice = "Please enter and confirm your new password.";
      helpers.render();
      return;
    }

    if (state.newPassword !== state.confirmPassword) {
      state.notice = "Passwords do not match.";
      helpers.render();
      return;
    }

    if (!global.ICuCropsAuth?.isValidNewPassword?.(state.newPassword)) {
      state.notice = global.ICuCropsAuth?.PASSWORD_POLICY_MESSAGE
        || "Password must be 8–64 characters and include uppercase, lowercase, number, and special character.";
      helpers.render();
      return;
    }

    state.isSubmitting = true;
    state.notice = "";
    helpers.render();

    try {
      const response = await global.ICuCropsAuth.requestJson("/api/auth/forgot-password/reset", {
        method: "POST",
        // Writes the new password hash to Firebase and clears the challenge, so
        // it is the step where a timeout is most expensive: give up early and
        // the password may already have changed without the user being told.
        timeoutMs: global.ICuCropsAuth.AUTH_REQUEST_TIMEOUT_MS,
        body: {
          challengeId: state.challengeId,
          otp: state.otp.join(""),
          newPassword: state.newPassword,
          confirmPassword: state.confirmPassword,
        },
      });

      state.loginEmail = "";
      state.loginPassword = "";
      state.notice = String(response.message || "Password updated successfully. You can log in now.");
      restoreLoginView(state, helpers, true);
    } catch (error) {
      state.notice = extractRequestMessage(error, "Password reset failed.");
      state.isSubmitting = false;
      helpers.render();
    }
  }

  function restoreLoginView(state, helpers, keepNotice = false) {
    state.view = "login";
    state.loginEmail = "";
    state.loginPassword = "";
    state.recoveryEmail = "";
    state.otp = ["", "", "", "", "", ""];
    state.newPassword = "";
    state.confirmPassword = "";
    state.challengeId = "";
    state.maskedEmail = "";
    state.expiresAt = "";
    state.isSubmitting = false;
    if (!keepNotice) {
      state.notice = "";
    }
    helpers.render();
  }

  function extractRequestMessage(error, fallback) {
    if (error && typeof error === "object" && "payload" in error && error.payload?.message) {
      return String(error.payload.message);
    }

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

  async function readTemplate(path) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (response.ok) {
        return await response.text();
      }
    } catch (error) {
      const fallback = readTemplateSync(path);
      if (fallback) {
        return fallback;
      }
      console.warn(`Unable to fetch forgot password template: ${path}`, error);
    }

    return "";
  }

  function getTemplate(view) {
    const cached = templateCache.get(view);
    if (cached) {
      return cached;
    }

    const template = readTemplateSync(templatePaths[view]);
    if (template) {
      templateCache.set(view, template);
    }
    return template;
  }

  function readTemplateSync(path) {
    try {
      const request = new XMLHttpRequest();
      request.open("GET", path, false);
      request.send(null);

      if ((request.status >= 200 && request.status < 300) || request.status === 0) {
        return request.responseText;
      }
    } catch (error) {
      console.warn(`Unable to synchronously load forgot password template: ${path}`, error);
    }

    return "";
  }

  function replaceTokens(template, tokens) {
    return Object.entries(tokens).reduce(
      (markup, [token, value]) => markup.replaceAll(`{{${token}}}`, value ?? ""),
      template,
    );
  }
})(window);
