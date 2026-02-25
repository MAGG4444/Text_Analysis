const STORAGE_KEY = "narrative-analysis-history-v1";
const MAX_HISTORY_ITEMS = 10;
const MAX_STORED_TEXT = 120000;

const form = document.getElementById("analyzeForm");
const titleInput = document.getElementById("titleInput");
const fileInput = document.getElementById("fileInput");
const urlInput = document.getElementById("urlInput");
const discoverBtn = document.getElementById("discoverBtn");
const analyzeWebBtn = document.getElementById("analyzeWebBtn");
const discoveredFiles = document.getElementById("discoveredFiles");
const textInput = document.getElementById("textInput");
const useGenAiInput = document.getElementById("useGenAiInput");
const fileName = document.getElementById("fileName");
const statusEl = document.getElementById("status");
const resultPanel = document.getElementById("resultPanel");
const resultTitle = document.getElementById("resultTitle");
const resultMeta = document.getElementById("resultMeta");
const primaryTheme = document.getElementById("primaryTheme");
const themeChips = document.getElementById("themeChips");
const wordCount = document.getElementById("wordCount");
const peopleCount = document.getElementById("peopleCount");
const avgPeopleSentiment = document.getElementById("avgPeopleSentiment");
const analysisSummary = document.getElementById("analysisSummary");
const characterChart = document.getElementById("characterChart");
const peopleTableBody = document.getElementById("peopleTableBody");
const historyList = document.getElementById("historyList");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");
const resetBtn = document.getElementById("resetBtn");

let historyRecords = loadHistory();
let discoveredCandidates = [];
const CHARACTER_COLORS = [
  "#0e8a7f",
  "#d6792a",
  "#3d5aab",
  "#b24743",
  "#6a4da1",
  "#1a9a4b",
  "#8e3f90",
  "#6f7f2d",
];

function clampText(text, maxChars) {
  if (!text) return "";
  return text.length > maxChars ? text.slice(0, maxChars) : text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setStatus(message, type = "normal") {
  statusEl.textContent = message || "";
  statusEl.className = "status";
  if (type === "error") statusEl.classList.add("error");
  if (type === "success") statusEl.classList.add("success");
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch (_err) {
    return [];
  }
}

function saveHistory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(historyRecords));
}

function formatTimestamp(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return date.toLocaleString();
}

function scoreTagClass(sentiment) {
  if (sentiment === "positive") return "tag-positive";
  if (sentiment === "negative") return "tag-negative";
  return "tag-neutral";
}

function trajectorySvg(trajectory, color) {
  const width = 340;
  const height = 76;
  const padX = 12;
  const padY = 10;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;
  const points = Array.isArray(trajectory) ? trajectory : [];
  const count = points.length;
  if (!count) {
    return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="No trajectory"></svg>`;
  }

  const xAt = (index) => {
    if (count === 1) return padX + plotW / 2;
    return padX + (index / (count - 1)) * plotW;
  };
  const yAt = (score) => {
    const safe = Math.max(-1, Math.min(1, score));
    return padY + ((1 - safe) / 2) * plotH;
  };

  const segments = [];
  let current = [];
  points.forEach((point, idx) => {
    if (point.score === null || point.score === undefined) {
      if (current.length) segments.push(current);
      current = [];
      return;
    }
    current.push({ x: xAt(idx), y: yAt(point.score) });
  });
  if (current.length) segments.push(current);

  const polylines = segments
    .map((segment) => {
      const linePoints = segment.map((p) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
      return `<polyline fill="none" stroke="${color}" stroke-width="2.3" points="${linePoints}" />`;
    })
    .join("");

  const dots = segments
    .flatMap((segment) =>
      segment.map(
        (p) =>
          `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="2.5" fill="${color}" />`,
      ),
    )
    .join("");

  const midY = yAt(0);
  return `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Character trajectory">
      <line x1="${padX}" y1="${midY.toFixed(2)}" x2="${width - padX}" y2="${midY.toFixed(2)}" stroke="#d6dfe4" stroke-width="1" />
      ${polylines}
      ${dots}
    </svg>
  `;
}

function renderTheme(theme) {
  const primary = theme?.primary || "General / Mixed";
  primaryTheme.textContent = primary;

  const chips = Array.isArray(theme?.top_themes) ? theme.top_themes : [];
  if (!chips.length) {
    themeChips.innerHTML = "<span class='theme-chip'>No strong keyword theme detected</span>";
    return;
  }

  themeChips.innerHTML = chips
    .map((item) => {
      const safeTheme = escapeHtml(item.theme);
      const safeHits = Number(item.hits || 0);
      return `<span class="theme-chip">${safeTheme} (${safeHits})</span>`;
    })
    .join("");
}

function renderCharacterChart(characterData) {
  if (!characterData.length) {
    characterChart.innerHTML = "<p class='dock-note'>No repeated people names found yet.</p>";
    return;
  }

  characterChart.innerHTML = characterData
    .slice(0, 8)
    .map((item, idx) => {
      const color = CHARACTER_COLORS[idx % CHARACTER_COLORS.length];
      const safeName = escapeHtml(item.name);
      const sentimentCls = scoreTagClass(item.sentiment);
      const safeSentiment = escapeHtml(item.sentiment);
      const mentionLabel = `${item.mentions} mention${item.mentions === 1 ? "" : "s"}`;
      return `
        <article class="char-card">
          <div class="char-head">
            <div class="char-name" title="${safeName}">
              <span class="char-dot" style="background:${color};"></span>${safeName}
            </div>
            <div class="char-meta">
              <span>${mentionLabel}</span>
              <span class="${sentimentCls}">${safeSentiment}</span>
              <span>${item.score.toFixed(2)}</span>
            </div>
          </div>
          <div class="char-traj">${trajectorySvg(item.trajectory, color)}</div>
        </article>
      `;
    })
    .join("");
}

function renderPeopleTable(peopleData) {
  peopleTableBody.innerHTML = peopleData
    .map((person) => {
      const cls = scoreTagClass(person.sentiment);
      const safeName = escapeHtml(person.name);
      const safeSentiment = escapeHtml(person.sentiment);
      const evidence = Array.isArray(person.evidence) ? person.evidence : [];
      const safeEvidence = escapeHtml(evidence.join(" | "));
      return `
        <tr>
          <td>${safeName}</td>
          <td class="${cls}">${safeSentiment}</td>
          <td>${person.score.toFixed(2)}</td>
          <td>${person.mentions}</td>
          <td>${safeEvidence}</td>
        </tr>
      `;
    })
    .join("");
}

function renderResult(record) {
  const { analysis } = record;
  const peopleData = analysis.people_data || analysis.character_data || [];
  const genaiMeta = analysis.genai?.applied
    ? " | GenAI-assisted"
    : analysis.genai?.requested
      ? " | Local fallback"
      : "";

  resultTitle.textContent = record.title || "Analysis Results";
  resultMeta.textContent = `${record.source_name || "text"} | ${formatTimestamp(record.created_at)}${genaiMeta}`;

  wordCount.textContent = analysis.word_count.toLocaleString();
  peopleCount.textContent = String(analysis.people_count ?? peopleData.length);
  avgPeopleSentiment.textContent = Number(analysis.avg_people_sentiment || 0).toFixed(2);
  analysisSummary.textContent = analysis.one_sentence_summary || analysis.summary || "";

  renderTheme(analysis.theme || {});
  renderCharacterChart(peopleData);
  renderPeopleTable(peopleData);

  resultPanel.classList.remove("hidden");
}

function pushHistory(record) {
  const stored = {
    id: record.id,
    title: record.title,
    source_name: record.source_name,
    created_at: record.created_at,
    warning: record.warning,
    extracted_text: clampText(record.extracted_text || "", MAX_STORED_TEXT),
    analysis: record.analysis,
  };

  historyRecords = [stored, ...historyRecords.filter((item) => item.id !== stored.id)];
  historyRecords = historyRecords.slice(0, MAX_HISTORY_ITEMS);
  saveHistory();
  renderHistory();
}

function clearDiscoveredFiles() {
  discoveredCandidates = [];
  discoveredFiles.innerHTML = "";
}

function renderDiscoveredFiles(files) {
  discoveredCandidates = Array.isArray(files) ? files : [];
  if (!discoveredCandidates.length) {
    discoveredFiles.innerHTML = "<p class='dock-note'>No supported files found on that page.</p>";
    return;
  }

  discoveredFiles.innerHTML = discoveredCandidates
    .map((item, index) => {
      const safeLabel = escapeHtml(item.label || "Remote file");
      const safeUrl = escapeHtml(item.url || "");
      return `
        <article class="discovered-card">
          <h4 title="${safeLabel}">${safeLabel}</h4>
          <p class="discovered-url">${safeUrl}</p>
          <div class="discovered-actions">
            <button type="button" data-action="analyze-link" data-index="${index}">Analyze</button>
          </div>
        </article>
      `;
    })
    .join("");
}

async function discoverFilesFromUrl(sourceUrl) {
  const response = await fetch("/api/discover-files", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url: sourceUrl }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Unable to discover files from this link.");
  }
  return payload;
}

async function analyzeSubmission({
  title = "",
  text = "",
  file = null,
  sourceUrl = "",
  sourceMode = "auto",
  useGenAi = false,
}) {
  const body = new FormData();
  if (title) body.append("title", title);
  if (text) body.append("text", text);
  if (file) body.append("file", file);
  if (sourceUrl) body.append("source_url", sourceUrl);
  if (sourceMode) body.append("source_mode", sourceMode);
  body.append("use_genai", useGenAi ? "true" : "false");

  setStatus("Analyzing theme and people sentiment...");
  const response = await fetch("/api/analyze", {
    method: "POST",
    body,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Unable to analyze text.");
  }
  return payload;
}

function renderHistory() {
  if (!historyRecords.length) {
    historyList.innerHTML = "<p class='dock-note'>No submissions yet.</p>";
    return;
  }

  historyList.innerHTML = historyRecords
    .map((item) => {
      const people = item.analysis?.people_count ?? item.analysis?.character_data?.length ?? 0;
      const words = item.analysis?.word_count ?? 0;
      const safeId = escapeHtml(item.id);
      const safeTitle = escapeHtml(item.title || "Untitled Submission");
      return `
        <article class="history-card" data-id="${safeId}">
          <h4 title="${safeTitle}">${safeTitle}</h4>
          <p class="history-meta">${formatTimestamp(item.created_at)} | ${people} people | ${words} words</p>
          <div class="history-actions">
            <button type="button" data-action="load">Edit</button>
            <button type="button" data-action="resubmit">Resubmit</button>
          </div>
        </article>
      `;
    })
    .join("");
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files && fileInput.files[0];
  fileName.textContent = file ? file.name : "No file selected";
});

discoverBtn.addEventListener("click", async () => {
  const sourceUrl = urlInput.value.trim();
  if (!sourceUrl) {
    setStatus("Enter a web link first.", "error");
    return;
  }

  discoverBtn.disabled = true;
  discoverBtn.textContent = "Finding...";
  try {
    const payload = await discoverFilesFromUrl(sourceUrl);
    renderDiscoveredFiles(payload.files || []);
    if ((payload.files || []).length) {
      setStatus(`Found ${payload.files.length} supported file link(s).`, "success");
    } else {
      setStatus("No supported file links found on that page.", "error");
    }
  } catch (error) {
    clearDiscoveredFiles();
    setStatus(error.message || "File discovery failed.", "error");
  } finally {
    discoverBtn.disabled = false;
    discoverBtn.textContent = "Find Files";
  }
});

discoveredFiles.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  if (target.dataset.action !== "analyze-link") return;

  const index = Number(target.dataset.index);
  const candidate = discoveredCandidates[index];
  if (!candidate || !candidate.url) return;

  target.disabled = true;
  const oldLabel = target.textContent;
  target.textContent = "Analyzing...";
  try {
    const record = await analyzeSubmission({
      title: titleInput.value.trim() || candidate.label || "",
      sourceUrl: candidate.url,
      sourceMode: "auto",
      useGenAi: Boolean(useGenAiInput?.checked),
    });
    urlInput.value = candidate.url;
    renderResult(record);
    if (record.warning) {
      setStatus(record.warning, "success");
    } else {
      setStatus("Analysis complete from web link.", "success");
    }
    if (!titleInput.value.trim() && record.title) {
      titleInput.value = record.title;
    }
    if (record.extracted_text) {
      textInput.value = record.extracted_text;
    }
    pushHistory(record);
  } catch (error) {
    setStatus(error.message || "Web link analysis failed.", "error");
  } finally {
    target.disabled = false;
    target.textContent = oldLabel || "Analyze";
  }
});

analyzeWebBtn.addEventListener("click", async () => {
  const sourceUrl = urlInput.value.trim();
  if (!sourceUrl) {
    setStatus("Enter a web link first.", "error");
    return;
  }

  analyzeWebBtn.disabled = true;
  const oldText = analyzeWebBtn.textContent;
  analyzeWebBtn.textContent = "Analyzing...";
  try {
    const record = await analyzeSubmission({
      title: titleInput.value.trim(),
      sourceUrl,
      sourceMode: "webpage",
      useGenAi: Boolean(useGenAiInput?.checked),
    });
    renderResult(record);
    if (record.warning) {
      setStatus(record.warning, "success");
    } else {
      setStatus("Web page text analyzed.", "success");
    }
    if (!titleInput.value.trim() && record.title) {
      titleInput.value = record.title;
    }
    if (record.extracted_text) {
      textInput.value = record.extracted_text;
    }
    pushHistory(record);
  } catch (error) {
    setStatus(error.message || "Web page analysis failed.", "error");
  } finally {
    analyzeWebBtn.disabled = false;
    analyzeWebBtn.textContent = oldText || "Analyze Web Page";
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
  const text = textInput.value.trim();
  const sourceUrl = urlInput.value.trim();
  const title = titleInput.value.trim();

  if (!file && !text && !sourceUrl) {
    setStatus("Please upload a file, paste text, or provide a web link.", "error");
    return;
  }

  const analyzeBtn = document.getElementById("analyzeBtn");
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing...";

  try {
    const record = await analyzeSubmission({
      title,
      text,
      file,
      sourceUrl: !file && !text ? sourceUrl : "",
      sourceMode: "auto",
      useGenAi: Boolean(useGenAiInput?.checked),
    });
    renderResult(record);
    if (record.warning) {
      setStatus(record.warning, "success");
    } else {
      setStatus("Analysis complete.", "success");
    }
    if (record.extracted_text && !textInput.value.trim()) {
      textInput.value = record.extracted_text;
    }
    if (!titleInput.value.trim() && record.title) {
      titleInput.value = record.title;
    }
    pushHistory(record);
  } catch (error) {
    setStatus(error.message || "Analysis failed.", "error");
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze Theme + People";
  }
});

resetBtn.addEventListener("click", () => {
  form.reset();
  clearDiscoveredFiles();
  fileName.textContent = "No file selected";
  setStatus("");
});

clearHistoryBtn.addEventListener("click", () => {
  historyRecords = [];
  saveHistory();
  renderHistory();
});

historyList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  const action = target.dataset.action;
  const card = target.closest(".history-card");
  if (!card) return;

  const id = card.dataset.id;
  const record = historyRecords.find((item) => item.id === id);
  if (!record) return;

  if (action === "load") {
    titleInput.value = record.title || "";
    textInput.value = record.extracted_text || "";
    urlInput.value = "";
    clearDiscoveredFiles();
    fileInput.value = "";
    fileName.textContent = "No file selected";
    renderResult(record);
    setStatus("Loaded submission into editor.", "success");
    return;
  }

  if (action === "resubmit") {
    if (!record.extracted_text) {
      setStatus("No stored text to resubmit.", "error");
      return;
    }

    target.disabled = true;
    const oldText = target.textContent;
    target.textContent = "Running...";
    try {
      const newRecord = await analyzeSubmission({
        title: record.title || "",
        text: record.extracted_text,
        useGenAi: Boolean(useGenAiInput?.checked),
      });
      renderResult(newRecord);
      titleInput.value = newRecord.title || "";
      textInput.value = newRecord.extracted_text || record.extracted_text;
      setStatus("Resubmission complete.", "success");
      pushHistory(newRecord);
    } catch (error) {
      setStatus(error.message || "Resubmission failed.", "error");
    } finally {
      target.disabled = false;
      target.textContent = oldText || "Resubmit";
    }
  }
});

renderHistory();
