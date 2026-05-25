#!/usr/bin/env node
// log-streamer.js — SSE server that tails OpenClaw session .jsonl files
// Streams only assistant messages and tool call names (sanitized).
// Runs on port 9090, bound to localhost (exposed via Cloudflare tunnel).

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = 9090;
const SESSIONS_DIR = path.join(process.env.HOME || "/home/ubuntu", ".openclaw/agents/main/sessions");
const MAX_HISTORY = 30;

const clients = new Set();
const history = [];

function getSessionFiles() {
  try {
    return fs.readdirSync(SESSIONS_DIR)
      .filter(f => f.endsWith(".jsonl") && !f.includes(".trajectory."))
      .map(f => ({ name: f, path: path.join(SESSIONS_DIR, f), mtime: fs.statSync(path.join(SESSIONS_DIR, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);
  } catch { return []; }
}

function sanitizeLine(raw) {
  try {
    const entry = JSON.parse(raw);
    // Only stream message entries
    if (entry.type !== "message") return null;
    const msg = entry.message;
    if (!msg || msg.role !== "assistant") return null;

    const content = msg.content || [];
    const texts = content.filter(c => c.type === "text").map(c => c.text).filter(Boolean);
    const tools = content.filter(c => c.type === "toolCall").map(c => c.name).filter(Boolean);

    if (!texts.length && !tools.length) return null;

    return JSON.stringify({
      ts: entry.timestamp,
      text: texts.join("\n"),
      tools: tools.length ? tools : undefined,
    });
  } catch { return null; }
}

function broadcast(sanitized) {
  history.push(sanitized);
  if (history.length > MAX_HISTORY) history.shift();
  const payload = `data: ${sanitized}\n\n`;
  for (const res of clients) {
    try { res.write(payload); } catch { clients.delete(res); }
  }
}

// Watch the latest session file for new lines
let watcher = null;
let currentFile = null;
let fileSize = 0;

function watchLatest() {
  const files = getSessionFiles();
  const latest = files[0];
  if (!latest) { setTimeout(watchLatest, 3000); return; }

  if (latest.path !== currentFile) {
    if (watcher) { try { watcher.close(); } catch {} }
    currentFile = latest.path;
    fileSize = fs.statSync(currentFile).size;
    watcher = fs.watch(currentFile, () => {
      try {
        const stat = fs.statSync(currentFile);
        if (stat.size <= fileSize) return;
        const stream = fs.createReadStream(currentFile, { start: fileSize, encoding: "utf8" });
        let buf = "";
        stream.on("data", chunk => { buf += chunk; });
        stream.on("end", () => {
          fileSize = stat.size;
          for (const line of buf.split("\n")) {
            if (!line.trim()) continue;
            const sanitized = sanitizeLine(line);
            if (sanitized) broadcast(sanitized);
          }
        });
      } catch {}
    });
  }

  // Check for newer session files periodically
  setTimeout(watchLatest, 5000);
}

const server = http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("ok");
    return;
  }
  if (req.url !== "/stream") {
    res.writeHead(404);
    res.end();
    return;
  }

  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "Access-Control-Allow-Origin": "*",
    "X-Accel-Buffering": "no",
  });

  // Send recent history
  for (const entry of history) {
    res.write(`data: ${entry}\n\n`);
  }

  clients.add(res);
  req.on("close", () => clients.delete(res));
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[log-streamer] SSE on 127.0.0.1:${PORT}/stream`);
  watchLatest();
});
