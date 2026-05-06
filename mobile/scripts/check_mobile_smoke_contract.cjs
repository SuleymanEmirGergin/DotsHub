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

// ─── Health-tourism (Session 17 pivot) ─────────────────────────────

function verifyHtRouteRegistered() {
  // The /quote route must be exposed in the root Stack — without this
  // the IntroScreen's `router.push("/quote")` falls through silently.
  const source = read(path.join("app", "_layout.tsx"));
  assert.match(source, /name="quote"/);
}

function verifyHtIntroEntry() {
  // IntroScreen must surface the HT entry point. We assert the
  // navigation call rather than the button label so a copy change
  // doesn't accidentally break this gate.
  const source = read(path.join("src", "screens", "IntroScreen.tsx"));
  assert.match(source, /router\.push\("\/quote"\)/);
  assert.match(source, /healthTourismCta/);
}

function verifyHtClientContract() {
  // The three POST endpoints + idempotency header are the public
  // contract with the backend's health_tourism routes. A missing path
  // here would surface as 404 only at runtime.
  const source = read(path.join("src", "api", "quoteClient.ts"));
  assert.match(source, /\/v1\/quote\b/);
  assert.match(source, /\/v1\/quote\/itinerary/);
  assert.match(source, /\/v1\/quote\/lead/);
  assert.match(source, /Idempotency-Key/);
  assert.match(source, /USE_MOCK/);
}

function verifyHtEnvelopeUnion() {
  // Triage Envelope union must include QUOTE/ITINERARY so a screen
  // that reads `env.type` doesn't widen to `string`. Backend already
  // emits these — type drift is silent at runtime, loud here.
  const source = read(path.join("src", "state", "types.ts"));
  assert.match(source, /"QUOTE"/);
  assert.match(source, /"ITINERARY"/);
}

function verifyHtCatalogShapes() {
  // proceduresCatalog mirrors backend procedures.json — the contract
  // is the existence of a couple of well-known ids the backend always
  // ships. If they go missing the browse screen will silently skip
  // a category.
  const source = read(path.join("src", "data", "proceduresCatalog.ts"));
  assert.match(source, /fue_hair_transplant/);
  assert.match(source, /dental_veneers/);
  assert.match(source, /lasik/);
}

function main() {
  verifyLayoutLocaleBootstrapping();
  verifyI18nPersistenceAndRTL();
  verifyHistoryFetchContract();
  verifySummaryClientContract();
  verifyResultScreenSummaryCalls();
  verifyPushRegistrationFallback();
  verifyPushClientContract();
  verifyHtRouteRegistered();
  verifyHtIntroEntry();
  verifyHtClientContract();
  verifyHtEnvelopeUnion();
  verifyHtCatalogShapes();
  console.log("mobile_smoke_contract_check: PASS");
}

main();
