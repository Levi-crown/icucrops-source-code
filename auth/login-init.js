(function initSharedLogin() {
  const config = window.ICuCropsLoginConfig || {};

  window.ICuCropsAuth?.createLoginController?.({
    defaultLoginRole: config.defaultLoginRole || "user",
    roleSelectionEnabled: config.roleSelectionEnabled !== false,
    showForgotPassword: config.showForgotPassword !== false,
    loginTitle: config.loginTitle || "Login to ICuCrops",
    loginCopy: config.loginCopy || "Access your farm dashboard and monitoring controls.",
    allowedForgotPasswordRoles: Array.isArray(config.allowedForgotPasswordRoles) && config.allowedForgotPasswordRoles.length
      ? config.allowedForgotPasswordRoles
      : ["admin"],
    postLoginPaths: config.postLoginPaths || {
      admin: "../administrator/index.html",
      user: "../user/index.html",
    },
  });
})();
