const test = require('node:test');
const assert = require('node:assert/strict');
const { APP_HOME, isTrustedUrl } = require('../security');

test('mobile portal uses HTTPS', () => assert.equal(isTrustedUrl(APP_HOME), true));
test('mobile rejects foreign, cleartext, and file URLs', () => {
  for (const url of [
    'http://learningmanagementsystem.pythonanywhere.com/',
    'https://learningmanagementsystem.pythonanywhere.com.evil.test/',
    'https://example.com/',
    'file:///tmp/secret',
    'javascript:alert(1)',
    'https://user:password@learningmanagementsystem.pythonanywhere.com/',
  ]) assert.equal(isTrustedUrl(url), false, url);
});
