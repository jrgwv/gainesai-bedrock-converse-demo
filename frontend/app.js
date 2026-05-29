async function sendMessage() {
  const apiUrl = document.getElementById("api-url").value.trim();
  const taskType = document.getElementById("task-type").value;
  const systemPrompt = document.getElementById("system-prompt").value.trim();
  const message = document.getElementById("message").value.trim();

  if (!message) return;

  const btn = document.getElementById("send-btn");
  btn.disabled = true;
  btn.textContent = "Sending…";
  hide("response-area", "error-area");

  const payload = {
    messages: [{ role: "user", content: message }],
    task_type: taskType,
  };
  if (systemPrompt) payload.system_prompt = systemPrompt;

  try {
    const resp = await fetch(`${apiUrl}/converse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail ?? resp.statusText);
    }

    showResponse(await resp.json());
  } catch (err) {
    showError(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Send";
  }
}

function showResponse(data) {
  document.getElementById("response-content").textContent = data.content;
  document.getElementById("model-id").textContent = data.model_id;
  document.getElementById("tokens-in").textContent = data.input_tokens;
  document.getElementById("tokens-out").textContent = data.output_tokens;
  document.getElementById("latency").textContent = `${data.latency_ms.toFixed(0)} ms`;
  document.getElementById("fallback").textContent = data.fallback_used ? "Yes ⚠️" : "No";
  document.getElementById("response-area").classList.remove("hidden");
}

function showError(message) {
  const el = document.getElementById("error-area");
  el.textContent = `Error: ${message}`;
  el.classList.remove("hidden");
}

function hide(...ids) {
  ids.forEach((id) => document.getElementById(id).classList.add("hidden"));
}

document.getElementById("message").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendMessage();
});
