const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function read(relPath) {
  const full = path.join(__dirname, "..", relPath);
  return fs.readFileSync(full, "utf8");
}

function verifyLayoutLocaleBootstrapping() {
  const source = read(path.join("app", "_layout.tsx"));
  assert.match(source, /getDefaultLocale/);
  assert.match(source, /<I18nProvider defaultLocale=\{initialLocale\}>/);
}

function verifyI18nPersistenceAndRTL() {
  const source = read(path.join("i18n", "I18nProvider.tsx"));
  assert.match(source, /setStoredLocale/);
  assert.match(source, /const isRTL = locale === "ar"/);
  assert.match(source, /RTL_TEXT_STYLE/);
}

function verifyHistoryFetchContract() {
  const source = read(path.join("src", "screens", "HistoryScreen.tsx"));
  assert.match(source, /\/v1\/triage\/history\?limit=50/);
  assert.match(source, /"x-device-id"/);
  assert.match(source, /getDeviceId/);
}

function verifySummaryClientContract() {
  const source = read(path.join("src", "api", "summaryClient.ts"));
  assert.match(source, /\/send-summary/);
  assert.match(source, /\/export-summary/);
  assert.match(source, /Content-Type": "application\/json/);
}

function verifyResultScreenSummaryCalls() {
  const source = read(path.join("src", "screens", "ResultScreen.tsx"));
  assert.match(source, /sendSummaryEmail/);
  assert.match(source, /exportSummary/);
  assert.match(source, /result\.sendSummaryEmail/);
}

function verifyPushRegistrationFallback() {
  const source = read(path.join("src", "hooks", "usePushRegistration.ts"));
  assert.match(source, /loadExpoNotifications/);
  assert.match(source, /!notifications\?\.requestPermissionsAsync \|\| !notifications\.getExpoPushTokenAsync/);
  assert.match(source, /registerPushToken/);
  assert.match(source, /unregisterPushToken/);
}

function verifyPushClientContract() {
  const source = read(path.join("src", "api", "pushClient.ts"));
  assert.match(source, /\/v1\/triage\/push-token/);
  assert.match(source, /method:\s*"POST"/);
  assert.match(source, /method:\s*"DELETE"/);
  assert.match(source, /device_id/);
}

function main() {
  verifyLayoutLocaleBootstrapping();
  verifyI18nPersistenceAndRTL();
  verifyHistoryFetchContract();
  verifySummaryClientContract();
  verifyResultScreenSummaryCalls();
  verifyPushRegistrationFallback();
  verifyPushClientContract();
  console.log("mobile_smoke_contract_check: PASS");
}

main();
