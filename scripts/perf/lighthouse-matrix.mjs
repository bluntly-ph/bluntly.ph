#!/usr/bin/env node
/**
 * Lighthouse matrix — repeatable lab measurements for every representative
 * route, on mobile and desktop, N runs each, median + range.
 *
 *   node scripts/perf/lighthouse-matrix.mjs                              # production, 3 runs, both
 *   node scripts/perf/lighthouse-matrix.mjs --base http://127.0.0.1:3100 --label candidate
 *   node scripts/perf/lighthouse-matrix.mjs --form-factor mobile --runs 5 --only /,/search
 *   node scripts/perf/lighthouse-matrix.mjs --assert                     # exit 1 on an `error` budget
 *
 * WHY NOT A SINGLE RUN. One Lighthouse navigation is one sample of a noisy
 * process: the network, the host CPU and the server all vary between runs, and
 * the owner's question ("is it Vercel, or the page?") cannot be answered from a
 * sample of one. Every value in the summary is the median of N cold-cache runs
 * with its min–max beside it, and the representative report kept on disk is
 * the run Lighthouse's own `computeMedianRun` picks (closest to median FCP and
 * TTI), not the best one.
 *
 * WHY NOT LHCI. `@lhci/cli` 0.15 bundles Lighthouse 12.6; Lighthouse 13 moved
 * the performance diagnostics onto the shared Performance Insights (LCP
 * breakdown, document latency, render blocking…) that this audit needs to
 * attribute time. So this drives Lighthouse 13 directly through its Node API,
 * which is what LHCI itself does, and keeps LHCI's shape: collect N, pick the
 * median, assert against a budget file.
 *
 * CONDITIONS, recorded in every summary so two runs can be compared honestly:
 *   mobile   Lighthouse default: Moto G Power emulation, simulated slow 4G
 *            (150 ms RTT, 1.6 Mbps down), 4x CPU slowdown
 *   desktop  Lighthouse desktop config: 1350x940, simulated dense 4G
 *            (40 ms RTT, 10 Mbps), no CPU slowdown
 *   cache    cold — a fresh Chrome profile for every run
 *   host     Lighthouse's benchmarkIndex and free memory at the start of each
 *            run, because a loaded laptop inflates TBT and JS execution
 *
 * WHAT IT IS NOT. Lab data. It does not say what real users experience (that
 * is CrUX/RUM, and a lab LCP is not a p75), and TBT is a responsiveness proxy,
 * not INP. The summary labels every number as lab.
 *
 * READ-ONLY: GET navigations of public pages. Nothing is clicked, submitted or
 * followed; `/r/` affiliate redirects are never requested.
 *
 * Output (gitignored): .perf/lighthouse/<label>-<timestamp>/
 *   summary.json, summary.md       medians, ranges, budget verdicts, conditions
 *   runs/<route>-<ff>-<n>.json     the extracted numbers of every run
 *   median/<route>-<ff>.json.gz    the full report of the median run
 */

import { execSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { gzipSync } from "node:zlib";

import * as chromeLauncher from "chrome-launcher";
import lighthouse, { desktopConfig } from "lighthouse";
import { computeMedianRun } from "lighthouse/core/lib/median-run.js";

const HERE = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const ROOT = path.resolve(HERE, "..", "..");

// ---------------------------------------------------------------- arguments
function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  if (i === -1) return fallback;
  const next = process.argv[i + 1];
  return next === undefined || next.startsWith("--") ? true : next;
}

const BASE = String(arg("base", "https://www.bluntly.ph")).replace(/\/$/, "");
const RUNS = Number(arg("runs", 3));
const FORM_FACTORS = String(arg("form-factor", "both")) === "both"
  ? ["mobile", "desktop"]
  : [String(arg("form-factor"))];
const ONLY = arg("only", null);
const ASSERT = arg("assert", false) === true;
const LOCAL = /^https?:\/\/(127\.0\.0\.1|localhost)/.test(BASE);
const LABEL = String(arg("label", LOCAL ? "candidate" : "production"));
const STAMP = new Date().toISOString().replace(/[:.]/g, "-");
const OUT = path.resolve(String(arg("out", path.join(ROOT, ".perf", "lighthouse", `${LABEL}-${STAMP}`))));

const routesFile = JSON.parse(readFileSync(path.join(HERE, "routes.json"), "utf8"));
const budget = JSON.parse(readFileSync(path.join(HERE, "budget.json"), "utf8"));
const ROUTES = routesFile.routes.filter(
  (r) => !ONLY || String(ONLY).split(",").includes(r.path),
);

// ---------------------------------------------------------------- what is being measured
function commitOf() {
  if (arg("sha", null)) return String(arg("sha"));
  if (!LOCAL) return "unknown (production: pass --sha from the deployment record)";
  try {
    return execSync("git rev-parse HEAD", { cwd: ROOT }).toString().trim();
  } catch {
    return "unknown";
  }
}

async function chromePath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  // The Playwright Chromium the e2e suite already installs: one browser build for both.
  const { chromium } = await import("@playwright/test");
  return chromium.executablePath();
}

// ---------------------------------------------------------------- extraction
const num = (lhr, id) => lhr.audits[id]?.numericValue ?? null;
const kb = (bytes) => (bytes == null ? null : Math.round(bytes / 102.4) / 10);

function transfer(lhr) {
  const items = lhr.audits["resource-summary"]?.details?.items ?? [];
  const by = Object.fromEntries(items.map((i) => [i.resourceType, i]));
  return {
    "total-transfer-kb": kb(by.total?.transferSize),
    "script-transfer-kb": kb(by.script?.transferSize),
    "stylesheet-transfer-kb": kb(by.stylesheet?.transferSize),
    "font-transfer-kb": kb(by.font?.transferSize),
    "image-transfer-kb": kb(by.image?.transferSize),
    "document-transfer-kb": kb(by.document?.transferSize),
    "third-party-transfer-kb": kb(by["third-party"]?.transferSize ?? 0),
    requests: by.total?.requestCount ?? null,
    "script-requests": by.script?.requestCount ?? null,
  };
}

/** The LCP insight's element and phase split — where the LCP time actually went. */
function lcpBreakdown(lhr) {
  const details = lhr.audits["lcp-breakdown-insight"]?.details;
  const out = { element: null, phases: {} };
  for (const item of details?.items ?? []) {
    if (item.type === "node") out.element = item.snippet ?? item.nodeLabel ?? null;
    if (item.type === "table") {
      for (const row of item.items ?? []) {
        if (row.label && typeof row.duration === "number") out.phases[row.label] = Math.round(row.duration);
      }
    }
  }
  if (!out.element) {
    const node = lhr.audits["largest-contentful-paint-element"]?.details?.items?.[0]?.items?.[0]?.node;
    out.element = node?.snippet ?? null;
  }
  return out;
}

function mainThread(lhr) {
  const groups = Object.fromEntries(
    (lhr.audits["mainthread-work-breakdown"]?.details?.items ?? []).map((i) => [i.group, Math.round(i.duration)]),
  );
  const scripts = (lhr.audits["bootup-time"]?.details?.items ?? [])
    .slice(0, 5)
    .map((i) => ({ url: String(i.url).replace(BASE, ""), total: Math.round(i.total), scripting: Math.round(i.scripting) }));
  const longTasks = lhr.audits["long-tasks"]?.details?.items ?? [];
  return {
    "mainthread-ms": Math.round(num(lhr, "mainthread-work-breakdown") ?? 0),
    "js-execution-ms": Math.round(num(lhr, "bootup-time") ?? 0),
    groups,
    topScripts: scripts,
    "long-tasks": longTasks.length,
    "longest-task-ms": Math.round(Math.max(0, ...longTasks.map((t) => t.duration))),
  };
}

function insightSummary(lhr) {
  const ids = [
    "document-latency-insight", "render-blocking-insight", "lcp-discovery-insight",
    "network-dependency-tree-insight", "image-delivery-insight", "font-display-insight",
    "cache-insight", "third-parties-insight", "dom-size-insight", "forced-reflow-insight",
    "duplicated-javascript-insight", "legacy-javascript-insight", "unused-javascript",
  ];
  const out = {};
  for (const id of ids) {
    const a = lhr.audits[id];
    if (!a) continue;
    out[id] = {
      score: a.score,
      display: a.displayValue ?? null,
      savingsMs: a.metricSavings ?? null,
      wastedKb: kb(a.details?.overallSavingsBytes ?? null),
    };
  }
  return out;
}

function extract(lhr, run) {
  const score = (id) => lhr.categories[id]?.score ?? null;
  return {
    run,
    finalUrl: lhr.finalDisplayedUrl,
    fetchTime: lhr.fetchTime,
    runtimeError: lhr.runtimeError?.code ?? null,
    runWarnings: lhr.runWarnings ?? [],
    scores: {
      performance: score("performance"),
      accessibility: score("accessibility"),
      "best-practices": score("best-practices"),
      seo: score("seo"),
      "agentic-browsing": score("agentic-browsing"),
    },
    metrics: {
      "first-contentful-paint": num(lhr, "first-contentful-paint"),
      "largest-contentful-paint": num(lhr, "largest-contentful-paint"),
      "cumulative-layout-shift": num(lhr, "cumulative-layout-shift"),
      "total-blocking-time": num(lhr, "total-blocking-time"),
      "speed-index": num(lhr, "speed-index"),
      interactive: num(lhr, "interactive"),
      // Observed, not simulated: the real document TTFB from this host.
      "server-response-time": num(lhr, "server-response-time"),
      "network-rtt": num(lhr, "network-rtt"),
    },
    lcp: lcpBreakdown(lhr),
    transfer: transfer(lhr),
    mainThread: mainThread(lhr),
    insights: insightSummary(lhr),
    failedAudits: Object.values(lhr.audits)
      .filter((a) => a.score === 0 && ["binary", "numeric", "metricSavings"].includes(a.scoreDisplayMode))
      .map((a) => a.id),
    environment: {
      benchmarkIndex: lhr.environment?.benchmarkIndex ?? null,
      hostUserAgent: lhr.environment?.hostUserAgent ?? null,
      lighthouseVersion: lhr.lighthouseVersion,
      throttling: lhr.configSettings.throttling,
      throttlingMethod: lhr.configSettings.throttlingMethod,
      formFactor: lhr.configSettings.formFactor,
      screen: lhr.configSettings.screenEmulation,
    },
  };
}

// ---------------------------------------------------------------- statistics
function median(values) {
  const v = values.filter((x) => typeof x === "number" && Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return null;
  const mid = Math.floor(v.length / 2);
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
}
const range = (values) => {
  const v = values.filter((x) => typeof x === "number" && Number.isFinite(x));
  return v.length ? [Math.min(...v), Math.max(...v)] : null;
};

function aggregate(runs) {
  const pick = (f) => runs.map(f);
  const block = (keys, getter) =>
    Object.fromEntries(keys.map((k) => [k, { median: median(pick((r) => getter(r)[k])), range: range(pick((r) => getter(r)[k])) }]));
  return {
    scores: block(Object.keys(runs[0].scores), (r) => r.scores),
    metrics: block(Object.keys(runs[0].metrics), (r) => r.metrics),
    transfer: block(Object.keys(runs[0].transfer), (r) => r.transfer),
    mainThread: block(["mainthread-ms", "js-execution-ms", "long-tasks", "longest-task-ms"], (r) => r.mainThread),
    benchmarkIndex: { median: median(pick((r) => r.environment.benchmarkIndex)), range: range(pick((r) => r.environment.benchmarkIndex)) },
  };
}

function checkBudget(agg) {
  const verdicts = [];
  for (const [id, rule] of Object.entries(budget.categories)) {
    const v = agg.scores[id]?.median;
    if (v != null && v < rule.min) verdicts.push({ id, value: v, limit: `>= ${rule.min}`, severity: rule.severity });
  }
  for (const [id, rule] of Object.entries(budget.metrics)) {
    const v = agg.metrics[id]?.median;
    if (v != null && v > rule.max) verdicts.push({ id, value: Math.round(v * 1000) / 1000, limit: `<= ${rule.max}`, severity: rule.severity });
  }
  for (const [id, rule] of Object.entries(budget.resources)) {
    const v = agg.transfer[id]?.median;
    if (v != null && v > rule.max) verdicts.push({ id, value: v, limit: `<= ${rule.max}`, severity: rule.severity });
  }
  return verdicts;
}

// ---------------------------------------------------------------- run
const slug = (p) => (p === "/" ? "home" : p.replace(/^\//, "").replace(/[^a-z0-9]+/gi, "_")).slice(0, 60);

async function preflight(url) {
  try {
    const res = await fetch(url, { redirect: "manual" });
    return res.status;
  } catch (e) {
    return `error: ${e.message}`;
  }
}

/**
 * Profiles that could not be removed straight after their run. Chrome's
 * helper processes can hold a profile for seconds after the browser exits, and
 * on 2026-09-17 the per-run removal had quietly left 258 profiles in %TEMP%
 * and filled the disk. They are retried once the whole matrix has finished.
 */
const leftoverProfiles = new Set();

function removeProfile(profile) {
  try {
    rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  } catch {
    /* retried at the end */
  }
  if (existsSync(profile)) leftoverProfiles.add(profile);
  else leftoverProfiles.delete(profile);
}

async function sweepLeftoverProfiles() {
  for (let attempt = 0; attempt < 5 && leftoverProfiles.size > 0; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    for (const profile of [...leftoverProfiles]) removeProfile(profile);
  }
  for (const profile of leftoverProfiles) {
    console.log(`  WARNING: temp profile not removed, delete by hand: ${profile}`);
  }
}

async function measure(url, formFactor, executable) {
  // A new profile every launch: cold HTTP cache, no service worker, no extensions.
  const profile = mkdtempSync(path.join(os.tmpdir(), "bluntly-lh-"));
  const chrome = await chromeLauncher.launch({
    chromePath: executable,
    userDataDir: profile,
    chromeFlags: ["--headless=new", "--no-first-run", "--disable-extensions", "--no-default-browser-check"],
  });
  try {
    const flags = { port: chrome.port, output: "json", logLevel: "error" };
    const config = formFactor === "desktop" ? desktopConfig : undefined;
    const result = await lighthouse(url, flags, config);
    return result.lhr;
  } finally {
    // On Windows Chrome still holds its profile for a moment after exit, and
    // chrome-launcher's own cleanup throws EPERM — which, from a `finally`,
    // would discard a report that completed. Kill, then remove with retries.
    try {
      await chrome.kill();
    } catch {
      /* the process is gone; only the profile removal failed */
    }
    removeProfile(profile);
  }
}

async function main() {
  mkdirSync(path.join(OUT, "runs"), { recursive: true });
  mkdirSync(path.join(OUT, "median"), { recursive: true });
  const executable = await chromePath();
  const meta = {
    label: LABEL,
    base: BASE,
    commit: commitOf(),
    startedAt: new Date().toISOString(),
    runsPerRoute: RUNS,
    formFactors: FORM_FACTORS,
    node: process.version,
    host: { platform: `${os.platform()} ${os.release()}`, cpus: os.cpus().length, cpuModel: os.cpus()[0]?.model, totalMemMb: Math.round(os.totalmem() / 1048576) },
    chrome: executable,
    cache: "cold (fresh profile per run)",
    evidence: "LAB (Lighthouse). Not field/CrUX, not RUM.",
  };
  writeFileSync(path.join(OUT, "meta.json"), JSON.stringify(meta, null, 2));
  console.log(`lighthouse matrix → ${BASE} (${LABEL}, ${meta.commit})\n  out ${OUT}`);

  const summary = [];
  for (const route of ROUTES) {
    const url = `${BASE}${route.path}`;
    const status = await preflight(url);
    if (status !== 200) {
      console.log(`SKIP ${route.path}: preflight ${status}`);
      summary.push({ ...route, url, status, skipped: true });
      continue;
    }
    for (const formFactor of FORM_FACTORS) {
      const lhrs = [];
      const runs = [];
      for (let n = 1; n <= RUNS; n += 1) {
        const file = path.join(OUT, "runs", `${slug(route.path)}-${formFactor}-${n}.json`);
        const freeMemMb = Math.round(os.freemem() / 1048576);
        try {
          const lhr = await measure(url, formFactor, executable);
          const row = { ...extract(lhr, n), freeMemMbAtStart: freeMemMb };
          writeFileSync(file, JSON.stringify(row, null, 2));
          if (!lhr.runtimeError) lhrs.push(lhr);
          runs.push(row);
          const m = row.metrics;
          console.log(
            `${route.path} ${formFactor} #${n}: perf ${row.scores.performance} ` +
              `LCP ${Math.round(m["largest-contentful-paint"])}ms TBT ${Math.round(m["total-blocking-time"])}ms ` +
              `CLS ${m["cumulative-layout-shift"]?.toFixed(3)} TTFB ${Math.round(m["server-response-time"])}ms ` +
              `bench ${row.environment.benchmarkIndex} free ${freeMemMb}MB`,
          );
        } catch (e) {
          console.log(`${route.path} ${formFactor} #${n}: FAILED ${e.message}`);
          runs.push({ run: n, error: e.message, freeMemMbAtStart: freeMemMb });
        }
      }
      const good = runs.filter((r) => !r.error && !r.runtimeError);
      if (!good.length) {
        summary.push({ ...route, url, formFactor, status, error: "no valid runs" });
        continue;
      }
      const agg = aggregate(good);
      const medianLhr = lhrs.length ? computeMedianRun(lhrs) : null;
      if (medianLhr) {
        writeFileSync(path.join(OUT, "median", `${slug(route.path)}-${formFactor}.json.gz`), gzipSync(JSON.stringify(medianLhr)));
      }
      const medianRow = medianLhr ? good.find((r) => r.fetchTime === medianLhr.fetchTime) : good[0];
      summary.push({
        ...route,
        url,
        formFactor,
        status,
        validRuns: good.length,
        aggregate: agg,
        medianRun: medianRow?.run ?? null,
        lcpElement: medianRow?.lcp?.element ?? null,
        lcpPhases: medianRow?.lcp?.phases ?? null,
        topScripts: medianRow?.mainThread?.topScripts ?? [],
        mainThreadGroups: medianRow?.mainThread?.groups ?? {},
        insights: medianRow?.insights ?? {},
        failedAudits: medianRow?.failedAudits ?? [],
        budget: checkBudget(agg),
      });
      writeFileSync(path.join(OUT, "summary.json"), JSON.stringify({ meta, summary }, null, 2));
    }
  }

  await sweepLeftoverProfiles();
  meta.finishedAt = new Date().toISOString();
  writeFileSync(path.join(OUT, "summary.json"), JSON.stringify({ meta, summary }, null, 2));
  writeFileSync(path.join(OUT, "summary.md"), markdown(meta, summary));
  console.log(`\n${markdown(meta, summary)}`);

  const errors = summary.flatMap((s) => (s.budget ?? []).filter((b) => b.severity === "error").map((b) => `${s.path} ${s.formFactor} ${b.id}`));
  if (ASSERT && errors.length) {
    console.error(`\nbudget errors:\n  ${errors.join("\n  ")}`);
    process.exit(1);
  }
}

function markdown(meta, summary) {
  const fmt = (x, d = 0) => (x == null ? "—" : Number(x).toFixed(d));
  const cell = (b, d = 0, scale = 1) =>
    b?.median == null ? "—" : `${fmt(b.median * scale, d)} (${fmt(b.range[0] * scale, d)}–${fmt(b.range[1] * scale, d)})`;
  const lines = [
    `# Lighthouse matrix — ${meta.label}`,
    "",
    `- base: ${meta.base}`,
    `- commit: ${meta.commit}`,
    `- started: ${meta.startedAt}${meta.finishedAt ? ` · finished: ${meta.finishedAt}` : ""}`,
    `- runs per route and form factor: ${meta.runsPerRoute}, cold cache, median (min–max)`,
    `- evidence: ${meta.evidence}`,
    "",
    "| route | ff | perf | a11y | bp | seo | LCP ms | CLS | TBT ms | FCP ms | TTFB ms | JS KB | total KB | JS exec ms | bench | budget |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
  ];
  for (const s of summary) {
    if (s.skipped || s.error) {
      lines.push(`| ${s.path} | ${s.formFactor ?? "—"} | ${s.error ?? `skipped (${s.status})`} |||||||||||||`);
      continue;
    }
    const a = s.aggregate;
    lines.push(
      `| ${s.path.length > 32 ? `${s.path.slice(0, 30)}…` : s.path} | ${s.formFactor} | ${cell(a.scores.performance, 0, 100)} | ${fmt(a.scores.accessibility.median * 100)} | ${fmt(a.scores["best-practices"].median * 100)} | ${fmt(a.scores.seo.median * 100)} | ` +
        `${cell(a.metrics["largest-contentful-paint"])} | ${cell(a.metrics["cumulative-layout-shift"], 3)} | ${cell(a.metrics["total-blocking-time"])} | ` +
        `${cell(a.metrics["first-contentful-paint"])} | ${cell(a.metrics["server-response-time"])} | ${fmt(a.transfer["script-transfer-kb"].median)} | ` +
        `${fmt(a.transfer["total-transfer-kb"].median)} | ${cell(a.mainThread["js-execution-ms"])} | ${fmt(a.benchmarkIndex.median)} | ` +
        `${s.budget.length ? s.budget.map((b) => `${b.severity === "error" ? "✗" : "!"} ${b.id}`).join("; ") : "ok"} |`,
    );
  }
  return `${lines.join("\n")}\n`;
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
