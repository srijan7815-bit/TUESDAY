/**
 * TUESDAY HUD client — thin frontend; credentials stay server-side.
 */
(() => {
  "use strict";

  const $ = (sel, el = document) => el.querySelector(sel);

  const state = {
    conversationId: localStorage.getItem("tuesday.conversationId") || crypto.randomUUID(),
    abort: null,
    streaming: false,
    workspace: { status: "none", provider: "—" },
    health: null,
    msgCount: 0,
    pendingAttachments: [],
    voiceOutput: localStorage.getItem("tuesday.voiceOutput") === "true",
    recorder: null,
    recordingStream: null,
    recordChunks: [],
    protectedBooted: false,
  };

  const motionPreference = localStorage.getItem("tuesday.reduceMotion") === "true";
  document.documentElement.dataset.reducedMotion = String(motionPreference);

  localStorage.setItem("tuesday.conversationId", state.conversationId);

  const els = {
    messages: $("#messages"),
    input: $("#input"),
    form: $("#composer"),
    btnSend: $("#btn-send"),
    btnStop: $("#btn-stop"),
    streamState: $("#stream-state"),
    lblModel: $("#lbl-model"),
    lblWs: $("#lbl-ws"),
    pillWs: $("#pill-ws"),
    lblConv: $("#lbl-conv"),
    desktopImg: $("#desktop-img"),
    desktopPh: $("#desktop-placeholder"),
    desktopMeta: $("#desktop-meta"),
    memoryList: $("#memory-list"),
    modal: $("#modal"),
    modalBody: $("#modal-body"),
    modalYes: $("#modal-yes"),
    modalNo: $("#modal-no"),
    toasts: $("#toasts"),
    // status
    barHp: $("#bar-hp"),
    barMp: $("#bar-mp"),
    barCpu: $("#bar-cpu"),
    valHp: $("#val-hp"),
    valMp: $("#val-mp"),
    valCpu: $("#val-cpu"),
    sStr: $("#s-str"),
    sVit: $("#s-vit"),
    sAgi: $("#s-agi"),
    sInt: $("#s-int"),
    sPer: $("#s-per"),
    sCtx: $("#s-ctx"),
    statLevel: $("#stat-level"),
    statAp: $("#stat-ap"),
    sysClock: $("#sys-clock"),
    btnNewSession: $("#btn-new-session"),
    btnMotion: $("#btn-motion"),
    btnAttach: $("#btn-attach"),
    btnRecord: $("#btn-record"),
    btnVoice: $("#btn-voice"),
    fileInput: $("#file-input"),
    approvalList: $("#approval-list"),
    btnApprovalRefresh: $("#btn-approval-refresh"),
    authGate: $("#auth-gate"),
    authForm: $("#auth-form"),
    authToken: $("#auth-token"),
    authError: $("#auth-error"),
  };

  function updateClock() {
    if (!els.sysClock) return;
    els.sysClock.textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  function setReducedMotion(reduced) {
    document.documentElement.dataset.reducedMotion = String(reduced);
    localStorage.setItem("tuesday.reduceMotion", String(reduced));
    els.btnMotion?.setAttribute("aria-pressed", String(reduced));
    if (els.btnMotion) els.btnMotion.textContent = reduced ? "Motion off" : "Motion";
  }

  els.lblConv.textContent = `CONV ${state.conversationId.slice(0, 8)}`;

  function toast(msg, kind = "info") {
    const t = document.createElement("div");
    t.className = `toast${kind === "error" ? " error" : ""}`;
    t.textContent = msg;
    els.toasts.appendChild(t);
    setTimeout(() => t.remove(), 4200);
  }

  function setStreamUI(on) {
    state.streaming = on;
    els.btnSend.disabled = on;
    els.btnStop.disabled = !on;
    els.streamState.textContent = on ? "streaming" : "idle";
  }

  function appendMessage(role, content, { streaming = false, id = null } = {}) {
    const wrap = document.createElement("article");
    wrap.className = `msg ${role}${streaming ? " streaming" : ""}`;
    if (id) wrap.dataset.id = id;
    const roleEl = document.createElement("div");
    roleEl.className = "role";
    roleEl.textContent = role;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = content;
    wrap.append(roleEl, bubble);
    els.messages.appendChild(wrap);
    els.messages.scrollTop = els.messages.scrollHeight;
    state.msgCount += 1;
    els.sCtx.textContent = String(state.msgCount);
    updateHudStats();
    return wrap;
  }

  function establishNewConversation() {
    state.conversationId = crypto.randomUUID();
    state.workspace = {
      status: "none",
      provider: state.health?.capabilities?.sandbox_provider || "—",
    };
    state.msgCount = 0;
    localStorage.setItem("tuesday.conversationId", state.conversationId);
    els.lblConv.textContent = `CONV ${state.conversationId.slice(0, 8)}`;
    els.messages.replaceChildren();
    els.desktopImg.hidden = true;
    els.desktopPh.hidden = false;
    setWorkspacePill("none", state.workspace.provider);
    appendMessage(
      "system",
      "New conversation established. Workspace access stays off until requested."
    );
    loadMemory();
    loadApprovals();
    toast("New conversation ready");
    els.input.focus();
  }

  async function startNewConversation() {
    if (state.streaming) state.abort?.abort();
    if (["running", "starting"].includes(state.workspace.status)) {
      const proceed = await confirmModal(
        "Stop this conversation's remote workspace before beginning a new session?<br><span class='hl'>Workspace files are retained.</span>"
      );
      if (!proceed) return;
      await stopWorkspace();
    }
    establishNewConversation();
  }

  function updateBubble(el, text, { done = false } = {}) {
    const bubble = el.querySelector(".bubble");
    bubble.textContent = text;
    if (done) el.classList.remove("streaming");
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function setWorkspacePill(status, provider) {
    state.workspace.status = status || "none";
    state.workspace.provider = provider || state.workspace.provider;
    els.pillWs.dataset.state = state.workspace.status;
    els.lblWs.textContent = `WS · ${state.workspace.status}`;
    els.desktopMeta.textContent = `provider: ${state.workspace.provider} · status: ${state.workspace.status}`;
    updateHudStats();
  }

  function updateHudStats() {
    // Cosmetic HUD meters driven by session signals (not real game stats)
    const hp = state.health?.status === "ok" ? 100 : 40;
    const mp = state.streaming ? 72 : 90;
    const cpuMap = {
      running: 55,
      starting: 80,
      error: 95,
      unavailable: 30,
      stopped: 10,
      none: 5,
    };
    const cpu = state.streaming ? 70 : cpuMap[state.workspace.status] ?? 8;
    els.barHp.style.width = `${hp}%`;
    els.barMp.style.width = `${mp}%`;
    els.barCpu.style.width = `${cpu}%`;
    els.valHp.textContent = `${hp}/100`;
    els.valMp.textContent = `${mp}/100`;
    els.valCpu.textContent = `${cpu}%`;
    els.sStr.textContent = state.health?.capabilities?.nvidia ? "48" : "24";
    els.sVit.textContent = "27";
    els.sAgi.textContent = state.streaming ? "41" : "27";
    els.sInt.textContent = state.health?.capabilities?.mock_model ? "18" : "42";
    els.sPer.textContent = "27";
    const level = Math.min(99, 1 + Math.floor(state.msgCount / 4));
    els.statLevel.textContent = String(level).padStart(2, "0");
    els.statAp.textContent = String(Math.max(0, 12 - (state.msgCount % 13)));
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    if (!res.ok) {
      if (res.status === 401) showAuthGate();
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = j.detail?.message || j.detail || JSON.stringify(j);
      } catch (_) {}
      throw new Error(detail || `HTTP ${res.status}`);
    }
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res;
  }

  function showAuthGate() {
    if (!els.authGate) return;
    els.authGate.hidden = false;
    setTimeout(() => els.authToken?.focus(), 0);
  }

  function hideAuthGate() {
    if (!els.authGate) return;
    els.authGate.hidden = true;
    if (els.authToken) els.authToken.value = "";
    if (els.authError) els.authError.textContent = "";
  }

  async function ensureAuthenticated() {
    const status = await api("/v1/auth/status");
    if (!status.auth_required || status.authenticated) {
      hideAuthGate();
      return true;
    }
    showAuthGate();
    return false;
  }

  async function authenticate(token) {
    try {
      await api("/v1/auth/session", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      hideAuthGate();
      await bootProtected();
    } catch (error) {
      els.authError.textContent = error.message || "Authentication failed";
      els.authToken.select();
    }
  }

  async function loadHealth() {
    try {
      const h = await api("/health");
      state.health = h;
      const caps = h.capabilities || {};
      if (caps.mock_model) {
        els.lblModel.textContent = "MODEL mock";
      } else if (caps.nvidia) {
        els.lblModel.textContent = "MODEL nemotron";
      } else {
        els.lblModel.textContent = "MODEL —";
      }
      setWorkspacePill(state.workspace.status, caps.sandbox_provider || "—");
      updateHudStats();
    } catch (e) {
      toast(`Health check failed: ${e.message}`, "error");
    }
  }

  async function refreshWorkspace() {
    try {
      const st = await api(`/v1/conversations/${state.conversationId}/workspace`);
      setWorkspacePill(st.status, st.provider);
      if (st.status === "running") {
        // optional auto-shot once
      }
    } catch (e) {
      /* ignore cold start */
    }
  }

  async function startWorkspace() {
    try {
      const st = await api(`/v1/conversations/${state.conversationId}/workspace/start`, {
        method: "POST",
        body: "{}",
      });
      setWorkspacePill(st.status, st.provider);
      if (st.status === "running") {
        toast("Workspace online");
        await grabScreenshot();
      } else {
        toast(st.message || `Workspace ${st.status}`, st.status === "unavailable" ? "error" : "info");
      }
    } catch (e) {
      toast(String(e.message || e), "error");
      setWorkspacePill("error", state.workspace.provider);
    }
  }

  async function stopWorkspace() {
    try {
      const st = await api(`/v1/conversations/${state.conversationId}/workspace/stop`, {
        method: "POST",
        body: "{}",
      });
      setWorkspacePill(st.status || "stopped", st.provider);
      els.desktopImg.hidden = true;
      els.desktopPh.hidden = false;
      toast("Workspace stopped");
    } catch (e) {
      toast(String(e.message || e), "error");
    }
  }

  async function grabScreenshot() {
    try {
      const url = `/v1/conversations/${state.conversationId}/workspace/screenshot?t=${Date.now()}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Screenshot ${res.status}`);
      const blob = await res.blob();
      const obj = URL.createObjectURL(blob);
      if (els.desktopImg.src) URL.revokeObjectURL(els.desktopImg.src);
      els.desktopImg.src = obj;
      els.desktopImg.hidden = false;
      els.desktopPh.hidden = true;
      setWorkspacePill("running", state.workspace.provider);
    } catch (e) {
      toast(`Screenshot: ${e.message}`, "error");
    }
  }

  async function loadMemory() {
    try {
      const data = await api("/v1/memory");
      const entries = data.entries || [];
      if (!entries.length) {
        els.memoryList.textContent = "No entries";
        return;
      }
      els.memoryList.innerHTML = "";
      for (const e of entries.slice(0, 20)) {
        const div = document.createElement("div");
        div.className = "mem-item";
        const heading = document.createElement("strong");
        heading.textContent = `${e.kind}${e.key ? " · " + e.key : ""}`;
        div.append(heading, document.createElement("br"), document.createTextNode(String(e.content).slice(0, 120)));
        els.memoryList.appendChild(div);
      }
    } catch (e) {
      els.memoryList.textContent = "Memory unavailable";
    }
  }

  async function loadApprovals() {
    try {
      const data = await api(
        `/v1/approvals/pending?conversation_id=${encodeURIComponent(state.conversationId)}`
      );
      const approvals = data.approvals || [];
      els.approvalList.replaceChildren();
      if (!approvals.length) {
        els.approvalList.textContent = "No pending actions";
        return;
      }
      for (const approval of approvals) {
        const item = document.createElement("div");
        item.className = "approval-item";
        const summary = document.createElement("span");
        summary.textContent = approval.summary;
        const actions = document.createElement("div");
        actions.className = "approval-actions";
        for (const decision of ["approved", "denied"]) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "ghost";
          button.textContent = decision === "approved" ? "Authorize" : "Deny";
          button.addEventListener("click", async () => {
            button.disabled = true;
            try {
              await api(`/v1/approvals/${approval.id}`, {
                method: "POST",
                body: JSON.stringify({ decision }),
              });
              toast(decision === "approved" ? "Action authorized. Ask TUESDAY to continue." : "Action denied.");
              await loadApprovals();
            } catch (error) {
              toast(error.message, "error");
              button.disabled = false;
            }
          });
          actions.appendChild(button);
        }
        item.append(summary, actions);
        els.approvalList.appendChild(item);
      }
    } catch (error) {
      els.approvalList.textContent = "Approvals unavailable";
    }
  }

  async function uploadAttachment(file) {
    const form = new FormData();
    form.append("conversation_id", state.conversationId);
    form.append("file", file, file.name);
    els.btnAttach.disabled = true;
    try {
      const res = await fetch("/v1/media/attachments", { method: "POST", body: form });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail?.message || payload.detail || `Upload HTTP ${res.status}`);
      }
      const uploaded = await res.json();
      state.pendingAttachments.push(uploaded.path);
      appendMessage("system", `Attachment staged: ${uploaded.filename} (${uploaded.size} bytes)`);
      toast("Attachment ready for the next message");
    } catch (error) {
      if (String(error.message).includes("Authentication")) showAuthGate();
      toast(error.message || String(error), "error");
    } finally {
      els.btnAttach.disabled = false;
      els.fileInput.value = "";
    }
  }

  async function toggleRecording() {
    if (state.recorder?.state === "recording") {
      state.recorder.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      toast("Audio recording is not supported by this client", "error");
      return;
    }
    try {
      state.recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      state.recordChunks = [];
      state.recorder = new MediaRecorder(state.recordingStream);
      state.recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) state.recordChunks.push(event.data);
      });
      state.recorder.addEventListener("stop", transcribeRecording, { once: true });
      state.recorder.start();
      els.btnRecord.setAttribute("aria-pressed", "true");
      els.btnRecord.textContent = "Stop recording";
    } catch (error) {
      toast(`Microphone: ${error.message || error}`, "error");
    }
  }

  async function transcribeRecording() {
    els.btnRecord.setAttribute("aria-pressed", "false");
    els.btnRecord.textContent = "Transcribing…";
    els.btnRecord.disabled = true;
    state.recordingStream?.getTracks().forEach((track) => track.stop());
    const type = state.recorder?.mimeType || "audio/webm";
    const blob = new Blob(state.recordChunks, { type });
    const form = new FormData();
    form.append("file", blob, "recording.webm");
    try {
      const res = await fetch("/v1/media/transcribe", { method: "POST", body: form });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail || `Transcription HTTP ${res.status}`);
      }
      const data = await res.json();
      els.input.value = data.text || "";
      autoGrow();
      els.input.focus();
    } catch (error) {
      toast(error.message || String(error), "error");
    } finally {
      els.btnRecord.disabled = false;
      els.btnRecord.textContent = "Push to talk";
      state.recorder = null;
      state.recordChunks = [];
    }
  }

  async function speakText(text) {
    if (!state.voiceOutput || !text.trim()) return;
    try {
      const res = await fetch("/v1/media/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.slice(0, 5000), format: "mp3" }),
      });
      if (!res.ok) throw new Error(`Voice output HTTP ${res.status}`);
      const url = URL.createObjectURL(await res.blob());
      const audio = new Audio(url);
      audio.addEventListener("ended", () => URL.revokeObjectURL(url), { once: true });
      await audio.play();
    } catch (error) {
      toast(error.message || String(error), "error");
    }
  }

  /* ——— SSE chat ——— */
  async function sendMessage(text) {
    if (!text.trim() || state.streaming) return;
    appendMessage("user", text.trim());
    const attachments = [...state.pendingAttachments];
    state.pendingAttachments = [];
    const promptText = attachments.length
      ? `${text.trim()}\n\nAttachments staged in this conversation workspace:\n${attachments.map((path) => `- ${path}`).join("\n")}`
      : text.trim();
    els.input.value = "";
    autoGrow();

    const assistantEl = appendMessage("assistant", "", { streaming: true });
    let full = "";
    setStreamUI(true);
    state.abort = new AbortController();

    try {
      const res = await fetch("/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({
          conversation_id: state.conversationId,
          messages: [{ role: "user", content: promptText }],
          enable_tools: true,
          task: "chat",
        }),
        signal: state.abort.signal,
      });
      if (!res.ok) throw new Error(`Chat HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n");
        buffer = parts.pop() || "";
        let ev = "message";
        let dataLines = [];
        const flush = () => {
          if (!dataLines.length) return;
          const dataRaw = dataLines.join("\n");
          dataLines = [];
          handleSSE(ev, dataRaw, {
            onDelta: (c) => {
              full += c;
              updateBubble(assistantEl, full);
            },
            onMeta: (d) => {
              if (d.model) els.lblModel.textContent = `MODEL ${String(d.model).slice(0, 28)}`;
              if (d.conversation_id) {
                state.conversationId = d.conversation_id;
                localStorage.setItem("tuesday.conversationId", state.conversationId);
                els.lblConv.textContent = `CONV ${state.conversationId.slice(0, 8)}`;
              }
            },
            onTool: (kind, d) => {
              const label =
                kind === "tool_start"
                  ? `▶ ${d.name}`
                  : `✓ ${d.name}${d.result?.ok === false ? " (err)" : ""}`;
              appendMessage("tool", label + (d.arguments ? `\n${String(d.arguments).slice(0, 200)}` : ""));
              if (kind === "tool_result" && String(d.name || "").startsWith("computer_")) {
                setWorkspacePill("running", state.workspace.provider);
                if (d.result?.approval_required) loadApprovals();
              }
            },
            onWorkspace: () => {
              setWorkspacePill("running", state.workspace.provider);
              grabScreenshot().catch(() => {});
            },
            onError: (m) => {
              toast(m, "error");
              if (!full) full = `Error: ${m}`;
            },
          });
          ev = "message";
        };

        for (const line of parts) {
          if (line.startsWith("event:")) {
            ev = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          } else if (line.trim() === "") {
            flush();
          }
        }
      }
    } catch (e) {
      if (e.name === "AbortError") {
        if (!full) full = "— cancelled —";
      } else {
        toast(String(e.message || e), "error");
        if (!full) full = `Error: ${e.message || e}`;
      }
    } finally {
      updateBubble(assistantEl, full || "…", { done: true });
      setStreamUI(false);
      state.abort = null;
      refreshWorkspace();
      loadMemory();
      loadApprovals();
      if (full && !full.startsWith("Error:")) speakText(full);
    }
  }

  function handleSSE(event, dataRaw, hooks) {
    let data = {};
    try {
      data = JSON.parse(dataRaw);
    } catch {
      data = { content: dataRaw };
    }
    switch (event) {
      case "session":
      case "meta":
        hooks.onMeta(data);
        break;
      case "delta":
        hooks.onDelta(data.content || "");
        break;
      case "tool_start":
        hooks.onTool("tool_start", data);
        break;
      case "tool_result":
        hooks.onTool("tool_result", data);
        break;
      case "workspace":
        hooks.onWorkspace(data);
        break;
      case "error":
        hooks.onError(data.message || "Unknown error");
        break;
      case "done":
        if (data.model) hooks.onMeta({ model: data.model });
        break;
      default:
        break;
    }
  }

  /* Modal helper */
  function confirmModal(bodyText) {
    return new Promise((resolve) => {
      els.modal.hidden = false;
      els.modal.classList.add("open");
      els.modalBody.innerHTML = bodyText;
      const done = (v) => {
        els.modal.classList.remove("open");
        els.modal.hidden = true;
        els.modalYes.onclick = null;
        els.modalNo.onclick = null;
        resolve(v);
      };
      els.modalYes.onclick = () => done(true);
      els.modalNo.onclick = () => done(false);
    });
  }

  function autoGrow() {
    const t = els.input;
    t.style.height = "auto";
    t.style.height = Math.min(160, t.scrollHeight) + "px";
  }

  /* Events */
  els.form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(els.input.value);
  });
  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(els.input.value);
    }
  });
  els.input.addEventListener("input", autoGrow);
  els.btnStop.addEventListener("click", () => state.abort?.abort());
  els.btnNewSession?.addEventListener("click", startNewConversation);
  els.btnMotion?.addEventListener("click", () => {
    setReducedMotion(document.documentElement.dataset.reducedMotion !== "true");
  });

  document.querySelectorAll("[data-panel-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.panelTarget);
      if (!target) return;
      document.querySelectorAll(".rail-button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      target.scrollIntoView({
        behavior: document.documentElement.dataset.reducedMotion === "true" ? "auto" : "smooth",
        block: "nearest",
      });
      if (target.id === "panel-comms") els.input.focus();
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.altKey && event.key.toLowerCase() === "n") {
      event.preventDefault();
      startNewConversation();
    }
    if (event.key === "Escape" && !els.modal.hidden) els.modalNo.click();
  });

  $("#btn-ws-start").addEventListener("click", startWorkspace);
  $("#btn-ws-stop").addEventListener("click", async () => {
    const ok = await confirmModal(
      "Stop the remote workspace for this conversation?<br><span class='hl'>Workspace files are retained.</span>"
    );
    if (ok) stopWorkspace();
  });
  $("#btn-ws-shot").addEventListener("click", grabScreenshot);
  $("#btn-ws-refresh").addEventListener("click", () => {
    refreshWorkspace();
    grabScreenshot().catch(() => {});
  });
  $("#btn-mem-refresh").addEventListener("click", loadMemory);
  els.btnApprovalRefresh.addEventListener("click", loadApprovals);
  els.btnAttach.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", () => {
    const file = els.fileInput.files?.[0];
    if (file) uploadAttachment(file);
  });
  els.btnRecord.addEventListener("click", toggleRecording);
  els.btnVoice.addEventListener("click", () => {
    state.voiceOutput = !state.voiceOutput;
    localStorage.setItem("tuesday.voiceOutput", String(state.voiceOutput));
    els.btnVoice.setAttribute("aria-pressed", String(state.voiceOutput));
    els.btnVoice.textContent = state.voiceOutput ? "Voice output on" : "Voice output off";
  });
  els.authForm.addEventListener("submit", (event) => {
    event.preventDefault();
    authenticate(els.authToken.value);
  });

  async function bootProtected() {
    if (!state.protectedBooted) {
      state.protectedBooted = true;
      appendMessage(
        "system",
        "TUESDAY online. Workspace access is isolated per conversation and starts only when requested."
      );
      setInterval(loadApprovals, 12_000);
    }
    await Promise.all([refreshWorkspace(), loadMemory(), loadApprovals()]);
    updateHudStats();
  }

  async function boot() {
    setReducedMotion(motionPreference);
    els.btnVoice.setAttribute("aria-pressed", String(state.voiceOutput));
    els.btnVoice.textContent = state.voiceOutput ? "Voice output on" : "Voice output off";
    updateClock();
    setInterval(updateClock, 1000);
    await loadHealth();
    try {
      if (await ensureAuthenticated()) await bootProtected();
    } catch (error) {
      toast(`Startup failed: ${error.message || error}`, "error");
    }
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/service-worker.js").catch(() => {});
    }
  }

  boot();
})();
