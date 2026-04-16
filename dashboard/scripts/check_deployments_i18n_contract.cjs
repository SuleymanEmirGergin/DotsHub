const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readFile(relPath) {
  const filePath = path.join(__dirname, "..", relPath);
  return fs.readFileSync(filePath, "utf8");
}

function readJson(relPath) {
  return JSON.parse(readFile(relPath));
}

function getByPath(obj, dottedPath) {
  return dottedPath.split(".").reduce((acc, key) => {
    if (acc == null || typeof acc !== "object") return undefined;
    return acc[key];
  }, obj);
}

const deploymentsPageKeys = [
  "title",
  "healthLabel",
  "subtitle",
  "statsSummary",
  "onlyProblems",
  "all",
  "status",
  "severity",
  "problemBanner",
  "tableDeployed",
  "tableTitle",
  "tableStatus",
  "tableImpact",
  "tableGitSha",
  "untitled",
  "viewImpact",
  "noImpactReport",
  "noGitSha",
  "noRows",
  "error",
  "impactSeverityTitle",
  "statusApplied",
  "statusRolledBackPending",
  "statusRolledBack",
  "severityAll",
  "severityOk",
  "severityInfo",
  "severityWarning",
  "severityCritical",
];

const deploymentImpactKeys = [
  "title",
  "breadcrumb",
  "deploymentLabel",
  "backToDeployments",
  "noReport",
  "commentaryTitle",
  "findings",
  "recommendedActions",
  "sampleSize",
  "downRate",
  "avgConfidence",
  "avgQuestions",
  "last7Days",
  "severityOk",
  "severityInfo",
  "severityWarning",
  "severityCritical",
  "noteInsufficientData",
  "noteDownRateWorse",
  "noteDownRateBetter",
  "noteDownRateStable",
  "noteConfidenceDown",
  "noteConfidenceUp",
  "noteConfidenceStable",
  "noteQuestionsUp",
  "noteQuestionsFaster",
  "noteQuestionsStable",
  "actionWaitMoreFeedback",
  "actionCritical",
  "actionWarning",
  "actionOk",
  "actionSynonym",
  "actionQuestion",
];

function verifyDeploymentsPageSource() {
  const source = readFile(path.join("app", "admin", "deployments", "page.tsx"));

  assert.match(source, /cookies/);
  assert.match(source, /getText/);
  assert.match(source, /const locale = await getLocale\(\)/);
  assert.match(source, /const t = \(key: string\) => getText\(locale, key\)/);
  assert.match(source, /const localeTag = locale === "en" \? "en-US" : "tr-TR"/);

  for (const key of deploymentsPageKeys) {
    assert.match(source, new RegExp(`deploymentsPage\\.${key}`));
  }

  assert.doesNotMatch(source, /â†’|â€¢/);
}

function verifyImpactPageSource() {
  const source = readFile(path.join("app", "admin", "deployments", "[id]", "impact", "page.tsx"));

  assert.match(source, /cookies/);
  assert.match(source, /getText/);
  assert.match(source, /const locale = await getLocale\(\)/);
  assert.match(source, /const t = \(key: string\) => getText\(locale, key\)/);

  for (const key of deploymentImpactKeys) {
    assert.match(source, new RegExp(`deploymentImpact\\.${key}`));
  }

  assert.doesNotMatch(source, /â†’|â€¢/);
}

function verifyMessageCatalogs() {
  const en = readJson(path.join("messages", "en.json"));
  const tr = readJson(path.join("messages", "tr.json"));

  for (const locale of [
    { code: "en", messages: en },
    { code: "tr", messages: tr },
  ]) {
    for (const key of deploymentsPageKeys) {
      const value = getByPath(locale.messages, `deploymentsPage.${key}`);
      assert.equal(typeof value, "string", `${locale.code} missing deploymentsPage.${key}`);
      assert.notEqual(value.trim(), "", `${locale.code} empty deploymentsPage.${key}`);
    }

    for (const key of deploymentImpactKeys) {
      const value = getByPath(locale.messages, `deploymentImpact.${key}`);
      assert.equal(typeof value, "string", `${locale.code} missing deploymentImpact.${key}`);
      assert.notEqual(value.trim(), "", `${locale.code} empty deploymentImpact.${key}`);
    }
  }
}

function main() {
  verifyDeploymentsPageSource();
  verifyImpactPageSource();
  verifyMessageCatalogs();
  console.log("deployments_i18n_contract_check: PASS");
}

main();
