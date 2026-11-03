(function registerSettingsAboutSection(global) {
  const registry = global.settingsSectionRegistry || (global.settingsSectionRegistry = {});

  registry.about = {
    path: "./settings-about.html?v=20260703e",
    render(template) {
      return replaceTemplateTokens(template, {
        ABOUT_LOGO_PATH: "../assets/icucrops-logo-transparent.png",
        LOGO_PATH,
        SARATE_LOGO_PATH,
      });
    },
  };

  global.settingsAboutTemplate = function settingsAboutTemplate() {
    return renderExternalTemplate("about");
  };
})(window);
