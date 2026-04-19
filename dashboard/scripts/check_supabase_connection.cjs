/**
 * One-off script to verify Supabase connection using dashboard/.env.local.
 * Usage: node scripts/check_supabase_connection.cjs
 * Output: OK or ERROR: <message> (no secrets printed)
 */
const fs = require("node:fs");
const path = require("node:path");

const envPath = path.join(__dirname, "..", ".env.local");
if (!fs.existsSync(envPath)) {
  console.log("ERROR: .env.local not found");
  process.exit(1);
}
const content = fs.readFileSync(envPath, "utf8");
content.split(/\r?\n/).forEach((line) => {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#")) return;
  const idx = trimmed.indexOf("=");
  if (idx <= 0) return;
  const k = trimmed.slice(0, idx).trim();
  let v = trimmed.slice(idx + 1).trim();
  if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'")))
    v = v.slice(1, -1);
  process.env[k] = v;
});

const url = process.env.SUPABASE_URL;
const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!url || !key) {
  console.log("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing in .env.local");
  process.exit(1);
}
if (url.includes("xxxx")) {
  console.log("ERROR: SUPABASE_URL is still placeholder (xxxx)");
  process.exit(1);
}

const { createClient } = require("@supabase/supabase-js");
const sb = createClient(url, key, { auth: { persistSession: false } });

sb.from("triage_sessions")
  .select("id")
  .limit(1)
  .maybeSingle()
  .then(({ data: _data, error }) => {
    if (error) {
      console.log("ERROR:", error.message);
      process.exit(1);
    }
    console.log("OK");
  })
  .catch((e) => {
    console.log("ERROR:", e.message);
    process.exit(1);
  });
