/* ══════════════════════════════════════════════════
   Personal Dashboard — Frontend Logic
   ══════════════════════════════════════════════════ */
(async () => {

"use strict";

/* ── Boot Sequence ────────────────────────────────── */
const bootEl   = document.getElementById("boot");
const bootText = document.getElementById("boot-content");
const dashEl   = document.getElementById("dashboard");

const bootLines = [
  "",
  " > Initializing personal dashboard v1.0...",
  " > Connecting data feeds...",
  "",
  "   [  ..  ] Weather station      ",
  "   [  ..  ] GitHub API           ",
  "   [  ..  ] arXiv feed           ",
  "",
  " > System ready. Welcome, Jacken.",
  "",
];

// resolve boot lines in real-time with success/fail status
const resolved = [
  "",
  " > Initializing personal dashboard v1.0...  [OK]",
  " > Connecting data feeds...",
  "",
];

const FEED_OK  = "[  OK  ]";
const FEED_FAIL = "[FAIL ]";

function feedLine(name, ok) {
  return `   ${ok ? FEED_OK : FEED_FAIL} ${name.padEnd(22)}`;
}

async function playBoot() {
  const lines = [...resolved];

  // show initialization
  for (let i = 0; i < lines.length; i++) {
    bootText.textContent = lines.slice(0, i + 1).join("\n");
    await delay(180 + Math.random() * 120);
  }

  // try to load actual data for boot status
  const weatherOk = await probeData("weather.json");
  const githubOk = await probeData("github.json");
  const arxivOk  = await probeData("arxiv.json");

  lines.push("");
  lines.push(feedLine("Weather station", weatherOk));
  await appendLines(bootText, lines, 1);
  lines.push(feedLine("GitHub API", githubOk));
  await appendLines(bootText, lines, 1);
  lines.push(feedLine("arXiv feed", arxivOk));
  await appendLines(bootText, lines, 1);
  lines.push("");
  await appendLines(bootText, lines, 1);

  const allOk = weatherOk && githubOk && arxivOk;
  const readyLine = allOk
    ? " > System ready. Welcome, Jacken."
    : " > System online (partial). Welcome, Jacken.";
  lines.push(readyLine);
  bootText.textContent = lines.join("\n");
  await delay(600);

  // fade out boot screen
  bootEl.classList.add("fade-out");
  await delay(600);
  bootEl.style.display = "none";
  dashEl.classList.remove("hidden");
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

async function appendLines(el, lines, count) {
  const start = lines.length - count;
  for (let i = 0; i < count; i++) {
    el.textContent = lines.slice(0, start + i + 1).join("\n");
    await delay(100 + Math.random() * 80);
  }
}

async function probeData(file) {
  try {
    const r = await fetch(`./data/${file}?_=${Date.now()}`, { method: "HEAD" });
    return r.ok;
  } catch { return false; }
}


/* ── Data Loader ──────────────────────────────────── */
async function loadJSON(file) {
  const r = await fetch(`./data/${file}?_=${Date.now()}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

function $id(id) { return document.getElementById(id); }


/* ── Clock & Greeting ─────────────────────────────── */
function updateClock() {
  const now = new Date();
  const h = now.getHours().toString().padStart(2, "0");
  const m = now.getMinutes().toString().padStart(2, "0");
  const s = now.getSeconds().toString().padStart(2, "0");
  $id("clock").textContent = `${h}:${m}:${s}`;

  // greeting
  let greet = "Good evening";
  if (h < 6) greet = "Still up";
  else if (h < 12) greet = "Good morning";
  else if (h < 14) greet = "Good afternoon";
  else if (h < 18) greet = "Good afternoon";
  else greet = "Good evening";
  $id("greeting").textContent = `${greet}, Jacken`;
}


/* ── Render Sections ──────────────────────────────── */

// ── Weather ──
function renderWeather(data) {
  const badge = $id("weather-badge");
  if (!data || data.error) {
    badge.textContent = "☁️ --°C";
    return;
  }
  badge.textContent = `☁️ ${data.temperature || "--"}°C · ${data.condition || ""}`;
}

// ── GitHub ──
function renderGitHub(data) {
  const body = $id("github-body");
  const badge = $id("github-badge");

  if (!data || data.error) {
    body.innerHTML = '<div class="error-state">⨯ failed to load</div>';
    return;
  }

  // Update stats bar
  $id("stat-repos").querySelector(".stat-value").textContent = data.public_repos ?? "--";
  $id("stat-stars").querySelector(".stat-value").textContent = data.total_stars ?? "--";
  $id("stat-followers").querySelector(".stat-value").textContent = data.followers ?? "--";

  badge.textContent = `${data.repos?.length || 0} repos`;

  if (!data.repos || data.repos.length === 0) {
    body.innerHTML = '<div class="empty-state">no public repos</div>';
    return;
  }

  let html = "";
  for (const r of data.repos) {
    const desc = r.description ? `<span class="repo-desc">${escapeHtml(r.description)}</span>` : "";
    const lang = r.language ? `<span class="repo-lang">${escapeHtml(r.language)}</span>` : "";
    const stars = r.stars > 0 ? `<span class="repo-stars">★ ${r.stars}</span>` : "";
    html += `
      <div class="repo-item">
        <div>
          <a class="repo-name" href="${r.url}" target="_blank" rel="noopener">
            ${escapeHtml(r.name)}${desc}
          </a>
        </div>
        <div>${stars}${lang}</div>
      </div>`;
  }
  body.innerHTML = html;
}

// ── arXiv / Research ──
function renderArxiv(data) {
  const body = $id("arxiv-body");
  const badge = $id("arxiv-badge");

  if (!data || data.error) {
    body.innerHTML = '<div class="error-state">⨯ failed to load</div>';
    return;
  }

  const papers = data.papers || [];
  $id("stat-papers").querySelector(".stat-value").textContent = papers.length;
  badge.textContent = papers.length > 0 ? `${papers.length} papers` : "0";

  if (papers.length === 0) {
    body.innerHTML = '<div class="empty-state">no recent papers</div>';
    return;
  }

  let html = "";
  for (const p of papers) {
    html += `
      <div class="paper-item">
        <a class="paper-title" href="${escapeHtml(p.link)}" target="_blank" rel="noopener">
          ${escapeHtml(p.title)}
        </a>
        <div class="paper-meta">
          <span>${escapeHtml(p.authors)}</span>
          <span>${p.published || ""}</span>
          <span class="tag">${p.id || ""}</span>
        </div>
      </div>`;
  }
  body.innerHTML = html;
}

// ── Daily Quote ──
function renderDaily(data) {
  const body = $id("quote-body");
  const badge = $id("daily-badge");

  if (!data || data.error) {
    body.innerHTML = '<div class="error-state">⨯ failed to load</div>';
    return;
  }

  badge.textContent = data.date || "";

  if (data.quote) {
    body.innerHTML = `
      <div class="quote-text">${escapeHtml(data.quote.text)}</div>
      <div class="quote-author">${escapeHtml(data.quote.author)}</div>`;
  } else {
    body.innerHTML = '<div class="empty-state">no quote</div>';
  }
}

// ── Bird of the Day ──
function renderBird(data) {
  const body = $id("bird-body");
  const badge = $id("bird-badge");

  if (!data || data.error) {
    body.innerHTML = '<div class="error-state">⨯ failed to load</div>';
    return;
  }

  if (data.bird) {
    const hint = data.bird.name_cn
      ? `${data.bird.name_cn} · try spotting one today!`
      : "try spotting one today!";
    badge.textContent = data.bird.name_cn || "";
    body.innerHTML = `
      <div>
        <span class="bird-name">${escapeHtml(data.bird.name_en)}</span>
        <span class="bird-name-cn">${escapeHtml(data.bird.name_cn || "")}</span>
      </div>
      <div class="bird-hint">${hint}</div>`;
  } else {
    body.innerHTML = '<div class="empty-state">no bird data</div>';
  }
}

// ── Footer ──
function renderFooter(data) {
  const el = $id("footer-updated");
  if (!data || !data.updated_at) {
    el.textContent = "last updated: unknown";
    return;
  }
  const d = new Date(data.updated_at);
  const pad = n => n.toString().padStart(2, "0");
  el.textContent = `updated: ${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ── Ping / connectivity ──
function renderPing(time) {
  const el = $id("footer-ping");
  if (time) {
    el.textContent = `response: ${time}ms`;
  } else {
    el.textContent = "";
  }
}


/* ── Helpers ──────────────────────────────────────── */
function escapeHtml(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}


/* ── Main ─────────────────────────────────────────── */
async function main() {
  // Play boot sequence
  await playBoot();

  // Start clock
  updateClock();
  setInterval(updateClock, 1000);

  // Load all data files in parallel
  const startTime = performance.now();
  let hasData = false;

  try {
    const [weather, github, arxiv, daily, ts] = await Promise.all([
      loadJSON("weather.json"),
      loadJSON("github.json"),
      loadJSON("arxiv.json"),
      loadJSON("daily.json"),
      loadJSON("timestamp.json").catch(() => null),
    ]);
    hasData = true;

    renderWeather(weather);
    renderGitHub(github);
    renderArxiv(arxiv);
    renderDaily(daily);
    renderBird(daily);
    renderFooter(ts || daily || weather);

    const ping = Math.round(performance.now() - startTime);
    renderPing(ping);

  } catch (err) {
    console.warn("Dashboard data load error:", err);
    // Show partial results if some loaded
    // if everything failed, show messages on all cards
    if (!hasData) {
      const cards = document.querySelectorAll(".card-body");
      for (const c of cards) {
        if (c.querySelector(".loading-dots")) {
          c.innerHTML = '<div class="error-state">⨯ data unavailable. waiting for first sync...</div>';
        }
      }
      $id("footer-updated").textContent = "waiting for first data sync...";
    }
  }
}

main();

})();
