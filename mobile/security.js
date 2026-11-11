"use strict";

const APP_ORIGIN = "https://learningmanagementsystem.pythonanywhere.com";
const APP_HOME = `${APP_ORIGIN}/users/`;

function isTrustedUrl(value) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && parsed.origin === APP_ORIGIN &&
      !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

module.exports = { APP_HOME, isTrustedUrl };
