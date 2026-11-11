"use strict";

const APP_ORIGIN = "https://learningmanagementsystem.pythonanywhere.com";
const APP_HOME = `${APP_ORIGIN}/users/`;

function isTrustedUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.origin === APP_ORIGIN &&
      !url.username && !url.password;
  } catch {
    return false;
  }
}

module.exports = { APP_HOME, isTrustedUrl };
