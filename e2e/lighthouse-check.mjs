// Fails when a Lighthouse JSON report scores below the bar in any category.
// Usage: node lighthouse-check.mjs <report.json> [minScore=0.9]
import { readFileSync } from "node:fs";

const [, , reportPath, minArg] = process.argv;
if (!reportPath) {
  console.error("usage: node lighthouse-check.mjs <report.json> [minScore]");
  process.exit(2);
}
const min = Number(minArg || "0.9");
const report = JSON.parse(readFileSync(reportPath, "utf8"));
const categories = report.categories || {};
const wanted = ["performance", "accessibility", "best-practices", "seo"];
let failed = false;
for (const key of wanted) {
  const cat = categories[key];
  if (!cat) {
    console.log(`${key}: missing`);
    failed = true;
    continue;
  }
  const score = Number(cat.score);
  const ok = score >= min;
  console.log(`${ok ? "OK  " : "FAIL"} ${key}: ${Math.round(score * 100)}`);
  if (!ok) failed = true;
}
const cls = report.audits?.["cumulative-layout-shift"]?.numericValue;
if (cls !== undefined) {
  const ok = cls <= 0.1;
  console.log(`${ok ? "OK  " : "FAIL"} cumulative-layout-shift: ${cls.toFixed(3)}`);
  if (!ok) failed = true;
}
const consoleErrors = report.audits?.["errors-in-console"]?.score;
if (consoleErrors !== undefined && consoleErrors !== null) {
  const ok = consoleErrors === 1;
  console.log(`${ok ? "OK  " : "FAIL"} errors-in-console`);
  if (!ok) failed = true;
}
console.log(`\n${report.finalDisplayedUrl || report.requestedUrl}: ${failed ? "BELOW BAR" : "meets the bar"} (min ${min})`);
process.exit(failed ? 1 : 0);
