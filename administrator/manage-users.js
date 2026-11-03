function addUserModalTemplate() {
  if (state.newUser.stage === "success") {
    return addUserSuccessModalTemplate();
  }

  if (state.newUser.stage === "otp") {
    return addUserOtpModalTemplate();
  }

  if (state.newUser.stage === "confirm") {
    return addUserPasswordConfirmModalTemplate();
  }

  return addUserFormModalTemplate();
}

function addUserFormModalTemplate() {
  const passwordsMismatch = hasNewUserPasswordMismatch();

  return `
    <div class="overlay overlay--center">
      <div class="modal modal--sm add-user-modal">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <p class="add-user-modal__eyebrow">Account Setup</p>
              <h3 class="section-title">Add New User</h3>
              <p class="section-copy">Create a real account that can log in to ICuCrops.</p>
            </div>
            <button class="icon-button" type="button" data-action="close-add-user">
              ${icon("close")}
            </button>
          </div>
        </div>

        <div class="modal__body page-stack add-user-modal__body add-user-modal__body--details">
          <article class="glass-card card add-user-step-card add-user-step-card--details">
            <div class="add-user-step-card__head">
              <div class="inline-copy add-user-step-card__copy">
                <div class="spot-icon">${icon("user-plus")}</div>
                <div>
                  <h4 class="section-title">Account Details</h4>
                  <p class="section-copy">Use a valid Gmail address to create the account.</p>
                </div>
              </div>
              <span class="pill pill--normal">Step 2 of 3</span>
            </div>

            <div class="add-user-step-card__scroll">
              ${addUserNoticeMarkup()}

              <div class="field-grid add-user-form-grid">
                <div class="field">
                  <label class="field__label" for="new-user-name">Name</label>
                  <input class="input" id="new-user-name" type="text" value="${escapeHtml(state.newUser.name)}" ${state.newUser.isSubmitting ? "disabled" : ""} />
                </div>
                <div class="field">
                  <label class="field__label" for="new-user-email">Email</label>
                  <input class="input" id="new-user-email" type="email" value="${escapeHtml(state.newUser.email)}" ${state.newUser.isSubmitting ? "disabled" : ""} />
                </div>
                <div class="field">
                  <label class="field__label" for="new-user-role">Role</label>
                  <select class="select" id="new-user-role" ${state.newUser.isSubmitting ? "disabled" : ""}>
                    <option value="user" ${state.newUser.role === "user" ? "selected" : ""}>User</option>
                    <option value="admin" ${state.newUser.role === "admin" ? "selected" : ""}>Administrator</option>
                  </select>
                </div>
                ${addUserPasswordFieldTemplate({
                  id: "new-user-password",
                  label: "Password",
                  value: state.newUser.password,
                  disabled: state.newUser.isSubmitting,
                })}
                ${addUserPasswordFieldTemplate({
                  id: "new-user-confirm-password",
                  label: "Confirm Password",
                  value: state.newUser.confirmPassword,
                  disabled: state.newUser.isSubmitting,
                })}
              </div>

              <p class="password-policy-alert add-user-step-card__note">
                ${escapeHtml(PASSWORD_POLICY_MESSAGE)}
              </p>

              ${
                passwordsMismatch
                  ? `
                    <p class="section-copy add-user-step-card__note add-user-step-card__note--error">
                      Passwords do not match yet. Please make sure both password fields are the same.
                    </p>
                  `
                  : ""
              }
            </div>
          </article>

          <div class="modal__actions add-user-modal__actions">
            <button class="button button--secondary button--full" type="button" data-action="close-add-user" ${state.newUser.isSubmitting ? "disabled" : ""}>
              Cancel
            </button>
            <button
              class="button button--primary button--full"
              type="button"
              data-action="submit-add-user"
              ${isNewUserDetailsIncomplete() || state.newUser.isSubmitting ? "disabled" : ""}
            >
              ${state.newUser.isSubmitting ? "Loading..." : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

// Add User opens here: the signed-in administrator's password comes first, as
// it does before a delete, and the form only follows once the server accepts
// it. The kiosk stays signed in on a panel anyone can reach, and a new
// administrator is a way in from anywhere. Built from the add-user dialog's
// own classes, so it follows both themes on desktop, phone and the 800x480
// panel without a new modal style.
function addUserPasswordConfirmModalTemplate() {
  const submitting = state.newUser.isSubmitting;
  return `
    <div class="overlay overlay--center overlay--dialog">
      <div class="modal modal--sm add-user-modal">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <p class="add-user-modal__eyebrow">Account Setup</p>
              <h3 class="section-title">Confirm with your password</h3>
              <p class="section-copy">Only a signed-in administrator can add an account.</p>
            </div>
            <button class="icon-button" type="button" data-action="close-add-user" ${submitting ? "disabled" : ""}>
              ${icon("close")}
            </button>
          </div>
        </div>

        <div class="modal__body page-stack add-user-modal__body">
          <article class="glass-card card add-user-step-card add-user-step-card--confirm">
            <div class="add-user-step-card__head">
              <div class="inline-copy add-user-step-card__copy">
                <div class="spot-icon">${icon("lock")}</div>
                <div>
                  <h4 class="section-title">Your Password</h4>
                  <p class="section-copy">
                    Enter the password of the administrator account you are signed in with to add a new account.
                  </p>
                </div>
              </div>
              <span class="pill pill--normal">Step 1 of 3</span>
            </div>

            ${adminPasswordFieldTemplate({
              id: "add-user-admin-password",
              value: state.newUser.adminPassword,
              disabled: submitting,
            })}
            ${adminPasswordErrorTemplate(state.newUser.adminPasswordError, "add-user-step-card__note")}
          </article>

          <div class="modal__actions add-user-modal__actions">
            <button class="button button--secondary button--full" type="button" data-action="close-add-user" ${submitting ? "disabled" : ""}>
              Cancel
            </button>
            <button
              class="button button--primary button--full"
              type="button"
              data-action="submit-add-user-admin-password"
              ${submitting || !state.newUser.adminPassword ? "disabled" : ""}
            >
              ${submitting ? "Checking..." : "Continue"}
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

// Back to the password card, empty, saying why.
function openAddUserPasswordConfirm(message = "") {
  state.newUser.stage = "confirm";
  state.newUser.adminPassword = "";
  state.newUser.adminPasswordError = message;
  state.newUser.notice = "";
  renderOverlays();
  focusAdminPasswordField("add-user-admin-password");
}

// Continue on the password card: the server checks it (and counts a wrong one
// toward the lockout) before the form is shown at all.
async function confirmAddUserAdminPassword() {
  const password = state.newUser.adminPassword;
  if (!password || state.newUser.isSubmitting) {
    return;
  }
  state.newUser.isSubmitting = true;
  state.newUser.adminPasswordError = "";
  renderOverlays();
  try {
    await window.ICuCropsAuth.requestJson("/api/users/confirm-admin-password", {
      method: "POST",
      body: { password },
    });
    state.newUser.isSubmitting = false;
    state.newUser.stage = "details";
    renderOverlays();
    document.getElementById("new-user-name")?.focus();
  } catch (error) {
    state.newUser.isSubmitting = false;
    openAddUserPasswordConfirm(adminPasswordRefusalMessage(error, "Unable to confirm your password."));
  }
}

// A refusal of the administrator's own password, as opposed to a problem with
// the new account's details or the email send.
function isAdminPasswordRefusal(error) {
  const code = String(error?.payload?.code || "");
  return (
    code === "ADMIN_PASSWORD_INCORRECT" ||
    code === "ADMIN_PASSWORD_REQUIRED" ||
    code === "ADMIN_LOGIN_LOCKED"
  );
}

function addUserOtpModalTemplate() {
  const otpInputs = state.newUser.otpCode
    .map(
      (digit, index) => `
        <input
          class="otp-input otp-input--glass"
          id="new-user-otp-${index}"
          type="text"
          inputmode="numeric"
          autocomplete="${index === 0 ? "one-time-code" : "off"}"
          maxlength="6"
          value="${escapeHtml(digit)}"
          ${state.newUser.isSubmitting ? "disabled" : ""}
        />
      `,
    )
    .join("");

  return `
    <div class="overlay overlay--center overlay--dialog">
      <div class="modal modal--sm add-user-modal">
        <div class="modal__header">
          <div class="card-head">
            <div>
              <p class="add-user-modal__eyebrow">Account Setup</p>
              <h3 class="section-title">Verify Gmail OTP</h3>
              <p class="section-copy">The account will only be created after the code is verified.</p>
            </div>
            <button class="icon-button" type="button" data-action="close-add-user" ${state.newUser.isSubmitting ? "disabled" : ""}>
              ${icon("close")}
            </button>
          </div>
        </div>

        <div class="modal__body page-stack add-user-modal__body">
          <article class="glass-card card add-user-step-card add-user-step-card--otp">
            <div class="add-user-step-card__head">
              <div class="inline-copy add-user-step-card__copy">
                <div class="spot-icon">${icon("mail")}</div>
                <div>
                  <h4 class="section-title">OTP Verification</h4>
                  <p class="section-copy">
                    Enter the 6-digit code sent to <strong>${escapeHtml(state.newUser.otpMaskedEmail || state.newUser.email)}</strong>.
                  </p>
                </div>
              </div>
              <span class="pill pill--normal">Step 3 of 3</span>
            </div>

            ${addUserNoticeMarkup()}

            <article class="glass-card card add-user-otp-card">
              <div class="password-otp-card__copy">
                <span class="spot-icon">${icon("shield")}</span>
                <div>
                  <h4 class="section-title">Verification Code</h4>
                  <p class="section-copy">Type all 6 digits below, then confirm to create the account.</p>
                </div>
              </div>
              <div class="otp-row otp-row--modal">
                ${otpInputs}
              </div>
            </article>

            <div class="add-user-otp-meta">
              <p class="section-copy">Need a fresh code?</p>
              <button class="button button--ghost add-user-otp-link" type="button" data-action="resend-add-user-otp" ${state.newUser.isSubmitting ? "disabled" : ""}>
                Resend OTP
              </button>
            </div>
          </article>

          <!-- Two buttons, not three. Cancel did exactly what the X in the
               header already does - abandon the whole thing - while Back is
               the one that keeps the name and email that were just typed.
               With three, the pair no longer fit on one row and "Verify &
               Create" was pushed onto a line of its own with dead space
               beside it. Dropping the duplicate puts the two real choices
               side by side and loses nothing: closing is still one click on
               the X. -->
          <div class="modal__actions add-user-modal__actions">
            <button class="button button--secondary button--full" type="button" data-action="back-add-user-details" ${state.newUser.isSubmitting ? "disabled" : ""}>
              Back
            </button>
            <button
              class="button button--primary button--full"
              type="button"
              data-action="submit-add-user-otp"
              ${isNewUserOtpIncomplete() || state.newUser.isSubmitting ? "disabled" : ""}
            >
              ${state.newUser.isSubmitting ? "Creating..." : "Verify & Create"}
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function addUserPasswordFieldTemplate({ id, label, value, disabled }) {
  return `
    <div class="field">
      <label class="field__label" for="${id}">${label}</label>
      <div class="login-input login-input--password add-user-password-field">
        <input
          class="input login-input__control--password"
          id="${id}"
          type="password"
          maxlength="64"
          autocomplete="new-password"
          value="${escapeHtml(value)}"
          ${disabled ? "disabled" : ""}
        />
        <button
          class="login-input__toggle"
          type="button"
          data-action="toggle-password-visibility"
          data-target="${id}"
          aria-label="Show password"
          ${disabled ? "disabled" : ""}
        >
          <span class="login-input__toggle-icon" data-password-icon aria-hidden="true">${passwordEyeIconMarkup(false)}</span>
        </button>
      </div>
    </div>
  `;
}

function addUserNoticeMarkup() {
  if (!state.newUser.notice) {
    return "";
  }

  return `
    <div class="center-banner">
      ${escapeHtml(state.newUser.notice)}
    </div>
  `;
}

async function addUser(isResend = false) {
  if (isNewUserDetailsIncomplete()) {
    updateAddUserButtonState();
    return;
  }
  if (!state.newUser.adminPassword) {
    openAddUserPasswordConfirm("Enter your password to confirm.");
    return;
  }

  state.newUser.isSubmitting = true;
  state.newUser.notice = "";
  state.newUser.adminPasswordError = "";
  renderOverlays();

  try {
    const response = await window.ICuCropsAuth.requestJson("/api/users/request-otp", {
      method: "POST",
      // Waits on the outbound email send (~10.5s on the Pi); see the
      // forgot-password request for why the 10s default is too short.
      timeoutMs: 45000,
      body: {
        name: state.newUser.name.trim(),
        email: state.newUser.email.trim().toLowerCase(),
        role: state.newUser.role,
        password: state.newUser.password,
        confirmPassword: state.newUser.confirmPassword,
        adminPassword: state.newUser.adminPassword,
      },
    });

    state.newUser.stage = "otp";
    state.newUser.isSubmitting = false;
    state.newUser.notice = String(
      response.message ||
        `${isResend ? "A new OTP was sent." : "OTP sent successfully."} Check the Gmail address you entered.`,
    );
    state.newUser.otpChallengeId = String(response.challengeId || "");
    state.newUser.otpMaskedEmail = String(response.maskedEmail || state.newUser.email.trim().toLowerCase());
    state.newUser.otpExpiresAt = String(response.expiresAt || "");
    state.newUser.otpCode = initialOtpCode();
    renderOverlays();
    focusNewUserOtpInput();
  } catch (error) {
    state.newUser.isSubmitting = false;
    if (isAdminPasswordRefusal(error)) {
      // Back to the password card, which says why; the details are kept.
      openAddUserPasswordConfirm(adminPasswordRefusalMessage(error, "Unable to confirm your password."));
      return;
    }
    state.newUser.notice = extractRequestMessage(error, "Unable to send the OTP right now.");
    renderOverlays();
  }
}

async function verifyAddUserOtp() {
  if (!state.newUser.otpChallengeId || isNewUserOtpIncomplete()) {
    updateAddUserButtonState();
    return;
  }

  state.newUser.isSubmitting = true;
  state.newUser.notice = "";
  renderOverlays();

  try {
    const response = await window.ICuCropsAuth.requestJson("/api/users/verify-otp", {
      method: "POST",
      // Creating the account hashes its password (310k iterations).
      timeoutMs: 30000,
      body: {
        challengeId: state.newUser.otpChallengeId,
        otp: state.newUser.otpCode.join(""),
      },
    });

    if (Array.isArray(response.users) && typeof mapUserAccounts === "function") {
      state.users = mapUserAccounts(response.users);
    }

    state.newUser.stage = "success";
    state.newUser.isSubmitting = false;
    state.newUser.adminPassword = "";
    state.newUser.successMessage = String(
      response.message || `${state.newUser.name.trim()} was added successfully and can now log in.`,
    );
    if (typeof refreshNotifications === "function") {
      await refreshNotifications({ render: false });
    }
    renderHeader();
    renderPage();
    renderOverlays();
    pushNotification("success", state.newUser.successMessage);
  } catch (error) {
    state.newUser.isSubmitting = false;
    state.newUser.notice = extractRequestMessage(error, "Unable to verify the OTP right now.");
    state.newUser.otpCode = initialOtpCode();
    renderOverlays();
    focusNewUserOtpInput();
  }
}

function returnToAddUserDetails() {
  state.newUser.stage = "details";
  state.newUser.notice = "";
  state.newUser.otpCode = initialOtpCode();
  state.newUser.otpChallengeId = "";
  state.newUser.otpMaskedEmail = "";
  state.newUser.otpExpiresAt = "";
  renderOverlays();
  document.getElementById("new-user-name")?.focus();
}

function focusNewUserOtpInput(index = 0) {
  const firstOtpInput = document.getElementById(`new-user-otp-${index}`);
  if (firstOtpInput instanceof HTMLInputElement) {
    firstOtpInput.focus();
    firstOtpInput.select();
  }
}

function handleNewUserOtpInput(target) {
  const index = Number(target.id.split("-")[3]);
  const digits = target.value.replace(/\D/g, "");

  if (!digits) {
    // Backspace on the Pi panel. Its on-screen keyboard sends only "input",
    // never keydown, so handleKeydown's Backspace handling never runs there.
    //
    // A box that held a digit is cleared and keeps the caret. A box that was
    // already empty clears the one before it and moves there. Stepping back
    // straight after clearing -- what this used to do -- spent the first
    // press on an empty box only moving, and left the caret on a box that
    // still had its digit, so every press after that cleared one box off
    // from the one the farmer was looking at.
    const wasEmpty = !state.newUser.otpCode[index];
    state.newUser.otpCode[index] = "";
    target.value = "";
    if (wasEmpty && index > 0) {
      state.newUser.otpCode[index - 1] = "";
      const previous = document.getElementById(`new-user-otp-${index - 1}`);
      if (previous instanceof HTMLInputElement) {
        previous.value = "";
        previous.focus();
      }
    }
    updateAddUserButtonState();
    return;
  }

  const availableSlots = state.newUser.otpCode.length - index;
  const nextDigits = digits.slice(0, availableSlots).split("");
  nextDigits.forEach((digit, offset) => {
    const otpIndex = index + offset;
    state.newUser.otpCode[otpIndex] = digit;
    const otpInput = document.getElementById(`new-user-otp-${otpIndex}`);
    if (otpInput instanceof HTMLInputElement) {
      otpInput.value = digit;
    }
  });

  const lastIndex = index + nextDigits.length - 1;
  const nextEmptyIndex = state.newUser.otpCode.findIndex((digit, otpIndex) => otpIndex >= index && !digit);
  updateAddUserButtonState();

  if (nextEmptyIndex !== -1) {
    focusNewUserOtpInput(nextEmptyIndex);
    return;
  }

  if (lastIndex < state.newUser.otpCode.length - 1) {
    focusNewUserOtpInput(lastIndex + 1);
  }
}

async function deleteUser(id) {
  const user = state.users.find((item) => item.id === id);
  if (!user || user.role === "admin") {
    return;
  }

  openDeleteUserConfirm(id);
}

function getDeleteUserTarget() {
  return state.users.find((item) => item.id === state.deleteUserTargetId) || null;
}

function deleteUserConfirmModalTemplate() {
  const user = getDeleteUserTarget();
  if (!user) {
    return "";
  }

  return `
    <div class="overlay overlay--center overlay--dialog">
      <div
        class="modal modal--sm delete-user-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-user-confirm-title"
        aria-describedby="delete-user-confirm-copy"
      >
        ${state.deleteUserStep === "password" ? `
        <div class="modal__body delete-user-confirm-modal__body">
          <span class="delete-user-confirm-modal__icon" aria-hidden="true">${icon("lock")}</span>
          <div class="delete-user-confirm-modal__copy">
            <p class="delete-user-confirm-modal__eyebrow">Manage Account</p>
            <h3 class="section-title delete-user-confirm-modal__title" id="delete-user-confirm-title">Confirm with your password</h3>
            <p class="section-copy delete-user-confirm-modal__text" id="delete-user-confirm-copy">
              Enter the password of the administrator account you are signed in with to delete <strong>${escapeHtml(user.name)}</strong>.
            </p>
          </div>
          ${adminPasswordFieldTemplate({
            id: "delete-user-password",
            value: state.deleteUserPassword,
            disabled: state.deleteUserSubmitting,
          })}
          ${adminPasswordErrorTemplate(state.deleteUserPasswordError, "delete-user-confirm-modal__email")}
          <div class="modal__actions delete-user-confirm-modal__actions">
            <button
              class="button button--secondary button--full"
              type="button"
              data-action="close-delete-user-confirm"
              ${state.deleteUserSubmitting ? "disabled" : ""}
            >
              Cancel
            </button>
            <button
              class="button button--danger button--full"
              type="button"
              data-action="submit-delete-user-password"
              ${state.deleteUserSubmitting || !state.deleteUserPassword ? "disabled" : ""}
            >
              ${icon("trash")}
              ${state.deleteUserSubmitting ? "Deleting..." : "Delete Account"}
            </button>
          </div>
        </div>
        ` : `
        <div class="modal__body delete-user-confirm-modal__body">
          <span class="delete-user-confirm-modal__icon" aria-hidden="true">${icon("trash")}</span>
          <div class="delete-user-confirm-modal__copy">
            <p class="delete-user-confirm-modal__eyebrow">Manage Account</p>
            <h3 class="section-title delete-user-confirm-modal__title" id="delete-user-confirm-title">Delete user account?</h3>
            <p class="section-copy delete-user-confirm-modal__text" id="delete-user-confirm-copy">
              This will permanently remove <strong>${escapeHtml(user.name)}</strong> from ICuCrops. This action cannot be undone.
            </p>
            <p class="section-copy delete-user-confirm-modal__email">${escapeHtml(user.email)}</p>
          </div>
          <div class="modal__actions delete-user-confirm-modal__actions">
            <button
              class="button button--secondary button--full"
              type="button"
              data-action="close-delete-user-confirm"
              ${state.deleteUserSubmitting ? "disabled" : ""}
            >
              Cancel
            </button>
            <button
              class="button button--danger button--full"
              type="button"
              data-action="confirm-delete-user"
              ${state.deleteUserSubmitting ? "disabled" : ""}
            >
              ${icon("trash")}
              <span>${state.deleteUserSubmitting ? "Deleting..." : "Confirm Delete"}</span>
            </button>
          </div>
        </div>
        `}
      </div>
    </div>
  `;
}

// The first card only asks; the delete itself waits for the password card.
function confirmDeleteUserDeletion() {
  const user = getDeleteUserTarget();
  if (!user || user.role === "admin" || state.deleteUserSubmitting) {
    return;
  }
  state.deleteUserStep = "password";
  state.deleteUserPassword = "";
  state.deleteUserPasswordError = "";
  renderOverlays();
  focusAdminPasswordField("delete-user-password");
}

async function submitDeleteUserPassword() {
  const user = getDeleteUserTarget();
  const password = state.deleteUserPassword;
  if (!user || user.role === "admin" || !password || state.deleteUserSubmitting) {
    return;
  }

  state.deleteUserSubmitting = true;
  state.deleteUserPasswordError = "";
  renderOverlays();

  try {
    const response = await window.ICuCropsAuth.requestJson(`/api/users/${encodeURIComponent(user.id)}`, {
      method: "DELETE",
      body: { password },
    });

    if (Array.isArray(response.users) && typeof mapUserAccounts === "function") {
      state.users = mapUserAccounts(response.users);
    } else {
      state.users = state.users.filter((item) => item.id !== user.id);
    }
    if (typeof refreshNotifications === "function") {
      await refreshNotifications({ render: false });
    }
    closeDeleteUserConfirm(false);
    renderHeader();
    renderPage();
    renderOverlays();
    pushNotification("warning", String(response.message || `${user.name} was removed from user accounts.`));
  } catch (error) {
    state.deleteUserSubmitting = false;
    state.deleteUserPassword = "";
    state.deleteUserPasswordError = adminPasswordRefusalMessage(
      error,
      "Unable to delete the user account right now.",
    );
    renderOverlays();
    focusAdminPasswordField("delete-user-password");
  }
}

function updateAddUserButtonState() {
  const addButton = document.querySelector('[data-action="submit-add-user"]');
  if (addButton) {
    addButton.disabled = isNewUserDetailsIncomplete() || state.newUser.isSubmitting;
  }

  const verifyButton = document.querySelector('[data-action="submit-add-user-otp"]');
  if (verifyButton) {
    verifyButton.disabled = isNewUserOtpIncomplete() || state.newUser.isSubmitting;
  }
}

function isNewUserDetailsIncomplete() {
  return (
    !state.newUser.name.trim() ||
    !state.newUser.email.trim() ||
    !state.newUser.password ||
    !state.newUser.confirmPassword ||
    !isValidNewPassword(state.newUser.password) ||
    hasNewUserPasswordMismatch()
  );
}

function isNewUserOtpIncomplete() {
  return state.newUser.otpCode.some((digit) => !digit);
}

function hasNewUserPasswordMismatch() {
  return Boolean(
    state.newUser.password &&
    state.newUser.confirmPassword &&
    state.newUser.password !== state.newUser.confirmPassword
  );
}

function addUserSuccessModalTemplate() {
  return `
    <div class="overlay overlay--center">
      <div class="modal modal--sm add-user-success-modal">
        <div class="modal__body add-user-success-modal__body">
          <article class="glass-card card add-user-success-card">
            <button class="icon-button add-user-success-card__close" type="button" data-action="close-add-user" aria-label="Close success message">
              ${icon("close")}
            </button>
            <div class="add-user-success-card__icon">${icon("check-circle")}</div>
            <span class="pill pill--normal add-user-success-card__pill">Account Ready</span>
            <div class="page-stack add-user-success-card__copy">
              <h3 class="section-title">User Added Successfully</h3>
              <p class="section-copy">${escapeHtml(state.newUser.successMessage || `${state.newUser.name.trim()} was added successfully.`)}</p>
              <p class="section-copy">This account is already saved in the database and can log in now.</p>
            </div>
          </article>
        </div>
      </div>
    </div>
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
