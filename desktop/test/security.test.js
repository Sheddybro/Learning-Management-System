"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { APP_HOME, isTrustedUrl } = require("../security");

test("desktop loads the HTTPS school site", () => {
  assert.equal(isTrustedUrl(APP_HOME), true);
});

test("rejects insecure, other-domain, lookalike and credential URLs", () => {
  const bad = [
    "http://learningmanagementsystem.pythonanywhere.com/users/",
    "https://learningmanagementsystem.pythonanywhere.com.evil.test/",
    "https://evil.test/",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "https://user:pass@learningmanagementsystem.pythonanywhere.com/",
    "not-a-url",
  ];
  for (const url of bad) assert.equal(isTrustedUrl(url), false, url);
});

test("allows nested routes only on the real domain", () => {
  assert.equal(isTrustedUrl(`${APP_HOME}login/`), true);
  assert.equal(isTrustedUrl("https://learningmanagementsystem.pythonanywhere.com/academics/"), true);
});
