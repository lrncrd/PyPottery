document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  const TAG_STYLE = {
    info: { icon: '<i class="bi bi-info-circle"></i>', color: "#38bdf8" },
    success: { icon: '<i class="bi bi-check-circle"></i>', color: "#34d399" },
    error: { icon: '<i class="bi bi-x-circle"></i>', color: "#f87171" },
    warning: { icon: '<i class="bi bi-exclamation-triangle"></i>', color: "#fbbf24" },
    progress: { icon: '<i class="bi bi-arrow-repeat"></i>', color: "#c084fc" },
  };

  const els = {
    splashScreen: document.getElementById("splash-screen"),
    splashBar: document.getElementById("splash-bar"),
    splashStatus: document.getElementById("splash-status"),
    installerModal: document.getElementById("installer-modal"),
    installerLogoBox: document.getElementById("installer-logo-box"),
    installerAppName: document.getElementById("installer-app-name"),
    installerAppSubtitle: document.getElementById("installer-app-subtitle"),
    installerRingBar: document.getElementById("installer-ring-bar"),
    installerPercentText: document.getElementById("installer-percent-text"),
    installerStatusTitle: document.getElementById("installer-status-title"),
    installerStatusDetail: document.getElementById("installer-status-detail"),
    installerConsoleLog: document.getElementById("installer-console-log"),
    btnInstallerClose: document.getElementById("btn-installer-close"),
    btnInstallerDone: document.getElementById("btn-installer-done"),
    btnInstallerLaunch: document.getElementById("btn-installer-launch"),
    stepDownload: document.getElementById("step-download"),
    stepExtract: document.getElementById("step-extract"),
    stepFinalize: document.getElementById("step-finalize"),
    step1Label: document.getElementById("step-1-label"),
    step2Label: document.getElementById("step-2-label"),
    step3Label: document.getElementById("step-3-label"),
    conn1: document.getElementById("conn-1"),
    conn2: document.getElementById("conn-2"),
    launcherVersion: document.getElementById("launcher-version"),
    systemStatusChip: document.getElementById("system-status-chip"),
    hwOs: document.querySelector('[data-hw="os"]'),
    hwCpu: document.querySelector('[data-hw="cpu"]'),
    hwRam: document.querySelector('[data-hw="ram"]'),
    ramBarFill: document.getElementById("ram-bar-fill"),
    hwGpu: document.querySelector('[data-hw="gpu"]'),
    hwPytorch: document.querySelector('[data-hw="pytorch"]'),
    environmentPanel: document.getElementById("environment-panel"),
    envStatusText: document.getElementById("env-status-text"),
    envVerifiedCheck: document.getElementById("env-verified-check"),
    envProgressBar: document.getElementById("env-progress-bar"),
    envProgressLabel: document.getElementById("env-progress-label"),
    btnEnvSetup: document.getElementById("btn-env-setup"),
    btnEnvVerify: document.getElementById("btn-env-verify"),
    appsList: document.getElementById("apps-list"),
    consoleLog: document.getElementById("console-log"),
    consoleDot: document.getElementById("console-dot"),
    consoleLastMsg: document.getElementById("console-last-msg"),
    consoleBody: document.getElementById("console-body"),
    btnConsoleToggle: document.getElementById("btn-console-toggle"),
    btnConsoleClear: document.getElementById("btn-console-clear"),
    btnConsoleCopy: document.getElementById("btn-console-copy"),
    logCount: document.getElementById("log-count"),
    modelCacheList: document.getElementById("model-cache-list"),
    modelCacheTotal: document.getElementById("model-cache-total"),
    btnModelsRefresh: document.getElementById("btn-models-refresh"),
    btnCheckUpdates: document.getElementById("btn-check-updates"),
    btnQuit: document.getElementById("btn-quit"),
    btnFloatingGuide: document.getElementById("btn-floating-guide"),
    guideModal: document.getElementById("guide-modal"),
    btnGuideClose: document.getElementById("btn-guide-close"),
    driverWarningBanner: document.getElementById("banner-driver-warning"),
    driverWarningText: document.getElementById("banner-driver-warning-text"),
    launcherUpdateBanner: document.getElementById("banner-launcher-update"),
    launcherUpdateText: document.getElementById("banner-launcher-update-text"),
    btnLauncherUpdateConfirm: document.getElementById("btn-launcher-update-confirm"),
    launcherUpdateProgressBanner: document.getElementById("banner-launcher-update-progress"),
    launcherUpdateProgressText: document.getElementById("banner-launcher-update-progress-text"),
    launcherUpdateProgressBar: document.getElementById("launcher-update-progress-bar"),
    toastContainer: document.getElementById("toast-container"),
    quoteDayBadge: document.getElementById("quote-day-badge"),
    heroQuoteText: document.getElementById("hero-quote-text"),
    btnNextQuote: document.getElementById("btn-next-quote"),
  };

  const store = {
    apps: {},             // app_id -> app dict
    appOrder: [],          // preserves display order
    downloadProgress: {},  // app_id -> {stage, message, percent}
    pendingUpdateVersion: null,
    envExists: false,
    consoleEntries: [],    // raw log entries
    activeInstallerAppId: null,
    installerLogs: {},     // app_id -> log string lines array
    activeLogFilter: "all",
    models: [],            // cached model entries (see /api/models)
  };

  const MODEL_KIND_ICON = {
    "huggingface-model": "🤗",
    "model-dir": "📦",
    "checkpoint-file": "🧠",
  };

  function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0 MB";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = bytes;
    let i = 0;
    while (value >= 1024 && i < units.length - 1) {
      value /= 1024;
      i++;
    }
    return `${value.toFixed(i === 0 || value >= 100 ? 0 : 1)} ${units[i]}`;
  }

  // ---- Toast Notification System ----

  function showToast(message, type = "info", duration = 4000) {
    if (!els.toastContainer) return;
    
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    const icons = {
      info: '<i class="bi bi-info-circle-fill"></i>',
      success: '<i class="bi bi-check-circle-fill"></i>',
      warning: '<i class="bi bi-exclamation-triangle-fill"></i>',
      error: '<i class="bi bi-x-circle-fill"></i>'
    };
    const icon = icons[type] || '<i class="bi bi-info-circle-fill"></i>';
    
    toast.innerHTML = `
      <span class="toast-icon">${icon}</span>
      <span class="toast-message">${escapeHtml(message)}</span>
    `;
    
    els.toastContainer.appendChild(toast);
    
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px) scale(0.95)";
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ---- Console Logs & Filtering ----

  function appendConsoleEntry(entry) {
    store.consoleEntries.push(entry);
    updateLogCount();

    if (store.activeLogFilter !== "all" && entry.tag !== store.activeLogFilter) {
      return;
    }

    renderSingleLogLine(entry);
  }

  function renderSingleLogLine(entry) {
    const style = TAG_STYLE[entry.tag] || TAG_STYLE.info;
    const line = document.createElement("div");
    line.className = "console-line";
    line.innerHTML = `
      <span class="console-timestamp">[${escapeHtml(entry.timestamp)}]</span>
      <span style="color: ${style.color}">${style.icon} ${escapeHtml(entry.message)}</span>
    `;
    
    els.consoleLog.appendChild(line);
    els.consoleLog.scrollTop = els.consoleLog.scrollHeight;

    els.consoleLastMsg.textContent = entry.message;
    const dotClass = ["error", "success", "warning"].includes(entry.tag) ? entry.tag : "info";
    els.consoleDot.className = `console-dot ${dotClass}`;
  }

  function renderConsoleLogs() {
    els.consoleLog.innerHTML = "";
    const filtered = store.consoleEntries.filter(
      e => store.activeLogFilter === "all" || e.tag === store.activeLogFilter
    );
    filtered.forEach(renderSingleLogLine);
    updateLogCount();
  }

  function updateLogCount() {
    if (els.logCount) {
      els.logCount.textContent = `${store.consoleEntries.length} entries`;
    }
  }

  // Log filter chips listener
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      store.activeLogFilter = chip.dataset.filter;
      renderConsoleLogs();
    });
  });

  if (els.btnConsoleToggle) {
    els.btnConsoleToggle.addEventListener("click", () => {
      const isHidden = els.consoleBody.classList.toggle("hidden");
      els.btnConsoleToggle.textContent = isHidden ? "Show Logs" : "Hide Logs";
    });
  }

  if (els.btnConsoleClear) {
    els.btnConsoleClear.addEventListener("click", () => {
      store.consoleEntries = [];
      els.consoleLog.innerHTML = "";
      els.consoleLastMsg.textContent = "Console cleared";
      updateLogCount();
      showToast("Console logs cleared", "info", 2000);
    });
  }

  if (els.btnConsoleCopy) {
    els.btnConsoleCopy.addEventListener("click", () => {
      const text = store.consoleEntries
        .map(e => `[${e.timestamp}] [${e.tag.toUpperCase()}] ${e.message}`)
        .join("\n");
      navigator.clipboard.writeText(text).then(() => {
        showToast("Logs copied to clipboard!", "success", 2500);
      });
    });
  }

  // ---- Hardware Panel ----

  function renderHardware(hw) {
    if (!hw) return;
    if (els.hwOs) els.hwOs.textContent = `${hw.os_name} (${hw.architecture})`;
    if (els.hwCpu) els.hwCpu.textContent = `${hw.cpu_name} (${hw.cpu_cores} cores)`;
    
    if (els.hwRam) {
      els.hwRam.textContent = `${hw.ram_total_gb.toFixed(1)} GB Total (${hw.ram_available_gb.toFixed(1)} GB Free)`;
      if (els.ramBarFill && hw.ram_total_gb > 0) {
        const usedPercent = Math.min(100, Math.max(0, ((hw.ram_total_gb - hw.ram_available_gb) / hw.ram_total_gb) * 100));
        els.ramBarFill.style.width = `${usedPercent}%`;
      }
    }

    let gpuText;
    if (hw.cuda_available && hw.gpus && hw.gpus.length) {
      gpuText = `${hw.gpus[0].name} (CUDA ${hw.cuda_version})`;
    } else if (hw.mps_available) {
      gpuText = "Apple Silicon (MPS Acceleration)";
    } else if (hw.rocm_available) {
      gpuText = "AMD GPU (ROCm Acceleration)";
    } else {
      gpuText = "CPU Mode";
    }
    if (els.hwGpu) els.hwGpu.textContent = gpuText;

    let pytorchText;
    if (hw.installed_pytorch_version) {
      pytorchText = `PyTorch v${hw.installed_pytorch_version} (${hw.installed_pytorch_device || 'Active'})`;
    } else {
      pytorchText = `Not Installed (Recommended: ${hw.recommended_pytorch_variant || 'CPU'})`;
    }
    if (els.hwPytorch) els.hwPytorch.textContent = pytorchText;

    if (!hw.cuda_compatible && hw.driver_warning) {
      showDriverWarning(hw.driver_warning);
    }
  }

  function showDriverWarning(message) {
    if (!els.driverWarningBanner) return;
    els.driverWarningText.textContent = message;
    els.driverWarningBanner.classList.remove("hidden");
  }

  // ---- Environment Panel ----

  function renderEnvStatus(exists) {
    store.envExists = exists;
    if (!els.envStatusText) return;

    els.envStatusText.classList.remove("ready", "error");
    if (exists) {
      els.envStatusText.innerHTML = '<i class="bi bi-check2-circle"></i> Active & Ready';
      els.envStatusText.classList.add("ready");
      els.btnEnvSetup.innerHTML = "<span>Reinstall Environment</span>";
      els.envProgressBar.style.width = "100%";
      els.envProgressLabel.textContent = "Virtualenv configured successfully.";

      if (els.environmentPanel) els.environmentPanel.classList.remove("env-needs-setup");
      if (els.envVerifiedCheck) els.envVerifiedCheck.classList.remove("hidden");
      if (els.btnEnvVerify) els.btnEnvVerify.classList.remove("hidden");
    } else {
      els.envStatusText.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Not Configured';
      els.envStatusText.classList.add("error");
      els.btnEnvSetup.innerHTML = "<span>Setup Environment</span>";
      els.envProgressBar.style.width = "0%";
      els.envProgressLabel.textContent = "Required dependencies need installation.";

      if (els.environmentPanel) els.environmentPanel.classList.add("env-needs-setup");
      if (els.envVerifiedCheck) els.envVerifiedCheck.classList.add("hidden");
      if (els.btnEnvVerify) els.btnEnvVerify.classList.add("hidden");
    }
    renderApps();
  }

  function renderEnvProgress(progress) {
    if (els.envProgressBar) {
      els.envProgressBar.style.width = `${progress.percent}%`;
      els.envProgressLabel.textContent = progress.message;
      els.envProgressLabel.style.color = progress.is_error ? "var(--danger)" : "var(--text-dim)";
    }
    handleEnvProgressEvent(progress);
  }

  if (els.btnEnvSetup) {
    els.btnEnvSetup.addEventListener("click", () => {
      openEnvInstallerModal();
      showToast("Setting up Python environment...", "info", 3000);
      fetch("/api/env/setup", { method: "POST" });
    });
  }

  if (els.btnEnvVerify) {
    els.btnEnvVerify.addEventListener("click", () => {
      showToast("Verifying Python environment dependencies...", "info", 3000);
      fetch("/api/env/verify", { method: "POST" });
    });
  }

  // ---- Model Cache Panel ----

  function modelRowHtml(entry) {
    const icon = MODEL_KIND_ICON[entry.kind] || "📦";
    const meta = entry.used_by ? `Used by ${entry.used_by}` : "Shared cache";
    return `
      <div class="model-row" data-path="${escapeHtml(entry.path)}">
        <span class="model-row-icon">${icon}</span>
        <div class="model-row-info">
          <span class="model-row-name">${escapeHtml(entry.name)}</span>
          <span class="model-row-meta">${escapeHtml(meta)}</span>
        </div>
        <span class="model-row-size">${formatBytes(entry.size_bytes)}</span>
        <button class="btn btn-danger-soft btn-icon-only" data-action="delete-model" data-path="${escapeHtml(entry.path)}" title="Delete this cached model">🗑️</button>
      </div>`;
  }

  function renderModelCache(snapshot) {
    if (!els.modelCacheList || !snapshot) return;
    store.models = snapshot.entries || [];

    if (els.modelCacheTotal) {
      els.modelCacheTotal.textContent = `${formatBytes(snapshot.total_size_bytes)} total`;
    }

    if (!store.models.length) {
      els.modelCacheList.innerHTML = '<p class="apps-empty">No models downloaded yet. They\'ll appear here once a tool downloads one.</p>';
      return;
    }
    els.modelCacheList.innerHTML = store.models.map(modelRowHtml).join("");
  }

  async function fetchModels() {
    try {
      const res = await fetch("/api/models");
      renderModelCache(await res.json());
    } catch (e) {
      // Card just keeps showing its last known state.
    }
  }

  if (els.btnModelsRefresh) {
    els.btnModelsRefresh.addEventListener("click", () => {
      fetchModels();
      showToast("Model cache refreshed", "info", 2000);
    });
  }

  if (els.modelCacheList) {
    els.modelCacheList.addEventListener("click", (evt) => {
      const btn = evt.target.closest('button[data-action="delete-model"]');
      if (!btn || btn.disabled) return;

      const path = btn.dataset.path;
      const entry = store.models.find((m) => m.path === path);
      const label = entry ? entry.name : path;

      const confirmed = confirm(
        `Delete "${label}" from the model cache?\n\nThis frees disk space now, but ${entry && entry.used_by ? entry.used_by : "the owning app"} will need to download it again next time it's used.`
      );
      if (!confirmed) return;

      btn.disabled = true;
      fetch("/api/models/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.success) {
            renderModelCache(data);
            showToast(`Deleted ${label} — ${formatBytes(entry ? entry.size_bytes : 0)} freed`, "success", 4000);
          } else {
            showToast(`Failed to delete ${label}: ${data.error || "unknown error"}`, "error", 4500);
            btn.disabled = false;
          }
        })
        .catch(() => {
          showToast(`Failed to delete ${label}`, "error", 4500);
          btn.disabled = false;
        });
    });
  }

  // ---- App Cards Rendering ----

  function actionState(app) {
    if (app.is_running) return { label: "Stop App", cls: "btn-danger", action: "stop" };
    if (app.installed) return { label: "Launch App", cls: "btn-success", action: "launch" };
    if (app.developer_mode) return { label: "Checkout Not Found", cls: "btn-primary", action: "none" };
    return { label: "Install", cls: "btn-primary", action: "install" };
  }

  function statusBadge(app) {
    if (app.is_running) return { text: "RUNNING", cls: "running", dot: "●" };
    if (app.installed) return { text: "INSTALLED", cls: "ready", dot: "●" };
    return { text: "NOT INSTALLED", cls: "", dot: "○" };
  }

  function appCardHtml(app) {
    const action = actionState(app);
    const badge = statusBadge(app);
    const isRunning = app.is_running;
    const isLocked = !store.envExists;
    
    const versionText = app.installed_version
      ? `v${app.installed_version}${app.update_available ? " • Update Available" : ""}`
      : "";

    const logoHtml = app.logo_path
      ? `<img src="/assets/${app.logo_path}" alt="${escapeHtml(app.name)}" onerror="this.replaceWith(document.createTextNode('${app.icon || '🏺'}'))">`
      : `<span class="emoji-icon">${app.icon || '🏺'}</span>`;

    const dl = store.downloadProgress[app.id];
    let progressHtml = "";
    if (dl && dl.stage !== "complete" && dl.stage !== "error") {
      progressHtml = `
        <div class="app-progress-box clickable" data-action="open_installer" data-app-id="${app.id}" title="Click to open detailed installation view" style="cursor:pointer;">
          <div class="progress-info-line">
            <span>${escapeHtml(dl.message || "Downloading...")}</span>
            <span>${Math.round(dl.percent || 0)}%</span>
          </div>
          <div class="progress-track-app">
            <div class="progress-fill-app" style="width:${dl.percent || 0}%"></div>
          </div>
        </div>`;
    } else if (dl && dl.stage === "error") {
      progressHtml = `
        <div class="app-progress-box" style="border-color: rgba(225,29,72,0.3)">
          <div class="progress-info-line" style="color:var(--danger)">
            <span><i class="bi bi-exclamation-circle-fill"></i> ${escapeHtml(dl.message || "Installation error")}</span>
          </div>
        </div>`;
    }

    const openBrowserBtn = isRunning
      ? `<a href="http://localhost:${app.port}" target="_blank" class="btn btn-outline btn-sm" title="Open web interface in new tab"><i class="bi bi-box-arrow-up-right"></i> Open Web</a>`
      : "";

    const updateBtnHtml = app.update_available
      ? `<button class="btn btn-outline btn-icon-only" data-action="update" data-app-id="${app.id}" title="${app.installed ? 'Update Application' : 'Install application first to enable updates'}" ${!app.installed || isLocked ? 'disabled' : ''}><i class="bi bi-arrow-up-circle"></i></button>`
      : "";

    const badgePillHtml = isLocked && !app.installed
      ? `<span class="status-badge-pill locked"><i class="bi bi-lock-fill"></i> REQUIRES ENV</span>`
      : `<span class="status-badge-pill ${badge.cls}">${badge.dot} ${badge.text}</span>`;

    const lockBannerHtml = isLocked && !app.installed
      ? `<div class="card-lock-banner"><i class="bi bi-lock-fill"></i> Setup Python Environment to unlock</div>`
      : "";

    return `
      <div class="app-card ${isRunning ? 'running-card' : ''} ${isLocked ? 'card-locked' : ''}" data-app-id="${app.id}">
        <div class="app-card-top">
          <div class="app-logo-box">
            ${logoHtml}
          </div>
          <div class="app-info-body">
            <div class="app-title-line">
              <span class="app-name">${escapeHtml(app.name)}</span>
              ${badgePillHtml}
            </div>
            <p class="app-desc">${escapeHtml(app.description)}</p>
            <div class="app-chips">
              <span class="chip"><i class="bi bi-ethernet"></i> Port ${app.port}</span>
              <span class="chip"><i class="bi bi-memory"></i> ${app.min_ram_gb}GB RAM</span>
              ${app.requires_gpu ? `<span class="chip chip-gpu"><i class="bi bi-gpu-card"></i> GPU</span>` : ""}
              ${app.developer_mode ? `<span class="chip chip-dev" title="Running from the local git checkout at the repo root - install/update disabled"><i class="bi bi-code-slash"></i> DEV MODE</span>` : ""}
              ${versionText ? `<span class="chip">${escapeHtml(versionText)}</span>` : ""}
            </div>
            ${lockBannerHtml}
          </div>
        </div>

        <div class="app-card-bottom">
          ${progressHtml}
          <div class="app-actions-row">
            <div class="app-actions-left">
              <button class="btn ${action.cls} main-action" data-action="${action.action}" data-app-id="${app.id}"
                ${isLocked
                  ? "disabled title='Please set up the Python Environment first to unlock'"
                  : action.action === 'none'
                    ? `disabled title='Clone ${escapeHtml(app.repo_name)} into the repo root to enable it in developer mode'`
                    : ""}>
                ${action.action === 'launch' ? '<i class="bi bi-play-fill"></i> ' : action.action === 'stop' ? '<i class="bi bi-stop-fill"></i> ' : action.action === 'none' ? '<i class="bi bi-search"></i> ' : '<i class="bi bi-download"></i> '}${action.label}
              </button>
              ${openBrowserBtn}
            </div>
            <div class="app-actions-right">
              ${updateBtnHtml}
              <button class="btn btn-quiet btn-icon-only" data-action="folder" data-app-id="${app.id}" title="Open Application Directory" ${!app.installed || isLocked ? "disabled" : ""}><i class="bi bi-folder2-open"></i></button>
            </div>
          </div>
        </div>
      </div>`;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function renderApps() {
    if (!store.appOrder.length) {
      els.appsList.innerHTML = '<p class="apps-empty">No applications configured in launcher.</p>';
      return;
    }
    els.appsList.innerHTML = store.appOrder.map((id) => appCardHtml(store.apps[id])).join("");
  }

  function setApps(appsArray) {
    store.apps = {};
    store.appOrder = [];
    for (const app of appsArray) {
      store.apps[app.id] = app;
      store.appOrder.push(app.id);
    }
    renderApps();
  }

  function updateSingleApp(app) {
    const previous = store.apps[app.id];
    store.apps[app.id] = app;
    if (!store.appOrder.includes(app.id)) {
      store.appOrder.push(app.id);
    }

    // Toast feedback on status changes
    if (previous) {
      if (!previous.is_running && app.is_running) {
        showToast(`${app.name} is now running on port ${app.port}`, "success", 5000);
      } else if (previous.is_running && !app.is_running) {
        showToast(`${app.name} has been stopped`, "info", 3000);
      } else if (!previous.installed && app.installed) {
        showToast(`${app.name} installed successfully!`, "success", 5000);
      }
    }

    renderApps();
  }

  // ---- Interactive Installer Hub Controller ----

  function openInstallerModal(appId) {
    const app = store.apps[appId];
    if (!app) return;

    store.activeInstallerAppId = appId;
    if (!store.installerLogs[appId]) store.installerLogs[appId] = [];

    if (els.installerAppName) els.installerAppName.textContent = `Installing ${app.name}`;
    if (els.installerAppSubtitle) els.installerAppSubtitle.textContent = app.description || "Archaeological Suite Tool";

    if (els.installerLogoBox) {
      if (app.logo_path) {
        els.installerLogoBox.innerHTML = `<img src="/assets/${app.logo_path}" alt="${escapeHtml(app.name)}">`;
      } else {
        els.installerLogoBox.innerHTML = `<i class="bi bi-box-seam" style="font-size: 1.6rem; color: var(--primary);"></i>`;
      }
    }

    setStepperLabels("Download", "Unpack & Setup", "Ready");
    resetInstallerStepper();
    updateInstallerProgressRing(0);

    if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Starting installation...";
    if (els.installerStatusDetail) els.installerStatusDetail.textContent = "Initializing connection to repository...";
    
    if (els.btnInstallerLaunch) els.btnInstallerLaunch.classList.add("hidden");
    if (els.btnInstallerDone) els.btnInstallerDone.classList.add("hidden");
    if (els.btnInstallerClose) els.btnInstallerClose.classList.remove("hidden");

    renderInstallerLogs(appId);
    if (els.installerModal) els.installerModal.classList.remove("hidden");
  }

  function openEnvInstallerModal() {
    store.activeInstallerAppId = "env";
    if (!store.installerLogs["env"]) store.installerLogs["env"] = [];

    if (els.installerAppName) els.installerAppName.textContent = "Setting Up Python Environment";
    if (els.installerAppSubtitle) els.installerAppSubtitle.textContent = "Configuring isolated virtualenv, PyTorch backend & AI libraries";
    if (els.installerLogoBox) els.installerLogoBox.innerHTML = `<i class="bi bi-terminal-split" style="font-size: 1.6rem; color: var(--primary);"></i>`;

    setStepperLabels("Virtualenv", "PyTorch & AI", "Ready");
    resetInstallerStepper();
    updateInstallerProgressRing(0);

    if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Preparing Python environment...";
    if (els.installerStatusDetail) els.installerStatusDetail.textContent = "Starting environment manager...";
    
    if (els.btnInstallerLaunch) els.btnInstallerLaunch.classList.add("hidden");
    if (els.btnInstallerDone) els.btnInstallerDone.classList.add("hidden");
    if (els.btnInstallerClose) els.btnInstallerClose.classList.remove("hidden");

    renderInstallerLogs("env");
    if (els.installerModal) els.installerModal.classList.remove("hidden");
  }

  function closeInstallerModal() {
    if (els.installerModal) els.installerModal.classList.add("hidden");
    store.activeInstallerAppId = null;
  }

  // ---- Workflow Guide Modal Controller ----
  if (els.btnFloatingGuide && els.guideModal) {
    els.btnFloatingGuide.addEventListener("click", () => {
      els.guideModal.classList.remove("hidden");
    });
  }

  if (els.btnGuideClose && els.guideModal) {
    els.btnGuideClose.addEventListener("click", () => {
      els.guideModal.classList.add("hidden");
    });
  }

  if (els.guideModal) {
    els.guideModal.addEventListener("click", (e) => {
      if (e.target === els.guideModal) {
        els.guideModal.classList.add("hidden");
      }
    });
  }

  function setStepperLabels(l1, l2, l3) {
    if (els.step1Label) els.step1Label.textContent = l1;
    if (els.step2Label) els.step2Label.textContent = l2;
    if (els.step3Label) els.step3Label.textContent = l3;
  }

  function resetInstallerStepper() {
    [els.stepDownload, els.stepExtract, els.stepFinalize].forEach((el) => {
      if (el) el.className = "step-item";
    });
    [els.conn1, els.conn2].forEach((el) => {
      if (el) el.className = "step-connector";
    });
    if (els.stepDownload) els.stepDownload.classList.add("active");
  }

  function updateInstallerProgressRing(percent) {
    if (!els.installerRingBar) return;
    const circumference = 289.02;
    const offset = circumference - (Math.min(100, Math.max(0, percent)) / 100) * circumference;
    els.installerRingBar.style.strokeDashoffset = offset;
    if (els.installerPercentText) els.installerPercentText.textContent = `${Math.round(percent)}%`;
  }

  function addInstallerLogLine(appId, message) {
    if (!message) return;
    if (!store.installerLogs[appId]) store.installerLogs[appId] = [];

    const logs = store.installerLogs[appId];
    if (logs.length > 0) {
      const last = logs[logs.length - 1];
      if (last.endsWith(message)) return;
    }

    const timestamp = new Date().toLocaleTimeString();
    const formattedLine = `[${timestamp}] ${message}`;
    logs.push(formattedLine);
    if (logs.length > 250) logs.shift();

    if (store.activeInstallerAppId === appId && els.installerConsoleLog) {
      const div = document.createElement("div");
      div.textContent = formattedLine;
      els.installerConsoleLog.appendChild(div);
      while (els.installerConsoleLog.children.length > 250) {
        els.installerConsoleLog.removeChild(els.installerConsoleLog.firstChild);
      }
      els.installerConsoleLog.scrollTop = els.installerConsoleLog.scrollHeight;
    }
  }

  function renderInstallerLogs(appId) {
    if (!els.installerConsoleLog) return;
    const logs = store.installerLogs[appId] || [];
    els.installerConsoleLog.innerHTML = "";
    const frag = document.createDocumentFragment();
    logs.forEach((line) => {
      const div = document.createElement("div");
      div.textContent = line;
      frag.appendChild(div);
    });
    els.installerConsoleLog.appendChild(frag);
    els.installerConsoleLog.scrollTop = els.installerConsoleLog.scrollHeight;
  }

  function handleInstallerProgressEvent(data) {
    const appId = data.app_id;
    const stage = data.stage;
    const percent = data.percent || 0;
    const message = data.message || "";

    addInstallerLogLine(appId, message);

    if (store.activeInstallerAppId === appId) {
      updateInstallerProgressRing(percent);
      if (els.installerStatusDetail) els.installerStatusDetail.textContent = message;

      if (stage === "downloading") {
        if (percent >= 100) {
          if (els.stepDownload) els.stepDownload.className = "step-item complete";
          if (els.conn1) els.conn1.className = "step-connector complete";
          if (els.stepExtract) els.stepExtract.className = "step-item active";
          if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Download complete. Preparing extraction...";
        } else {
          if (els.stepDownload) els.stepDownload.className = "step-item active";
          if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Downloading application archive...";
        }
      } else if (stage === "extracting") {
        if (els.stepDownload) els.stepDownload.className = "step-item complete";
        if (els.conn1) els.conn1.className = "step-connector complete";
        if (els.stepExtract) els.stepExtract.className = "step-item active";
        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Extracting & configuring files...";
      } else if (stage === "complete") {
        updateInstallerProgressRing(100);
        if (els.stepDownload) els.stepDownload.className = "step-item complete";
        if (els.conn1) els.conn1.className = "step-connector complete";
        if (els.stepExtract) els.stepExtract.className = "step-item complete";
        if (els.conn2) els.conn2.className = "step-connector complete";
        if (els.stepFinalize) els.stepFinalize.className = "step-item complete";

        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Installation Complete! 🎉";
        if (els.btnInstallerLaunch) {
          els.btnInstallerLaunch.classList.remove("hidden");
          els.btnInstallerLaunch.onclick = () => {
            closeInstallerModal();
            fetch(`/api/apps/${appId}/launch`, { method: "POST" });
          };
        }
        if (els.btnInstallerDone) {
          els.btnInstallerDone.classList.remove("hidden");
          els.btnInstallerDone.textContent = "✨ Done";
          els.btnInstallerDone.onclick = closeInstallerModal;
        }
      } else if (stage === "error") {
        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Installation Error ⚠️";
        if (els.btnInstallerDone) {
          els.btnInstallerDone.classList.remove("hidden");
          els.btnInstallerDone.textContent = "Close";
          els.btnInstallerDone.onclick = closeInstallerModal;
        }
      }
    }
  }

  function handleEnvProgressEvent(progress) {
    const stage = progress.stage;
    const percent = progress.percent || 0;
    const message = progress.message || "";

    addInstallerLogLine("env", message);

    if (store.activeInstallerAppId === "env") {
      updateInstallerProgressRing(percent);
      if (els.installerStatusDetail) els.installerStatusDetail.textContent = message;

      if (stage === "venv") {
        if (els.stepDownload) els.stepDownload.className = "step-item active";
        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Setting up Python virtual environment...";
      } else if (stage === "pytorch" || stage === "dependencies") {
        if (els.stepDownload) els.stepDownload.className = "step-item complete";
        if (els.conn1) els.conn1.className = "step-connector complete";
        if (els.stepExtract) els.stepExtract.className = "step-item active";
        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Installing PyTorch & AI packages...";
      } else if (stage === "complete" || percent >= 100) {
        if (els.stepDownload) els.stepDownload.className = "step-item complete";
        if (els.conn1) els.conn1.className = "step-connector complete";
        if (els.stepExtract) els.stepExtract.className = "step-item complete";
        if (els.conn2) els.conn2.className = "step-connector complete";
        if (els.stepFinalize) els.stepFinalize.className = "step-item complete";

        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Python Environment Configured! 🎉";
        if (els.btnInstallerClose) els.btnInstallerClose.classList.remove("hidden");
        if (els.btnInstallerDone) {
          els.btnInstallerDone.classList.remove("hidden");
          els.btnInstallerDone.textContent = "✨ Complete Setup";
          els.btnInstallerDone.onclick = closeInstallerModal;
        }
      } else if (progress.is_error) {
        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Environment Setup Error ⚠️";
        if (els.btnInstallerClose) els.btnInstallerClose.classList.remove("hidden");
        if (els.btnInstallerDone) {
          els.btnInstallerDone.classList.remove("hidden");
          els.btnInstallerDone.textContent = "Close";
          els.btnInstallerDone.onclick = closeInstallerModal;
        }
      }
    }
  }

  if (els.btnInstallerClose) els.btnInstallerClose.addEventListener("click", closeInstallerModal);
  if (els.btnInstallerMinimize) els.btnInstallerMinimize.addEventListener("click", closeInstallerModal);

  els.appsList.addEventListener("click", (evt) => {
    const btn = evt.target.closest("[data-action]");
    if (!btn || btn.disabled) return;
    const action = btn.dataset.action;
    const appId = btn.dataset.appId;
    const app = store.apps[appId];

    if (action === "open_installer") {
      openInstallerModal(appId);
    } else if (action === "install") {
      openInstallerModal(appId);
      showToast(`Starting installation of ${app ? app.name : appId}...`, "info", 4000);
      fetch(`/api/apps/${appId}/install`, { method: "POST" });
    } else if (action === "update") {
      if (!app || !app.installed) return;
      openInstallerModal(appId);
      showToast(`Updating ${app ? app.name : appId}...`, "info", 4000);
      fetch(`/api/apps/${appId}/update`, { method: "POST" });
    } else if (action === "launch") {
      showToast(`Launching ${app ? app.name : appId}...`, "info", 3000);
      fetch(`/api/apps/${appId}/launch`, { method: "POST" });
    } else if (action === "stop") {
      showToast(`Stopping ${app ? app.name : appId}...`, "warning", 3000);
      fetch(`/api/apps/${appId}/stop`, { method: "POST" });
    } else if (action === "folder") {
      fetch(`/api/apps/${appId}/folder`, { method: "POST" });
    }
  });

  // ---- Header & Global Actions ----

  if (els.btnCheckUpdates) {
    els.btnCheckUpdates.addEventListener("click", () => {
      showToast("Checking for updates...", "info", 3000);
      fetch("/api/updates/check", { method: "POST" });
    });
  }

  if (els.btnQuit) {
    els.btnQuit.addEventListener("click", () => {
      if (!confirm("Quit PyPottery Suite Launcher? All running applications will be stopped.")) return;
      fetch("/api/shutdown", { method: "POST" }).finally(() => {
        document.body.innerHTML = `
          <div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:sans-serif;color:#1c1917;background:#fbf9f5;text-align:center;">
            <h2 style="font-size:1.8rem;margin-bottom:12px;color:#c2410c;">Launcher Terminated 🏺</h2>
            <p style="color:#78716c;">PyPottery Suite launcher has been closed. You can close this browser tab.</p>
          </div>`;
      });
    });
  }

  document.querySelectorAll("[data-dismiss]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.dismiss);
      if (target) target.classList.add("hidden");
    });
  });

  // ---- Daily Day-of-Week & Time-of-Day Greetings ----

  const LATE_NIGHT_GREETINGS = [
    "Working late tonight? Don't forget to take a break!",
    "Burning the midnight oil? Remember to get some rest!",
    "Late night session! Working hard tonight?",
    "Still up? Make sure to get some sleep soon!",
  ];

  const EARLY_MORNING_GREETINGS = [
    "Up already? You're an early bird today!",
    "Up before the sun? Good morning, early bird!",
    "Early start today! Hope you have a wonderful day ahead.",
    "Up bright and early! Have a great start to your day.",
  ];

  const DAY_GREETINGS = {
    0: { // Sunday
      morning: "Good morning! Happy Sunday — have a peaceful day ahead.",
      afternoon: "Good afternoon! Happy Sunday — enjoy the rest of your weekend.",
      evening: "Good evening! Happy Sunday — getting ready for the week ahead.",
    },
    1: { // Monday
      morning: "Good morning! Happy Monday — have a great week ahead.",
      afternoon: "Good afternoon! Happy Monday — hope your week is off to a great start.",
      evening: "Good evening! Happy Monday — hope you had a productive day.",
    },
    2: { // Tuesday
      morning: "Good morning! Happy Tuesday — hope you have a wonderful day.",
      afternoon: "Good afternoon! Happy Tuesday — hope your day is going well.",
      evening: "Good evening! Happy Tuesday — have a relaxing evening.",
    },
    3: { // Wednesday
      morning: "Good morning! Happy Wednesday — have a great day ahead.",
      afternoon: "Good afternoon! Happy Wednesday — halfway through the week!",
      evening: "Good evening! Happy Wednesday — have a pleasant evening.",
    },
    4: { // Thursday
      morning: "Good morning! Happy Thursday — almost the weekend!",
      afternoon: "Good afternoon! Happy Thursday — almost Friday!",
      evening: "Good evening! Happy Thursday — Friday is just around the corner.",
    },
    5: { // Friday
      morning: "Good morning! Happy Friday — have a fantastic day!",
      afternoon: "Good afternoon! Happy Friday — have a great weekend ahead!",
      evening: "Good evening! Happy Friday — time to enjoy the weekend!",
    },
    6: { // Saturday
      morning: "Good morning! Happy Saturday — enjoy your weekend!",
      afternoon: "Good afternoon! Happy Saturday — enjoy the rest of your day.",
      evening: "Good evening! Happy Saturday — have a wonderful night.",
    },
  };

  function renderDailyGreeting() {
    const msgEl = document.getElementById("hero-greeting-msg");
    if (!msgEl) return;

    const now = new Date();
    const dayIdx = now.getDay();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const timeDecimal = hours + minutes / 60;

    let greeting = "";

    // Very late night: 23:00 - 04:59
    if (timeDecimal >= 23 || timeDecimal < 5) {
      const idx = now.getDate() % LATE_NIGHT_GREETINGS.length;
      greeting = LATE_NIGHT_GREETINGS[idx];
    }
    // Very early morning: 05:00 - 07:29
    else if (timeDecimal >= 5 && timeDecimal < 7.5) {
      const idx = now.getDate() % EARLY_MORNING_GREETINGS.length;
      greeting = EARLY_MORNING_GREETINGS[idx];
    }
    // Standard Morning: 07:30 - 11:59
    else if (timeDecimal >= 7.5 && timeDecimal < 12) {
      greeting = DAY_GREETINGS[dayIdx]?.morning || "Good morning! Have a wonderful day.";
    }
    // Afternoon: 12:00 - 17:59
    else if (timeDecimal >= 12 && timeDecimal < 18) {
      greeting = DAY_GREETINGS[dayIdx]?.afternoon || "Good afternoon! Hope your day is going well.";
    }
    // Evening: 18:00 - 22:59
    else {
      greeting = DAY_GREETINGS[dayIdx]?.evening || "Good evening! Have a pleasant night.";
    }

    msgEl.textContent = greeting;
  }

  // ---- Live Wikiquote Pop-Culture Quotes ----

  function renderPopQuote(data) {
    const textEl = document.getElementById("pop-quote-text");
    const sourceEl = document.getElementById("pop-quote-source");
    const quoteContainer = document.getElementById("hero-pop-quote");
    if (!textEl || !sourceEl || !data || !data.quote) return;

    if (quoteContainer) {
      quoteContainer.style.opacity = "0";
      setTimeout(() => {
        textEl.textContent = `“${data.quote}”`;
        sourceEl.textContent = `— ${data.source}`;
        quoteContainer.style.opacity = "1";
      }, 150);
    } else {
      textEl.textContent = `“${data.quote}”`;
      sourceEl.textContent = `— ${data.source}`;
    }
  }

  async function fetchWikiquote(forceRefresh = false) {
    try {
      const url = forceRefresh ? "/api/quote/wikiquote?refresh=1" : "/api/quote/wikiquote";
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        renderPopQuote(data);
      }
    } catch (e) {
      // Ignore network errors
    }
  }

  const quoteEl = document.getElementById("hero-pop-quote");
  if (quoteEl) {
    quoteEl.style.cursor = "pointer";
    quoteEl.setAttribute("title", "Click for another quote from Wikiquote");
    quoteEl.addEventListener("click", () => fetchWikiquote(true));
  }


  if (els.btnLauncherUpdateConfirm) {
    els.btnLauncherUpdateConfirm.addEventListener("click", () => {
      if (!store.pendingUpdateVersion) return;
      if (els.launcherUpdateBanner) els.launcherUpdateBanner.classList.add("hidden");
      if (els.launcherUpdateProgressBanner) els.launcherUpdateProgressBanner.classList.remove("hidden");
      fetch("/api/launcher/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: store.pendingUpdateVersion }),
      });
    });
  }

  // ---- Server-Sent Events (SSE) Dispatch ----

  function updateAppCardProgressInPlace(data) {
    const card = document.querySelector(`.app-card[data-app-id="${data.app_id}"]`);
    if (!card) return;
    const fill = card.querySelector(".progress-fill-app");
    const infoLine = card.querySelector(".progress-info-line span:nth-child(2)");
    const infoMsg = card.querySelector(".progress-info-line span:nth-child(1)");
    if (fill) fill.style.width = `${data.percent || 0}%`;
    if (infoLine) infoLine.textContent = `${Math.round(data.percent || 0)}%`;
    if (infoMsg) infoMsg.textContent = data.message || "";
  }

  function handleEvent(data) {
    switch (data.type) {
      case "console":
        appendConsoleEntry(data);
        break;
      case "hardware":
        renderHardware(data.hardware);
        break;
      case "driver_warning":
        showDriverWarning(data.message);
        break;
      case "env_status":
        renderEnvStatus(!!data.exists);
        break;
      case "env_progress":
        renderEnvProgress(data);
        break;
      case "apps_refresh":
        setApps(data.apps);
        break;
      case "app_status":
        updateSingleApp(data.app);
        break;
      case "models_refresh":
        renderModelCache(data);
        break;
      case "download_progress":
        store.downloadProgress[data.app_id] = data;
        handleInstallerProgressEvent(data);
        updateAppCardProgressInPlace(data);
        if (data.stage === "complete" || data.stage === "error") {
          renderApps();
          setTimeout(() => {
            delete store.downloadProgress[data.app_id];
            renderApps();
          }, 3000);
        }
        break;
      case "launcher_update_available":
        store.pendingUpdateVersion = data.update.latest_version;
        if (els.launcherUpdateText) {
          els.launcherUpdateText.textContent = `A new version of PyPottery Launcher (${data.update.latest_version}) is available.`;
        }
        if (els.launcherUpdateBanner) els.launcherUpdateBanner.classList.remove("hidden");
        showToast(`Update available: PyPottery Launcher v${data.update.latest_version}`, "info", 6000);
        break;
      case "launcher_update_progress":
        if (els.launcherUpdateProgressBanner) els.launcherUpdateProgressBanner.classList.remove("hidden");
        if (els.launcherUpdateProgressText) els.launcherUpdateProgressText.textContent = data.message;
        if (els.launcherUpdateProgressBar) {
          els.launcherUpdateProgressBar.style.width = `${data.percent || 0}%`;
          els.launcherUpdateProgressBar.classList.toggle("error", !!data.error);
        }
        break;
      default:
        break;
    }
  }

  function connectEvents() {
    const source = new EventSource("/api/events");
    source.onmessage = (evt) => {
      try {
        handleEvent(JSON.parse(evt.data));
      } catch (e) {
        // ignore malformed events
      }
    };
    source.onerror = () => {
      // EventSource auto-reconnects
    };
  }

  // ---- Splash Screen Controller ----

  function updateSplash(percent, statusMessage) {
    if (els.splashBar) els.splashBar.style.width = `${percent}%`;
    if (els.splashStatus) els.splashStatus.textContent = statusMessage;
  }

  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function hideSplash() {
    if (!els.splashScreen) return;
    updateSplash(100, "Ready!");
    await delay(500);
    els.splashScreen.classList.add("splash-fade-out");
    await delay(700);
    els.splashScreen.style.display = "none";
  }

  // ---- Initial State Hydration ----

  async function init() {
    renderDailyGreeting();
    const startTime = Date.now();
    updateSplash(25, "Initializing system components...");
    await delay(350);

    updateSplash(55, "Detecting hardware & environment...");

    try {
      const res = await fetch("/api/state");
      const state = await res.json();

      await delay(400);
      updateSplash(85, "Loading archaeological tools & models...");
      if (els.launcherVersion) els.launcherVersion.textContent = `v${state.launcher_version}`;
      if (state.hardware) renderHardware(state.hardware);
      if (state.pop_quote) {
        renderPopQuote(state.pop_quote);
      } else {
        fetchWikiquote();
      }
      renderEnvStatus(!!(state.env && state.env.exists));
      setApps(state.apps || []);
      (state.console || []).forEach(appendConsoleEntry);
      if (state.models) renderModelCache(state.models);
    } catch (e) {
      // Backend hydration fallback
      fetchWikiquote();
    }

    connectEvents();

    // Ensure splash screen stays visible for at least 1.8 seconds total
    const elapsed = Date.now() - startTime;
    const minSplashDuration = 1800;
    if (elapsed < minSplashDuration) {
      await delay(minSplashDuration - elapsed);
    }

    await hideSplash();
  }

  init();
});

