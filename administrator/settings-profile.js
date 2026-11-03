(function registerSettingsProfileSection(global) {
  const registry = global.settingsSectionRegistry || (global.settingsSectionRegistry = {});

  registry.profile = {
    path: "./settings-profile.html",
    render(template) {
      return replaceTemplateTokens(template, {
        // The photo itself, not just the initial: drawing the letter here made
        // every re-render swap the <img> out and back in, which blinked.
        PROFILE_INITIAL: profileAvatarMarkup(state.profileName),
        CAMERA_ICON: icon("camera"),
        PHOTO_BUTTON_LABEL: state.profilePhotoDataUrl ? "Change Photo" : "Upload Photo",
        PROFILE_NAME: escapeHtml(state.profileName),
        PROFILE_ROLE: escapeHtml(DEFAULT_PROFILE_ROLE),
        PROFILE_ROLE_BADGE: `<span class="role-badge">${icon("shield", "icon")}${escapeHtml(DEFAULT_PROFILE_ROLE)}</span>`,
        LOCK_ICON: icon("lock"),
        // Rendered here rather than left to syncPasswordToggleButtons:
        // this section is drawn into the settings overlay, which only
        // syncs its toggles for the Add New User modal, so the eye slot
        // stayed empty and the button was invisible on every shell.
        PASSWORD_EYE_ICON: passwordEyeIconMarkup(false),
        CURRENT_PASSWORD: escapeHtml(state.currentPassword),
        NEW_PASSWORD: escapeHtml(state.newPassword),
        CHANGE_PASSWORD_DISABLED: !state.currentPassword || !isValidNewPassword(state.newPassword) ? "disabled" : "",
      });
    },
  };

  global.settingsProfileTemplate = function settingsProfileTemplate() {
    return renderExternalTemplate("profile");
  };
})(window);
