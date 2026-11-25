// Debug/performance pass through the Chrome DevTools MCP server: console errors, failed network
// requests on every page, Lighthouse (accessibility / best practices / SEO) and a performance trace.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import fs from "node:fs";

const BASE = process.env.BASE ?? "http://127.0.0.1:5173";
import path from "node:path";
const OUT = path.resolve(process.env.OUT ?? "output/devtools");
fs.mkdirSync(OUT, { recursive: true });
const extra = process.env.CHROME_PATH ? ["--executablePath", process.env.CHROME_PATH] : [];
if (process.platform === "linux") extra.push("--chromeArg=--no-sandbox");
const t = new StdioClientTransport({ command: process.platform === "win32" ? "npx.cmd" : "npx",
  args: ["-y", "chrome-devtools-mcp@latest", "--headless", "--isolated", "--viewport", "1440x900", ...extra], env: { ...process.env }, stderr: "pipe" });
const c = new Client({ name: "salespilot-devtools", version: "1.0.0" });
await c.connect(t);
const txt = (r) => (r.content || []).filter((x) => x.type === "text").map((x) => x.text).join("\n");
const call = async (name, args = {}) => { const r = await c.callTool({ name, arguments: { pageId: 1, ...args } }); return txt(r); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const report = [];

for (const path of ["/", "/agent", "/crm", "/appointments", "/knowledge", "/analytics", "/settings"]) {
  await call("navigate_page", { type: "url", url: BASE + path });
  await sleep(2500);
  const consoleOut = await call("list_console_messages");
  const net = await call("list_network_requests");
  const errors = consoleOut.split("\n").filter((l) => /\b(error|Error)\b/.test(l) && !/^#/.test(l));
  const failed = net.split("\n").filter((l) => /\[(failed|[45]\d\d)\]|net::ERR/.test(l));
  const apiCalls = net.split("\n").filter((l) => l.includes("/api/")).length;
  report.push({ path, consoleErrors: errors, failedRequests: failed, apiCalls });
  console.log(`${path}: console errors=${errors.length}, failed requests=${failed.length}, api calls=${apiCalls}`);
}

for (const [path, device] of [["/", "desktop"], ["/agent", "desktop"], ["/crm", "mobile"]]) {
  await call("navigate_page", { type: "url", url: BASE + path });
  await sleep(1500);
  const lh = await call("lighthouse_audit", { mode: "navigation", device });
  fs.writeFileSync(`${OUT}/lighthouse${path.replace(/\//g, "_") || "_root"}-${device}.txt`, lh);
  const scores = [...lh.matchAll(/(Accessibility|Best Practices|SEO|Performance)[^\d\n]*(\d{1,3})/gi)].map((m) => `${m[1]} ${m[2]}`);
  console.log(`Lighthouse ${path} (${device}):`, scores.join(", ") || lh.slice(0, 300));
  report.push({ lighthouse: path, device, scores, excerpt: lh.slice(0, 2500) });
}

// Lighthouse may leave extra tabs; open a fresh page for the trace and target it explicitly.
const opened = await call("new_page", { url: BASE + "/" });
const pid = Number([...opened.matchAll(/^(\d+): .*\[selected\]/gm)].pop()?.[1] ?? 1);
await sleep(1500);
const perf = await call("performance_start_trace", { pageId: pid, reload: true, autoStop: true });
fs.writeFileSync(`${OUT}/performance.txt`, perf);
const lcp = perf.match(/LCP[^\n]*|CLS[^\n]*/g);
console.log("Performance:", lcp ? lcp.slice(0, 4).join(" | ") : perf.slice(0, 600));
fs.writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 2));
await c.close();
