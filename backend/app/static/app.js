const form = document.getElementById("complaintForm");
const statusEl = document.getElementById("status");
const errorBox = document.getElementById("errorBox");
const submitBtn = document.getElementById("submitBtn");
const stepsTraceEl = document.getElementById("stepsTrace");
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

function updateUrgency(urgency) {
  urgencyChip.className = "chip";
  if (urgency === "low") urgencyChip.classList.add("urgency-low");
  if (urgency === "medium") urgencyChip.classList.add("urgency-medium");
  if (urgency === "high") urgencyChip.classList.add("urgency-high");
  urgencyChip.textContent = `Urgency: ${urgency || "—"}`;
}

function resetDecision() {
  agencyChip.textContent = "Agency: —";
  updateUrgency(null);
  actionText.textContent = "—";
  justificationText.textContent = "—";
  confidenceFill.style.width = "0%";
  confidenceLabel.textContent = "—";
  reviewBanner.style.display = "none";
  stepsTraceEl.textContent = "—";
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
      return `<div class="history-item"><strong>${name}</strong> · ${borough} · ${status}<br/>${summary}</div>`;
    }).join("");
  } catch (e) {
    historyList.textContent = "Unable to load history.";
  }
}

function renderDecision(execData) {
  stepsTraceEl.textContent = JSON.stringify(execData.steps ?? [], null, 2);
  const decisionStep = (execData.steps || []).find((s) => s.module === "Decide_DispatchDecision");
  const reviewStep = (execData.steps || []).find((s) => s.module === "Human_Review_Escalation");
  const decision = decisionStep ? decisionStep.response : null;

  if (decision) {
    agencyChip.textContent = `Agency: ${decision.agency || "—"}`;
    updateUrgency(decision.urgency);
    actionText.textContent = decision.action || "—";
    justificationText.textContent = decision.justification || "—";
    const confidence = Number(decision.confidence || 0);
    confidenceFill.style.width = `${Math.min(100, Math.round(confidence * 100))}%`;
    confidenceLabel.textContent = `Confidence: ${(confidence * 100).toFixed(0)}%`;
    if (reviewStep && reviewStep.response && reviewStep.response.needs_human_review) {
      reviewBanner.style.display = "flex";
    }
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

  submitBtn.disabled = true;
  setStatus("Saving complaint...");

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

    setStatus("Running agent...");
    const execRes = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ complaint_id: createData.complaint_id }),
    });
    const execData = await execRes.json();
    if (execData.status !== "ok") {
      throw new Error(execData.error || "Agent failed to run.");
    }

    renderDecision(execData);

    setStatus("Done.");
    await loadHistory();
  } catch (e) {
    showError(String(e));
    setStatus("Error");
  } finally {
    submitBtn.disabled = false;
  }
});

quickRunBtn.addEventListener("click", async () => {
  clearError();
  resetDecision();
  quickRunBtn.disabled = true;
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
    if (execData.status !== "ok") {
      throw new Error(execData.error || "Agent failed to run.");
    }
    renderDecision(execData);
    quickStatus.textContent = "Done.";
  } catch (e) {
    showError(String(e));
    quickStatus.textContent = "Error";
  } finally {
    quickRunBtn.disabled = false;
  }
});

loadHistory();
