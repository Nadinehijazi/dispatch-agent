const form = document.getElementById("complaintForm");
const statusEl = document.getElementById("status");
const errorBox = document.getElementById("errorBox");
const submitBtn = document.getElementById("submitBtn");
const traceWrap = document.getElementById("traceWrap");
const rawOutput = document.getElementById("rawOutput");
const copyFinalBtn = document.getElementById("copyFinalBtn");
const copyStatus = document.getElementById("copyStatus");
const agencyChip = document.getElementById("agencyChip");
const urgencyChip = document.getElementById("urgencyChip");
const actionText = document.getElementById("actionText");
const justificationText = document.getElementById("justificationText");
const confidenceFill = document.getElementById("confidenceFill");
const confidenceLabel = document.getElementById("confidenceLabel");
const reviewBanner = document.getElementById("reviewBanner");
const historyList = document.getElementById("historyList");
const quickPrompt = document.getElementById("quick_prompt");
const quickRunBtn = document.getElementById("quickRunBtn");
const quickStatus = document.getElementById("quickStatus");

const submitBtnDefaultText = submitBtn ? submitBtn.textContent : "Submit complaint";
const quickBtnDefaultText = quickRunBtn ? quickRunBtn.textContent : "Run Agent";

function setStatus(text) {
  statusEl.textContent = text;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.style.display = "block";
}

function clearError() {
  errorBox.textContent = "";
  errorBox.style.display = "none";
}

function setButtonLoading(button, isLoading, runningLabel, defaultLabel) {
  if (!button) return;
  button.disabled = isLoading;
  if (isLoading) {
    button.innerHTML = `<span class="spinner" aria-hidden="true"></span> ${runningLabel}`;
  } else {
    button.textContent = defaultLabel;
  }
}

function updateUrgency(urgency) {
  urgencyChip.className = "chip";
  if (urgency === "low") urgencyChip.classList.add("urgency-low");
  if (urgency === "medium") urgencyChip.classList.add("urgency-medium");
  if (urgency === "high") urgencyChip.classList.add("urgency-high");
  urgencyChip.textContent = `Urgency: ${urgency || "-"}`;
}

function escapeHtml(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

function prettyJson(obj) {
  try {
    return JSON.stringify(obj ?? null, null, 2);
  } catch {
    return String(obj);
  }
}

function renderTraceSteps(steps) {
  const arr = Array.isArray(steps) ? steps : [];

  if (!traceWrap) return;
  if (arr.length === 0) {
    traceWrap.innerHTML = `<p class="status">No steps.</p>`;
    return;
  }

  traceWrap.innerHTML = arr.map((s, idx) => {
    const module = escapeHtml(s.module || `Step ${idx + 1}`);
    const promptRaw = prettyJson(s.prompt);
    const responseRaw = prettyJson(s.response);
    const promptJson = escapeHtml(promptRaw);
    const responseJson = escapeHtml(responseRaw);

    return `
      <details class="step-card">
        <summary>Step ${idx + 1}</summary>
        <div class="step-body">
          <div class="kv">
            <div class="kv-title">Module</div>
            <pre class="json">${module}</pre>
          </div>
          <div class="kv">
            <div class="kv-title">
              Prompt JSON
              <button class="btn-secondary copy-step" type="button" data-copy="${escapeHtml(promptRaw)}">Copy JSON</button>
            </div>
            <pre class="json">${promptJson}</pre>
          </div>
          <div class="kv">
            <div class="kv-title">
              Response JSON
              <button class="btn-secondary copy-step" type="button" data-copy="${escapeHtml(responseRaw)}">Copy JSON</button>
            </div>
            <pre class="json">${responseJson}</pre>
          </div>
        </div>
      </details>
    `;
  }).join("");

  traceWrap.querySelectorAll(".copy-step").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await copyText(btn.getAttribute("data-copy") || "");
      } catch {}
    });
  });
}

function resetDecision() {
  agencyChip.textContent = "Agency: -";
  updateUrgency(null);
  actionText.textContent = "-";
  justificationText.textContent = "-";
  confidenceFill.style.width = "0%";
  confidenceLabel.textContent = "-";
  reviewBanner.style.display = "none";
  if (traceWrap) traceWrap.innerHTML = `<p class="status">-</p>`;
  if (rawOutput) rawOutput.textContent = "-";
  if (copyStatus) copyStatus.textContent = "";
}

async function loadHistory() {
  try {
    const res = await fetch("/api/complaints_recent");
    const data = await res.json();
    if (!data.items || data.items.length === 0) {
      historyList.textContent = "No records yet.";
      return;
    }
    historyList.innerHTML = data.items.map((item) => {
      const name = item.full_name || "Unknown";
      const borough = item.borough || "UNKNOWN";
      const status = item.status || "new";
      const summary = (item.complaint_text || "").slice(0, 80);
      return `<div class="history-item"><strong>${escapeHtml(name)}</strong> | ${escapeHtml(borough)} | ${escapeHtml(status)}<br/>${escapeHtml(summary)}</div>`;
    }).join("");
  } catch (e) {
    historyList.textContent = "Unable to load history.";
  }
}

function showBanner(text) {
  reviewBanner.textContent = text;
  reviewBanner.style.display = "flex";
}

function renderDecision(execData) {
  renderTraceSteps(execData.steps);
  if (rawOutput) rawOutput.textContent = prettyJson(execData);

  const decisionStep = (execData.steps || []).find(
    (s) => s.module === "Decide_DispatchDecision"
  );
  const decision = decisionStep ? decisionStep.response : null;

  if (decision) {
    agencyChip.textContent = `Agency: ${decision.agency || "-"}`;
    updateUrgency(decision.urgency);
    actionText.textContent = decision.action || "-";
    justificationText.textContent = decision.justification || "-";

    const confidence = Number(decision.confidence || 0);
    confidenceFill.style.width = `${Math.min(100, Math.round(confidence * 100))}%`;
    confidenceLabel.textContent = `Confidence: ${(confidence * 100).toFixed(0)}%`;
  }

  // ✅ Banner logic (read from Human_Review_Escalation step, not top-level)
  const reviewStep = (execData.steps || []).find(
    (s) => s.module === "Human_Review_Escalation"
  );
  const review = reviewStep ? (reviewStep.response || {}) : {};

  const needsHumanReview = !!review.needs_human_review;
  const needsFollowup = !!review.needs_followup;
  const needsReview = !!review.needs_review;
  const missing = Array.isArray(review.missing_fields) ? review.missing_fields : [];

  if (needsHumanReview) {
    reviewBanner.style.display = "flex";
    if (needsFollowup) {
      reviewBanner.textContent = `Follow-up required: missing ${missing.join(", ") || "required fields"}.`;
    } else if (needsReview) {
      reviewBanner.textContent = "Human review recommended: low confidence.";
    } else {
      reviewBanner.textContent = review.reason || "Human review recommended.";
    }
  } else {
    reviewBanner.style.display = "none";
    reviewBanner.textContent = "";
  }
  if (copyFinalBtn) {
    copyFinalBtn.onclick = async () => {
      try {
        await copyText(prettyJson(execData));
        if (copyStatus) copyStatus.textContent = "Copied.";
        setTimeout(() => {
          if (copyStatus) copyStatus.textContent = "";
        }, 1200);
      } catch {
        if (copyStatus) copyStatus.textContent = "Copy failed.";
      }
    };
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  resetDecision();

  const payload = {
    full_name: form.full_name.value.trim(),
    phone: form.phone.value.trim() || null,
    email: form.email.value.trim() || null,
    complaint_text: form.complaint_text.value.trim(),
    borough: form.borough.value || null,
    location_details: form.location_details.value.trim() || null,
    incident_time: form.incident_time.value.trim() || null,
    urgency_hint: form.urgency_hint.value || null,
    consent: form.consent.checked,
  };

  if (!payload.full_name || !payload.complaint_text) {
    showError("Full name and complaint details are required.");
    return;
  }

  if (!payload.borough || payload.borough === "UNKNOWN") {
    showError("Borough is required to submit a complaint.");
    return;
  }

  // Optional: require location_details too
  // (recommended for true dispatch tickets; borough alone might be insufficient)
  if (!payload.location_details || payload.location_details.trim().length < 3) {
    showError("Location details (address / landmark) are required to submit a complaint.");
    return;
  }

  setButtonLoading(submitBtn, true, "Running...", submitBtnDefaultText);
  setStatus("Running...");

  try {
    const createRes = await fetch("/api/complaints", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const createData = await createRes.json();
    if (createData.status !== "ok") {
      throw new Error(createData.error || "Failed to save complaint.");
    }

    const execRes = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ complaint_id: createData.complaint_id }),
    });
    const execData = await execRes.json();
    renderDecision(execData);

    if (execData.status !== "ok") {
      showError(execData.error || "Agent failed to run.");
      setStatus("Error");
      return;
    }

    setStatus("Done.");
    await loadHistory();
  } catch (e) {
    showError(String(e));
    setStatus("Error");
  } finally {
    setButtonLoading(submitBtn, false, "Running...", submitBtnDefaultText);
  }
});

quickRunBtn.addEventListener("click", async () => {
  clearError();
  resetDecision();
  setButtonLoading(quickRunBtn, true, "Running...", quickBtnDefaultText);
  quickStatus.textContent = "Running...";

  try {
    const prompt = (quickPrompt.value || "").trim();
    if (!prompt) {
      throw new Error("Prompt is required.");
    }
    const execRes = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const execData = await execRes.json();
    renderDecision(execData);

    if (execData.status !== "ok") {
      showError(execData.error || "Agent failed to run.");
      quickStatus.textContent = "Error";
      return;
    }
    quickStatus.textContent = "Done.";
  } catch (e) {
    showError(String(e));
    quickStatus.textContent = "Error";
  } finally {
    setButtonLoading(quickRunBtn, false, "Running...", quickBtnDefaultText);
  }
});

loadHistory();
