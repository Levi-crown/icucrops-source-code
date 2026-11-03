const isMobileAdminLogin = /\/mobile_web\/administrator\//i.test(window.location.pathname);

window.ICuCropsAuth?.createLoginController?.({
  loginRole: isMobileAdminLogin ? "admin" : "user",
  showForgotPassword: isMobileAdminLogin,
  postLoginPaths: {
    admin: isMobileAdminLogin ? "./index.html" : "../administrator/index.html",
    user: isMobileAdminLogin ? "../user/index.html" : "./index.html",
  },
});
