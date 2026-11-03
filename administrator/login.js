window.ICuCropsAuth?.createLoginController?.({
  loginRole: "admin",
  showForgotPassword: true,
  postLoginPaths: {
    admin: "./index.html",
    user: "../user/index.html",
  },
});
