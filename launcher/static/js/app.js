document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  const TAG_STYLE = {
    info: { icon: '<i class="bi bi-info-circle" aria-hidden="true"></i>' },
    success: { icon: '<i class="bi bi-check-circle" aria-hidden="true"></i>' },
    error: { icon: '<i class="bi bi-x-circle" aria-hidden="true"></i>' },
    warning: { icon: '<i class="bi bi-exclamation-triangle" aria-hidden="true"></i>' },
    progress: { icon: '<i class="bi bi-arrow-repeat" aria-hidden="true"></i>' },
  };

  const els = {
    splashScreen: document.getElementById("splash-screen"),
    splashBar: document.getElementById("splash-bar"),
    splashStatus: document.getElementById("splash-status"),
    terminatedScreen: document.getElementById("terminated-screen"),
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
    systemDashboardPanel: document.getElementById("system-dashboard-panel"),
    btnDashboardToggle: document.getElementById("btn-dashboard-toggle"),
    hardwarePanel: document.getElementById("hardware-panel"),
    environmentPanel: document.getElementById("environment-panel"),
    envStatusText: document.getElementById("env-status-text"),
    envVerifiedCheck: document.getElementById("env-verified-check"),
    envProgressBar: document.getElementById("env-progress-bar"),
    envProgressLabel: document.getElementById("env-progress-label"),
    btnEnvSetup: document.getElementById("btn-env-setup"),
    btnEnvVerify: document.getElementById("btn-env-verify"),
    envVariantToggle: document.getElementById("env-variant-toggle"),
    chkGpuVariant: document.getElementById("chk-gpu-variant"),
    envVariantHint: document.getElementById("env-variant-hint"),
    envVariantToggleFirst: document.getElementById("env-variant-toggle-first"),
    chkGpuVariantFirst: document.getElementById("chk-gpu-variant-first"),
    envVariantHintFirst: document.getElementById("env-variant-hint-first"),
    gpuVariantModal: document.getElementById("gpu-variant-modal"),
    gpuVariantModalTitle: document.getElementById("gpu-variant-modal-title"),
    gpuVariantModalMessage: document.getElementById("gpu-variant-modal-message"),
    btnGpuVariantCancel: document.getElementById("btn-gpu-variant-cancel"),
    btnGpuVariantConfirm: document.getElementById("btn-gpu-variant-confirm"),
    appsList: document.getElementById("apps-list"),
    consolePanel: document.getElementById("console-panel"),
    consoleLog: document.getElementById("console-log"),
    consoleDot: document.getElementById("console-dot"),
    consoleLastMsg: document.getElementById("console-last-msg"),
    consoleBody: document.getElementById("console-body"),
    consoleBodyWrapper: document.getElementById("console-body-wrapper"),
    btnConsoleToggle: document.getElementById("btn-console-toggle"),
    btnConsoleClear: document.getElementById("btn-console-clear"),
    btnConsoleCopy: document.getElementById("btn-console-copy"),
    btnOpenLogs: document.getElementById("btn-open-logs"),
    btnAboutDataFolder: document.getElementById("btn-about-data-folder"),
    logCount: document.getElementById("log-count"),
    connectionLostBanner: document.getElementById("banner-connection-lost"),
    btnConnectionRetry: document.getElementById("btn-connection-retry"),
    modelCacheList: document.getElementById("model-cache-list"),
    modelCacheTotal: document.getElementById("model-cache-total"),
    btnModelsRefresh: document.getElementById("btn-models-refresh"),
    btnCheckUpdates: document.getElementById("btn-check-updates"),
    btnQuit: document.getElementById("btn-quit"),
    btnChangelog: document.getElementById("btn-changelog"),
    changelogModal: document.getElementById("changelog-modal"),
    btnChangelogClose: document.getElementById("btn-changelog-close"),
    changelogModalBody: document.getElementById("changelog-modal-body"),
    btnAbout: document.getElementById("btn-about"),
    aboutModal: document.getElementById("about-modal"),
    btnAboutClose: document.getElementById("btn-about-close"),
    aboutVersionBadge: document.getElementById("about-version-badge"),
    disclaimerModal: document.getElementById("disclaimer-modal"),
    btnAcceptDisclaimer: document.getElementById("btn-accept-disclaimer"),
    firstSetupModal: document.getElementById("first-setup-modal"),
    btnFirstSetupStart: document.getElementById("btn-first-setup-start"),
    driverWarningBanner: document.getElementById("banner-driver-warning"),
    driverWarningText: document.getElementById("banner-driver-warning-text"),
    launcherUpdateBanner: document.getElementById("banner-launcher-update"),
    launcherUpdateBadge: document.getElementById("banner-launcher-update-badge"),
    launcherUpdateText: document.getElementById("banner-launcher-update-text"),
    launcherUpdateNotes: document.getElementById("banner-launcher-update-notes"),
    btnLauncherUpdateNotesToggle: document.getElementById("btn-launcher-update-notes-toggle"),
    btnLauncherUpdateConfirm: document.getElementById("btn-launcher-update-confirm"),
    launcherUpdateProgressBanner: document.getElementById("banner-launcher-update-progress"),
    launcherUpdateProgressText: document.getElementById("banner-launcher-update-progress-text"),
    launcherUpdateProgressPct: document.getElementById("banner-launcher-update-progress-pct"),
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
    developerMode: false,
    envExists: false,
    isEnvSetupMandatory: false,
    consoleEntries: [],    // raw log entries
    activeInstallerAppId: null,
    installerLogs: {},     // app_id -> log string lines array
    activeLogFilter: "all",
    models: [],            // cached model entries (see /api/models)
    hw: null,               // last hardware payload received via SSE
    pytorchVariantTouched: false, // true once the user manually toggles the GPU checkbox
    envState: null,         // full /api/env/status payload: status, ready, reason...
    envReady: false,        // environment finished installing and still runs
    lastEnvSetupVariant: null, // what the user last asked for, so Retry doesn't change it
    envSetupFailed: false,  // lets the mandatory first-run modal be dismissed after an error
    lastEventAt: Date.now(), // watchdog for a silently dropped SSE connection
    connectionLost: false,
  };

  // Every fetch in this file goes through here. Bare fetch() calls silently
  // swallow both HTTP errors and a dead server, which is how "click Launch,
  // nothing happens, forever" used to look.
  async function api(path, { method = "GET", body = null, quiet = false } = {}) {
    let response;
    try {
      response = await fetch(path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      if (!quiet) showToast("Cannot reach the launcher - is it still running?", "error", 6000);
      markConnectionLost();
      return { ok: false, status: 0, data: null, error: String(err) };
    }

    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      data = null;
    }

    if (!response.ok || (data && data.success === false)) {
      const message = (data && data.error) || `Request failed (${response.status})`;
      if (!quiet) {
        showToast(message, response.status === 409 ? "warning" : "error", 6000);
      }
      return { ok: false, status: response.status, data, error: message };
    }

    return { ok: true, status: response.status, data, error: null };
  }

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
    const tag = entry.tag || "info";
    const style = TAG_STYLE[tag] || TAG_STYLE.info;
    const line = document.createElement("div");
    line.className = "console-line";
    line.innerHTML = `
      <span class="console-timestamp">[${escapeHtml(entry.timestamp)}]</span>
      <span class="console-msg console-msg-${escapeHtml(tag)}">${style.icon} <span>${escapeHtml(entry.message)}</span></span>
    `;
    
    els.consoleLog.appendChild(line);
    els.consoleLog.scrollTop = els.consoleLog.scrollHeight;

    els.consoleLastMsg.textContent = entry.message;
    const dotClass = ["error", "success", "warning"].includes(tag) ? tag : "info";
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
  document.querySelectorAll(".log-filter-chips .filter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".log-filter-chips .filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      store.activeLogFilter = chip.dataset.filter;
      renderConsoleLogs();
    });
  });

  if (els.btnConsoleToggle) {
    els.btnConsoleToggle.addEventListener("click", () => {
      const panel = els.consolePanel || document.getElementById("console-panel");
      const isOpen = panel ? panel.classList.toggle("is-open") : false;
      els.btnConsoleToggle.setAttribute("aria-expanded", String(isOpen));
      els.btnConsoleToggle.innerHTML = isOpen
        ? '<i class="bi bi-chevron-up" aria-hidden="true"></i> Hide Logs'
        : '<i class="bi bi-chevron-down" aria-hidden="true"></i> Show Logs';
      if (isOpen && els.consoleLog) {
        setTimeout(() => {
          els.consoleLog.scrollTop = els.consoleLog.scrollHeight;
        }, 100);
      }
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

  // ---- Collapsible Dashboard Panel ----

  function initCollapsiblePanels() {
    const dashPanel = els.systemDashboardPanel || document.getElementById("system-dashboard-panel");
    const dashToggle = els.btnDashboardToggle || document.getElementById("btn-dashboard-toggle");
    if (dashPanel && dashToggle) {
      const isCollapsed = localStorage.getItem("pypottery_dashboard_collapsed") === "true";
      if (isCollapsed) {
        dashPanel.classList.add("panel-collapsed");
        dashToggle.setAttribute("aria-expanded", "false");
      }
      dashToggle.addEventListener("click", () => {
        const collapsed = dashPanel.classList.toggle("panel-collapsed");
        dashToggle.setAttribute("aria-expanded", !collapsed);
        localStorage.setItem("pypottery_dashboard_collapsed", collapsed);
      });
    }
  }

  // ---- Hardware Panel ----

  function renderHardware(hw) {
    if (!hw) return;
    store.hw = hw;
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

    updateVariantToggleUI(hw);
  }

  // GPU (CUDA) vs CPU-only PyTorch toggle - Windows only. Lets the user opt
  // out of the heavy CUDA download; not offered as a way to force CUDA onto
  // hardware that doesn't have a CUDA-capable GPU.
  function updateVariantToggleUI(hw) {
    const isWindows = hw.os_name === "Windows";
    const checkboxes = [els.chkGpuVariant, els.chkGpuVariantFirst];
    const wrappers = [els.envVariantToggle, els.envVariantToggleFirst];
    const hints = [els.envVariantHint, els.envVariantHintFirst];

    wrappers.forEach((el) => {
      if (el) el.classList.toggle("hidden", !isWindows);
    });
    if (!isWindows) return;

    const hintText = hw.cuda_available
      ? ""
      : "No CUDA-capable GPU detected - GPU acceleration isn't available on this machine.";

    checkboxes.forEach((cb, i) => {
      if (!cb) return;
      cb.disabled = !hw.cuda_available;
      if (!store.pytorchVariantTouched) {
        if (store.envExists) {
          cb.checked = isCudaInstalled();
        } else {
          cb.checked = !!hw.cuda_available;
        }
      }
      if (hints[i]) hints[i].textContent = hintText;
    });
  }

  function showDriverWarning(message) {
    if (!els.driverWarningBanner) return;
    els.driverWarningText.textContent = message;
    els.driverWarningBanner.classList.remove("hidden");
  }

  // ---- Environment Panel ----

  function renderEnvStatus(envState) {
    // Back-compat: a couple of call sites still pass a bare boolean.
    if (typeof envState === "boolean") {
      envState = { status: envState ? "ready" : "absent", ready: envState };
    }
    if (!envState) {
      envState = { status: "absent", ready: false, reason: "No Python environment yet" };
    }
    const isDevMode = Boolean(store.developerMode || envState.developer_mode);
    if (isDevMode) {
      store.developerMode = true;
    }
    store.envState = envState;
    store.envExists = isDevMode || Boolean(envState.ready); // legacy alias, some code still reads this
    store.envReady = isDevMode || Boolean(envState.ready);

    const isReady = envState.status === "ready" || isDevMode;
    const needsSetup = !isDevMode && envState.status === "absent";
    const needsRepair = !isDevMode && (envState.status === "broken" || envState.status === "incomplete");

    if (els.firstSetupModal) {
      if (isReady || isDevMode) {
        els.firstSetupModal.classList.add("hidden");
      } else {
        const disclaimerOpen = els.disclaimerModal && !els.disclaimerModal.classList.contains("hidden");
        const installerOpen = els.installerModal && !els.installerModal.classList.contains("hidden");
        if (!disclaimerOpen && !installerOpen) {
          els.firstSetupModal.classList.remove("hidden");
        }
      }
    }

    if (!els.envStatusText) return;

    els.envStatusText.classList.remove("ready", "error", "warning");
    if (isDevMode) {
      els.envStatusText.innerHTML = '<i class="bi bi-code-slash"></i> System Python (Dev)';
      els.envStatusText.classList.add("ready");
      if (els.btnEnvSetup) els.btnEnvSetup.classList.add("hidden");
      if (els.envProgressBar) els.envProgressBar.style.width = "100%";
      if (els.envProgressLabel) els.envProgressLabel.textContent = "Using terminal Python environment";

      if (els.environmentPanel) els.environmentPanel.classList.remove("env-needs-setup");
      if (els.envVerifiedCheck) els.envVerifiedCheck.classList.remove("hidden");
      if (els.btnEnvVerify) els.btnEnvVerify.classList.remove("hidden");
    } else if (isReady) {
      els.envStatusText.innerHTML = '<i class="bi bi-check2-circle"></i> Active & Ready';
      els.envStatusText.classList.add("ready");
      if (els.btnEnvSetup) {
        els.btnEnvSetup.classList.remove("hidden");
        els.btnEnvSetup.innerHTML = "<span>Reinstall Environment</span>";
      }
      if (els.envProgressBar) els.envProgressBar.style.width = "100%";
      if (els.envProgressLabel) els.envProgressLabel.textContent = "Virtualenv configured successfully.";

      if (els.environmentPanel) els.environmentPanel.classList.remove("env-needs-setup");
      if (els.envVerifiedCheck) els.envVerifiedCheck.classList.remove("hidden");
      if (els.btnEnvVerify) els.btnEnvVerify.classList.remove("hidden");
    } else if (needsRepair) {
      els.envStatusText.innerHTML = '<i class="bi bi-tools"></i> Incomplete - needs repair';
      els.envStatusText.classList.add("warning");
      if (els.btnEnvSetup) {
        els.btnEnvSetup.classList.remove("hidden");
        els.btnEnvSetup.innerHTML = "<span>Repair Environment</span>";
      }
      if (els.envProgressBar) els.envProgressBar.style.width = "0%";
      els.envProgressLabel.textContent = envState.reason || "The environment needs to be rebuilt.";

      if (els.environmentPanel) els.environmentPanel.classList.add("env-needs-setup");
      if (els.envVerifiedCheck) els.envVerifiedCheck.classList.add("hidden");
      if (els.btnEnvVerify) els.btnEnvVerify.classList.add("hidden");
    } else {
      els.envStatusText.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Not Configured';
      els.envStatusText.classList.add("error");
      if (els.btnEnvSetup) {
        els.btnEnvSetup.classList.remove("hidden");
        els.btnEnvSetup.innerHTML = "<span>Setup Environment</span>";
      }
      if (els.envProgressBar) els.envProgressBar.style.width = "0%";
      els.envProgressLabel.textContent = "Required dependencies need installation.";

      if (els.environmentPanel) els.environmentPanel.classList.add("env-needs-setup");
      if (els.envVerifiedCheck) els.envVerifiedCheck.classList.add("hidden");
      if (els.btnEnvVerify) els.btnEnvVerify.classList.add("hidden");
    }
    renderApps();
    if (store.hw && !store.pytorchVariantTouched) {
      updateVariantToggleUI(store.hw);
    }
  }

  function renderEnvProgress(progress) {
    if (els.envProgressBar) {
      els.envProgressBar.style.width = `${progress.percent}%`;
      els.envProgressLabel.textContent = progress.message;
      els.envProgressLabel.style.color = progress.is_error ? "var(--danger)" : "var(--text-dim)";
    }
    handleEnvProgressEvent(progress);
  }

  // Generic themed confirm modal (replaces native alert()/confirm() so it
  // matches the rest of the app's dialogs). One "confirm" and one "cancel"
  // button; callbacks are rewired per-use since only one instance exists.
  // Originally built just for the GPU/CPU variant prompts, now reused for
  // anything needing a themed yes/no (e.g. uninstalling an app) - the
  // element ids kept their original "gpu-variant" names to avoid an
  // unrelated HTML/CSS rename, but the function itself is fully generic.
  let _gpuVariantModalHandlers = null;
  function showConfirmModal({ title, message, confirmText, cancelText = "Go Back", danger = false, onConfirm, onCancel }) {
    if (!els.gpuVariantModal) return;
    els.gpuVariantModalTitle.textContent = title;
    els.gpuVariantModalMessage.textContent = message;
    els.btnGpuVariantConfirm.textContent = confirmText;
    els.btnGpuVariantCancel.textContent = cancelText;
    els.btnGpuVariantConfirm.classList.toggle("btn-primary", !danger);
    els.btnGpuVariantConfirm.classList.toggle("btn-danger", danger);
    els.gpuVariantModal.classList.remove("hidden");

    if (_gpuVariantModalHandlers) {
      els.btnGpuVariantConfirm.removeEventListener("click", _gpuVariantModalHandlers.confirm);
      els.btnGpuVariantCancel.removeEventListener("click", _gpuVariantModalHandlers.cancel);
    }
    const close = () => els.gpuVariantModal.classList.add("hidden");
    const confirmHandler = () => { close(); if (onConfirm) onConfirm(); };
    const cancelHandler = () => { close(); if (onCancel) onCancel(); };
    _gpuVariantModalHandlers = { confirm: confirmHandler, cancel: cancelHandler };
    els.btnGpuVariantConfirm.addEventListener("click", confirmHandler);
    els.btnGpuVariantCancel.addEventListener("click", cancelHandler);
  }
  const showGpuVariantModal = showConfirmModal;

  function isCudaInstalled() {
    if (store.developerMode) return true;

    // Check device string from hardware detector (e.g. "CUDA (NVIDIA GeForce RTX 4070 Laptop GPU)")
    const dev = String(store.hw?.installed_pytorch_device || "").toUpperCase();
    if (dev.includes("CUDA") || dev.includes("NVIDIA") || dev.includes("GEFORCE") || dev.includes("RTX") || dev.includes("GTX")) {
      return true;
    }

    // Check PyTorch version string (e.g. "2.4.0+cu124", "2.5.1+cu121")
    const ver = String(store.hw?.installed_pytorch_version || "").toLowerCase();
    if (ver.includes("+cu") || ver.includes("cu12") || ver.includes("cu11")) {
      return true;
    }

    // Check environment state variant from marker (e.g. "cu124", "cu126", "cu128")
    const variant = String(store.envState?.variant || "").toLowerCase();
    if (variant.startsWith("cu") || variant === "auto") {
      return true;
    }

    // If previously selected GPU in this session and environment is ready
    if (store.lastEnvSetupVariant === true && store.envReady) {
      return true;
    }

    return false;
  }

  function isCpuOnlyInstalled() {
    if (store.developerMode) return false;
    if (!store.envExists) return false;
    if (isCudaInstalled()) return false;

    const dev = String(store.hw?.installed_pytorch_device || "").toUpperCase();
    const variant = String(store.envState?.variant || "").toLowerCase();
    const ver = String(store.hw?.installed_pytorch_version || "").toLowerCase();

    return variant === "cpu" || dev === "CPU" || (ver.length > 0 && !ver.includes("cu"));
  }

  function getWantsGpu() {
    const cb = els.chkGpuVariant || els.chkGpuVariantFirst;
    return cb ? cb.checked : true;
  }

  function setGpuCheckboxes(checked) {
    if (els.chkGpuVariant) els.chkGpuVariant.checked = checked;
    if (els.chkGpuVariantFirst) els.chkGpuVariantFirst.checked = checked;
  }

  function postEnvSetup(wantsGpu) {
    // Never send a literal "cuda"/cuXXX string - the backend already owns
    // the CUDA-version-to-index-url mapping. The frontend only ever sends a
    // binary "force CPU" vs "let the backend auto-detect" signal.
    // Remembered so Retry-after-error can reuse the same choice instead of
    // silently reverting to "auto" (a plain retry used to post no body at
    // all, which meant a CPU-only pick got upgraded to CUDA behind the
    // user's back the moment something else failed).
    store.lastEnvSetupVariant = wantsGpu;
    return api("/api/env/setup", { method: "POST", body: { pytorch_variant: wantsGpu ? "auto" : "cpu" } });
  }

  function startEnvSetup(wantsGpu) {
    openEnvInstallerModal(false);
    showToast("Setting up Python environment...", "info", 3000);
    postEnvSetup(wantsGpu);
  }

  // Keep the panel and first-setup-modal GPU checkboxes mirrored - both
  // exist in the DOM at all times, just conditionally hidden (see
  // updateVariantToggleUI above).
  [els.chkGpuVariant, els.chkGpuVariantFirst].forEach((cb) => {
    if (!cb) return;
    cb.addEventListener("change", () => {
      store.pytorchVariantTouched = true;
      const checked = cb.checked;
      setGpuCheckboxes(checked);

      // In developer mode, do not prompt for installation/reinstallation
      if (store.developerMode) return;

      // If CUDA is ALREADY installed, turning the toggle on simply restores the state —
      // do not prompt to reinstall what is already installed!
      if (isCudaInstalled()) return;

      // Only prompt if PyTorch is genuinely installed as CPU-only and user re-checks GPU
      if (checked && store.envExists && isCpuOnlyInstalled()) {
        showGpuVariantModal({
          title: "Enable GPU Acceleration",
          message: "PyTorch is currently installed CPU-only. Reinstall now to enable GPU-accelerated (CUDA) PyTorch.",
          confirmText: "Reinstall with CUDA",
          onConfirm: () => startEnvSetup(true),
          onCancel: () => setGpuCheckboxes(false),
        });
      }
    });
  });

  if (els.btnFirstSetupStart) {
    els.btnFirstSetupStart.addEventListener("click", () => {
      if (els.firstSetupModal) els.firstSetupModal.classList.add("hidden");
      openEnvInstallerModal(true);
      showToast("Starting Python environment setup...", "info", 3000);
      postEnvSetup(getWantsGpu());
    });
  }

  if (els.btnEnvSetup) {
    els.btnEnvSetup.addEventListener("click", () => {
      if (store.developerMode) {
        showToast("Developer mode is active; using terminal Python environment.", "info", 3000);
        return;
      }
      const wantsGpu = getWantsGpu();
      if (store.envExists && isCudaInstalled() && !wantsGpu) {
        showGpuVariantModal({
          title: "Switch to CPU-only?",
          message: "This will replace your existing GPU-accelerated PyTorch with a CPU-only version.",
          confirmText: "Reinstall CPU-only",
          onConfirm: () => startEnvSetup(false),
        });
        return;
      }
      startEnvSetup(wantsGpu);
    });
  }

  if (els.btnEnvVerify) {
    els.btnEnvVerify.addEventListener("click", () => {
      showToast("Verifying Python environment dependencies...", "info", 3000);
      api("/api/env/verify", { method: "POST" });
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
        <button class="btn btn-danger-soft btn-icon-only" data-action="delete-model" data-path="${escapeHtml(entry.path)}" title="Delete this cached model"><i class="bi bi-trash"></i></button>
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

      showConfirmModal({
        title: "Delete Cached Model",
        message: `Delete "${label}" from the model cache?\n\nThis frees disk space now, but ${entry && entry.used_by ? entry.used_by : "the owning app"} will need to download it again next time it's used.`,
        confirmText: "Delete Model",
        cancelText: "Keep Model",
        danger: true,
        onConfirm: () => {
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
        },
      });
    });
  }

  // ---- App Cards Rendering ----

  function actionState(app) {
    if (app.is_running) return { label: "Stop App", cls: "btn-danger", action: "stop" };
    if (app.installed) return { label: "Launch App", cls: "btn-success", action: "launch" };
    if (app.developer_mode) return { label: "Checkout Not Found", cls: "btn-outline btn-dev-mode", action: "none" };
    return { label: "Install", cls: "btn-primary", action: "install" };
  }

  function statusBadge(app) {
    if (app.is_running) return { text: "RUNNING", cls: "running", dot: "●" };
    if (app.installed) return { text: "INSTALLED", cls: "ready", dot: "●" };
    return { text: "NOT&nbsp;INSTALLED", cls: "", dot: "○" };
  }

  function appCardHtml(app) {
    const action = actionState(app);
    const badge = statusBadge(app);
    const isRunning = app.is_running;
    const isLocked = !store.envExists;
    
    const versionText = app.installed_version
      ? `v${app.installed_version}${app.update_available ? " • Update Available" : ""}`
      : "";

    const fallbackIcon = app.icon || 'bi-collection';
    const logoHtml = app.logo_path
      ? `<img src="/assets/${app.logo_path}" alt="${escapeHtml(app.name)}" onerror="var i=document.createElement('i');i.className='bi ${fallbackIcon}';this.replaceWith(i);">`
      : `<i class="bi ${fallbackIcon}" aria-hidden="true"></i>`;

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

    const uninstallBtnHtml = app.developer_mode ? "" : `<button class="btn btn-quiet btn-icon-only" data-action="uninstall" data-app-id="${app.id}" title="${isRunning ? 'Stop the app before uninstalling' : 'Uninstall'}" ${!app.installed || isRunning ? "disabled" : ""}><i class="bi bi-trash3"></i></button>`;

    const badgePillHtml = isLocked && !app.installed
      ? `<span class="status-badge-pill locked"><i class="bi bi-lock-fill"></i> REQUIRES&nbsp;ENV</span>`
      : `<span class="status-badge-pill ${badge.cls}">${badge.dot}&nbsp;${badge.text}</span>`;

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
              ${uninstallBtnHtml}
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

  let appFilterQuery = "";

  function renderApps() {
    if (!store.appOrder.length) {
      els.appsList.innerHTML = '<p class="apps-empty">No applications configured in launcher.</p>';
      return;
    }
    const q = appFilterQuery.toLowerCase();
    const visibleIds = store.appOrder.filter((id) => {
      if (!q) return true;
      const app = store.apps[id];
      if (!app) return false;
      return (
        app.name.toLowerCase().includes(q) ||
        (app.description && app.description.toLowerCase().includes(q)) ||
        id.toLowerCase().includes(q)
      );
    });

    if (!visibleIds.length) {
      els.appsList.innerHTML = `
        <div class="apps-search-empty" style="grid-column: 1 / -1; text-align: center; padding: 2.5rem 1rem; color: var(--text-muted);">
          <i class="bi bi-search" style="font-size: 1.8rem; display: block; margin-bottom: 0.5rem; opacity: 0.6;"></i>
          <p style="font-size: 0.95rem; margin-bottom: 0.75rem;">No tools match "<strong>${escapeHtml(appFilterQuery)}</strong>"</p>
          <button class="btn btn-outline btn-sm" id="btn-reset-search"><i class="bi bi-x-circle"></i> Clear search filter</button>
        </div>`;
      const resetBtn = document.getElementById("btn-reset-search");
      if (resetBtn) {
        resetBtn.addEventListener("click", () => {
          appFilterQuery = "";
          const input = document.getElementById("apps-search-input");
          if (input) input.value = "";
          const clearBtn = document.getElementById("apps-search-clear");
          if (clearBtn) clearBtn.classList.add("hidden");
          renderApps();
        });
      }
      return;
    }

    els.appsList.innerHTML = visibleIds.map((id) => appCardHtml(store.apps[id])).join("");
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
        showToast(`${app.name} is now running`, "success", 5000);
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

  function openEnvInstallerModal(isMandatory = false) {
    store.activeInstallerAppId = "env";
    store.isEnvSetupMandatory = !!isMandatory;
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
    if (els.btnInstallerClose) {
      if (isMandatory) {
        els.btnInstallerClose.classList.add("hidden");
      } else {
        els.btnInstallerClose.classList.remove("hidden");
      }
    }

    renderInstallerLogs("env");
    if (els.installerModal) els.installerModal.classList.remove("hidden");
  }

  function closeInstallerModal() {
    // The first-run setup is normally undismissable until it succeeds - but
    // that must never trap the user behind a failed install with no way out.
    if (store.isEnvSetupMandatory && !store.envReady && !store.envSetupFailed) {
      return;
    }
    if (els.installerModal) els.installerModal.classList.add("hidden");
    store.activeInstallerAppId = null;
    store.isEnvSetupMandatory = false;
    store.envSetupFailed = false;
  }

  // Reopen the installer modal for whatever the backend says is still
  // running, so reloading the page mid-install shows real progress instead
  // of a misleading "Setup Environment" button.
  function rejoinActiveJobs(jobs) {
    for (const job of jobs) {
      if (job.key === "env") {
        openEnvInstallerModal(store.isEnvSetupMandatory);
        if (job.progress) handleEnvProgressEvent(job.progress);
      } else if (job.key.startsWith("app:")) {
        const appId = job.key.slice("app:".length);
        if (store.apps[appId]) {
          openInstallerModal(appId);
          if (job.progress) handleInstallerProgressEvent(job.progress);
        }
      }
    }
  }

  // ---- Changelog Modal Controller ----
  async function loadChangelog() {
    if (!els.changelogModalBody) return;
    els.changelogModalBody.innerHTML = `
      <div class="changelog-loading">
        <div class="spinner"><i class="bi bi-arrow-repeat"></i></div>
        <p>Loading latest release notes from GitHub...</p>
      </div>
    `;

    try {
      const resp = await fetch("/api/changelog");
      const data = await resp.json();
      if (!resp.ok) throw new Error(data && data.error ? data.error : `HTTP ${resp.status}`);
      renderChangelog(data);
    } catch (err) {
      els.changelogModalBody.innerHTML = `
        <div class="changelog-item-card">
          <p class="text-danger"><i class="bi bi-exclamation-triangle"></i> Failed to load changelog: ${escapeHtml(err.message)}</p>
        </div>
      `;
    }
  }

  const APP_LOGOS = {
    launcher: "imgs/Logo.png",
    pypotteryink: "imgs/LogoInk.png",
    pypotterylayout: "imgs/LogoLayout.png",
    pypotterylens: "imgs/LogoLens.png",
    pypotteryscan: "imgs/LogoScan.png",
    pypotterytrace: "imgs/LogoTrace.png",
  };

  function renderChangelog(data) {
    if (!els.changelogModalBody) return;
    let html = "";

    const keys = Object.keys(data);
    const sortedKeys = [];
    if (keys.includes("launcher")) sortedKeys.push("launcher");
    keys.forEach(k => { if (k !== "launcher") sortedKeys.push(k); });

    sortedKeys.forEach((key) => {
      const item = data[key];
      const normKey = String(key || "").toLowerCase();
      const logoPath = item.logo_path || APP_LOGOS[normKey] || (store.apps && store.apps[key]?.logo_path) || "imgs/Logo.png";
      const published = item.published_at
        ? new Date(item.published_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
        : "";

      html += `
        <div class="changelog-item-card">
          <div class="changelog-item-header">
            <div class="changelog-item-title-group">
              <div class="changelog-item-logo-frame">
                <img src="/assets/${logoPath}" alt="${escapeHtml(item.name)}" class="changelog-item-logo" onerror="this.onerror=null; this.src='/assets/imgs/Logo.png';">
              </div>
              <h3 class="changelog-item-title">${escapeHtml(item.name)}</h3>
            </div>
            <div class="changelog-item-meta">
              <span class="version-badge">v${escapeHtml(item.latest_version)}</span>
              ${published ? `<span class="changelog-date"><i class="bi bi-calendar3"></i> ${published}</span>` : ''}
            </div>
          </div>
          <div class="changelog-notes">${escapeHtml(item.release_notes || 'No release notes available.')}</div>
          ${item.html_url ? `
            <a href="${item.html_url}" target="_blank" rel="noopener noreferrer" class="changelog-link-btn">
              <span>View full release on GitHub</span> <i class="bi bi-box-arrow-up-right"></i>
            </a>
          ` : ''}
        </div>
      `;
    });

    els.changelogModalBody.innerHTML = html || "<p class='text-dim'>No release information available.</p>";
  }

  if (els.btnChangelog && els.changelogModal) {
    els.btnChangelog.addEventListener("click", () => {
      els.changelogModal.classList.remove("hidden");
      loadChangelog();
    });
  }

  if (els.btnChangelogClose && els.changelogModal) {
    els.btnChangelogClose.addEventListener("click", () => {
      els.changelogModal.classList.add("hidden");
    });
  }

  if (els.changelogModal) {
    els.changelogModal.addEventListener("click", (e) => {
      if (e.target === els.changelogModal) {
        els.changelogModal.classList.add("hidden");
      }
    });
  }

  // ---- About / Info Modal Controller ----
  if (els.btnAbout && els.aboutModal) {
    els.btnAbout.addEventListener("click", () => {
      if (els.aboutVersionBadge && els.launcherVersion) {
        els.aboutVersionBadge.textContent = els.launcherVersion.textContent || "v1.1.0";
      }
      els.aboutModal.classList.remove("hidden");
    });
  }

  if (els.btnAboutClose && els.aboutModal) {
    els.btnAboutClose.addEventListener("click", () => {
      els.aboutModal.classList.add("hidden");
    });
  }

  if (els.aboutModal) {
    els.aboutModal.addEventListener("click", (e) => {
      if (e.target === els.aboutModal) {
        els.aboutModal.classList.add("hidden");
      }
    });
  }

  // ---- Disclaimer Modal Overlay Controller (Forced acceptance on first run) ----
  if (els.disclaimerModal) {
    if (localStorage.getItem("pypottery_disclaimer_accepted") !== "1") {
      els.disclaimerModal.classList.remove("hidden");
    }
  }

  if (els.btnAcceptDisclaimer && els.disclaimerModal) {
    els.btnAcceptDisclaimer.addEventListener("click", () => {
      els.disclaimerModal.classList.add("hidden");
      localStorage.setItem("pypottery_disclaimer_accepted", "1");
      if (!store.developerMode && !store.envExists && els.firstSetupModal) {
        els.firstSetupModal.classList.remove("hidden");
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

        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Installation Complete!";
        if (els.btnInstallerLaunch) {
          els.btnInstallerLaunch.classList.remove("hidden");
          els.btnInstallerLaunch.onclick = () => {
            closeInstallerModal();
            api(`/api/apps/${appId}/launch`, { method: "POST" });
          };
        }
        if (els.btnInstallerDone) {
          els.btnInstallerDone.classList.remove("hidden");
          els.btnInstallerDone.textContent = "Done";
          els.btnInstallerDone.onclick = closeInstallerModal;
        }
      } else if (stage === "error") {
        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Installation Error";
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

      // is_error must win over stage: the backend reports a failure with
      // whatever stage it happened during ("venv", "pytorch", ...), so
      // checking stage first here meant a failed install just sat showing
      // "Installing PyTorch..." forever - no error, no Close, no Retry, and
      // on first run the Close button starts out hidden, so there was no way
      // out of the modal at all.
      if (progress.is_error) {
        store.envSetupFailed = true;
        if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Environment Setup Error";
        if (els.btnInstallerClose) els.btnInstallerClose.classList.remove("hidden");
        if (els.btnInstallerDone) {
          els.btnInstallerDone.classList.remove("hidden");
          els.btnInstallerDone.innerHTML = '<i class="bi bi-arrow-repeat"></i> Retry Setup';
          els.btnInstallerDone.onclick = () => {
            store.envSetupFailed = false;
            resetInstallerStepper();
            updateInstallerProgressRing(0);
            if (els.installerStatusTitle) els.installerStatusTitle.textContent = "Retrying setup...";
            showToast("Retrying Python environment setup...", "info", 3000);
            // Reuse whatever the user actually chose last time (or the live
            // toggle state, if they haven't touched it) - a bare retry used
            // to silently drop back to "auto" (CUDA), undoing a CPU-only
            // choice without telling anyone.
            const wantsGpu = store.lastEnvSetupVariant != null ? store.lastEnvSetupVariant : getWantsGpu();
            postEnvSetup(wantsGpu);
          };
        }
      } else if (stage === "venv") {
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
          els.btnInstallerDone.innerHTML = '<i class="bi bi-rocket-takeoff-fill"></i> Enter PyPottery Suite';
          els.btnInstallerDone.onclick = () => {
            store.isEnvSetupMandatory = false;
            store.envSetupFailed = false;
            if (els.firstSetupModal) els.firstSetupModal.classList.add("hidden");
            closeInstallerModal();
            renderEnvStatus({ status: "ready", ready: true });
            showToast("PyPottery Suite is ready to use!", "success", 4000);
          };
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
      api(`/api/apps/${appId}/install`, { method: "POST" }).then(({ ok }) => {
        if (!ok) closeInstallerModal();
      });
    } else if (action === "update") {
      if (!app || !app.installed) return;
      openInstallerModal(appId);
      showToast(`Updating ${app ? app.name : appId}...`, "info", 4000);
      api(`/api/apps/${appId}/update`, { method: "POST" }).then(({ ok }) => {
        if (!ok) closeInstallerModal();
      });
    } else if (action === "launch") {
      showToast(`Launching ${app ? app.name : appId}...`, "info", 3000);
      api(`/api/apps/${appId}/launch`, { method: "POST" });
    } else if (action === "stop") {
      showToast(`Stopping ${app ? app.name : appId}...`, "warning", 3000);
      api(`/api/apps/${appId}/stop`, { method: "POST" });
    } else if (action === "folder") {
      api(`/api/apps/${appId}/folder`, { method: "POST" });
    } else if (action === "uninstall") {
      if (!app || !app.installed) return;
      showConfirmModal({
        title: `Uninstall ${app.name}?`,
        message: `This removes ${app.name} and its files from disk. Any AI models it downloaded to the shared model cache are kept. This cannot be undone.`,
        confirmText: "Uninstall",
        cancelText: "Cancel",
        danger: true,
        onConfirm: () => {
          showToast(`Uninstalling ${app.name}...`, "warning", 3000);
          api(`/api/apps/${appId}/uninstall`, { method: "POST" });
        },
      });
    }
  });

  // ---- Header & Global Actions ----

  if (els.btnCheckUpdates) {
    els.btnCheckUpdates.addEventListener("click", () => {
      showToast("Checking for updates...", "info", 3000);
      api("/api/updates/check", { method: "POST" });
    });
  }

  if (els.btnQuit) {
    els.btnQuit.addEventListener("click", () => {
      showConfirmModal({
        title: "Quit Launcher",
        message: "Quit PyPottery Suite Launcher? All running applications will be stopped.",
        confirmText: "Quit",
        cancelText: "Cancel",
        danger: true,
        onConfirm: () => {
          api("/api/shutdown", { method: "POST", quiet: true }).finally(() => {
            if (els.terminatedScreen) els.terminatedScreen.classList.remove("hidden");
          });
        },
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
    const contentEl = document.getElementById("pop-quote-content");
    if (!textEl || !sourceEl || !data || !data.quote) return;

    if (quoteContainer && contentEl) {
      // 1. Lock current height in pixels and clip during animation
      const currentH = quoteContainer.offsetHeight || contentEl.offsetHeight;
      quoteContainer.style.height = currentH + "px";
      quoteContainer.style.overflow = "hidden";
      quoteContainer.style.pointerEvents = "none";

      // 2. Fade & slight slide up
      contentEl.style.opacity = "0";
      contentEl.style.transform = "translateY(-4px)";

      setTimeout(() => {
        // 3. Swap text while invisible
        textEl.textContent = `\u201c${data.quote}\u201d`;
        sourceEl.textContent = `\u2014 ${data.source}`;

        // 4. Measure new height of inner content
        const newH = Math.max(contentEl.scrollHeight, contentEl.offsetHeight);

        // 5. Animate container height smoothly
        quoteContainer.style.height = newH + "px";

        // 6. Fade & slide content back in
        contentEl.style.opacity = "1";
        contentEl.style.transform = "translateY(0)";
        quoteContainer.style.pointerEvents = "";

        // 7. Ensure no clipping once animation settles
        setTimeout(() => {
          if (quoteContainer) quoteContainer.style.overflow = "visible";
        }, 400);
      }, 220);
    } else {
      textEl.textContent = `\u201c${data.quote}\u201d`;
      sourceEl.textContent = `\u2014 ${data.source}`;
    }
  }

  window.addEventListener("resize", () => {
    const qc = document.getElementById("hero-pop-quote");
    const qcc = document.getElementById("pop-quote-content");
    if (qc && qcc && qcc.offsetHeight > 0) {
      qc.style.height = qcc.offsetHeight + "px";
    }
  });

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


  if (els.btnLauncherUpdateNotesToggle) {
    els.btnLauncherUpdateNotesToggle.addEventListener("click", () => {
      if (els.launcherUpdateNotes) {
        els.launcherUpdateNotes.classList.toggle("hidden");
      }
    });
  }

  if (els.btnLauncherUpdateConfirm) {
    els.btnLauncherUpdateConfirm.addEventListener("click", async () => {
      if (!store.pendingUpdateVersion) return;
      if (els.launcherUpdateBanner) els.launcherUpdateBanner.classList.add("hidden");

      const { ok, data } = await api("/api/launcher/update", {
        method: "POST", body: { version: store.pendingUpdateVersion }, quiet: true,
      });

      if (!ok && data && data.code === "manual_update") {
        // A packaged build (frozen exe, AppImage, .app) can't rewrite itself
        // from the inside - the old code would just keep running. Point the
        // user at the download instead of quietly doing nothing.
        showToast(
          "This build updates by downloading the new version - opening the release page.",
          "info", 6000,
        );
        if (data.release_url) window.open(data.release_url, "_blank", "noopener");
        return;
      }
      if (!ok) {
        showToast((data && data.error) || "Could not start the update", "error", 6000);
        return;
      }

      if (els.launcherUpdateProgressBanner) {
        els.launcherUpdateProgressBanner.classList.remove("hidden");
        if (els.launcherUpdateProgressText) {
          els.launcherUpdateProgressText.textContent = "Starting launcher update...";
        }
        if (els.launcherUpdateProgressPct) {
          els.launcherUpdateProgressPct.textContent = "0%";
        }
        if (els.launcherUpdateProgressBar) {
          els.launcherUpdateProgressBar.style.width = "0%";
          els.launcherUpdateProgressBar.classList.remove("error");
        }
      }
    });
  }

  let restartPollActive = false;
  function pollForLauncherRestart() {
    if (restartPollActive) return;
    restartPollActive = true;

    if (els.launcherUpdateProgressText) {
      els.launcherUpdateProgressText.textContent = "Restarting launcher... Reconnecting automatically...";
    }

    let attempts = 0;
    const maxAttempts = 60; // Up to 60 seconds
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await fetch("/api/state?t=" + Date.now(), { cache: "no-store" });
        if (res.ok) {
          clearInterval(interval);
          if (els.launcherUpdateProgressText) {
            els.launcherUpdateProgressText.textContent = "Reconnected! Reloading page...";
          }
          setTimeout(() => {
            window.location.reload();
          }, 800);
        }
      } catch (e) {
        // Still restarting / offline
        if (attempts >= maxAttempts) {
          clearInterval(interval);
          restartPollActive = false; // otherwise a retried update can never poll again without a full reload
          if (els.launcherUpdateProgressText) {
            els.launcherUpdateProgressText.textContent = "Restart complete. Please reload this page.";
          }
        }
      }
    }, 1000);
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
        renderEnvStatus(data);
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
        if (els.launcherUpdateBadge) {
          els.launcherUpdateBadge.textContent = `v${data.update.latest_version}`;
        }
        if (els.launcherUpdateText) {
          els.launcherUpdateText.textContent = `A new version of PyPottery Launcher (v${data.update.latest_version}) is available.`;
        }
        if (data.update.release_notes && els.launcherUpdateNotes) {
          els.launcherUpdateNotes.textContent = data.update.release_notes;
          if (els.btnLauncherUpdateNotesToggle) {
            els.btnLauncherUpdateNotesToggle.classList.remove("hidden");
          }
        }
        if (els.launcherUpdateBanner) els.launcherUpdateBanner.classList.remove("hidden");
        showToast(`Update available: PyPottery Launcher v${data.update.latest_version}`, "info", 6000);
        break;
      case "init_failed":
        showToast(
          `Launcher initialization failed: ${data.message || "unknown error"}. See the log file for details.`,
          "error", 8000,
        );
        break;
      case "job_finished":
        // Another tab (or this one, after a reload) finished a job - re-sync
        // so a stale "still installing" state doesn't linger.
        api("/api/state", { quiet: true }).then(({ ok, data: s }) => {
          if (ok && s) {
            renderEnvStatus(s.env || { status: "absent", ready: false });
            setApps(s.apps || []);
          }
        });
        break;
      case "ping":
        break;
      case "launcher_update_progress":
        if (els.launcherUpdateProgressBanner) els.launcherUpdateProgressBanner.classList.remove("hidden");
        if (els.launcherUpdateProgressText) els.launcherUpdateProgressText.textContent = data.message;
        const pct = Math.round(data.percent || 0);
        if (els.launcherUpdateProgressPct) els.launcherUpdateProgressPct.textContent = `${pct}%`;
        if (els.launcherUpdateProgressBar) {
          els.launcherUpdateProgressBar.style.width = `${pct}%`;
          els.launcherUpdateProgressBar.classList.toggle("error", !!data.error);
        }

        if (data.stage === "restarting" || (pct >= 100 && !data.error)) {
          pollForLauncherRestart();
        }
        break;
      default:
        break;
    }
  }

  // The server sends a real "ping" event every 25s (not just an SSE comment,
  // which never reaches JS at all) specifically so this watchdog can tell
  // "quiet" apart from "the launcher died" - EventSource's own onerror only
  // fires after the browser has already given up retrying for a while.
  const SSE_WATCHDOG_MS = 45000;
  let _sseSource = null;
  let _sseWatchdogTimer = null;

  function markConnectionLost() {
    if (store.connectionLost) return;
    store.connectionLost = true;
    if (els.connectionLostBanner) els.connectionLostBanner.classList.remove("hidden");
  }

  function markConnectionRestored() {
    if (!store.connectionLost) return;
    store.connectionLost = false;
    if (els.connectionLostBanner) els.connectionLostBanner.classList.add("hidden");
    // The connection may have been down for a while - re-sync everything
    // rather than trusting whatever events happened to arrive after.
    api("/api/state", { quiet: true }).then(({ ok, data: s }) => {
      if (!ok || !s) return;
      renderEnvStatus(s.env || { status: "absent", ready: false });
      setApps(s.apps || []);
      if (s.hardware) renderHardware(s.hardware);
      if (s.models) renderModelCache(s.models);
      rejoinActiveJobs(s.jobs || []);
    });
  }

  function connectEvents() {
    if (_sseSource) {
      _sseSource.close();
    }

    const source = new EventSource("/api/events");
    _sseSource = source;

    source.onmessage = (evt) => {
      store.lastEventAt = Date.now();
      markConnectionRestored();
      try {
        handleEvent(JSON.parse(evt.data));
      } catch (e) {
        // ignore malformed events
      }
    };
    source.onerror = () => {
      // The browser's built-in EventSource reconnect can take a while to
      // kick in (and won't retry at all once the connection is CLOSED) - the
      // watchdog below is what actually surfaces the problem to the user.
    };

    if (_sseWatchdogTimer) clearInterval(_sseWatchdogTimer);
    _sseWatchdogTimer = setInterval(() => {
      const silent = Date.now() - store.lastEventAt;
      if (silent > SSE_WATCHDOG_MS) {
        markConnectionLost();
        if (source.readyState === EventSource.CLOSED) {
          connectEvents(); // native reconnect gave up - force a fresh attempt
        }
      }
    }, 5000);
  }

  if (els.btnConnectionRetry) {
    els.btnConnectionRetry.addEventListener("click", () => {
      store.lastEventAt = Date.now(); // don't immediately re-trigger the watchdog
      connectEvents();
    });
  }

  if (els.btnOpenLogs) {
    els.btnOpenLogs.addEventListener("click", () => {
      api("/api/logs/open", { method: "POST" });
    });
  }

  if (els.btnAboutDataFolder) {
    els.btnAboutDataFolder.addEventListener("click", () => {
      api("/api/data-folder/open", { method: "POST" });
    });
  }

  // ---- Search & Keyboard Shortcuts (Flexibility & Efficiency) ----

  const appsSearchInput = document.getElementById("apps-search-input");
  const appsSearchClear = document.getElementById("apps-search-clear");

  if (appsSearchInput) {
    appsSearchInput.addEventListener("input", (e) => {
      appFilterQuery = e.target.value.trim();
      if (appsSearchClear) {
        appsSearchClear.classList.toggle("hidden", !appFilterQuery);
      }
      renderApps();
    });
  }

  if (appsSearchClear) {
    appsSearchClear.addEventListener("click", () => {
      appFilterQuery = "";
      if (appsSearchInput) {
        appsSearchInput.value = "";
        appsSearchInput.focus();
      }
      appsSearchClear.classList.add("hidden");
      renderApps();
    });
  }

  // Global keyboard shortcuts (Escape to close modals, / to filter tools)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (els.aboutModal && !els.aboutModal.classList.contains("hidden")) {
        els.aboutModal.classList.add("hidden");
        return;
      }
      if (els.changelogModal && !els.changelogModal.classList.contains("hidden")) {
        els.changelogModal.classList.add("hidden");
        return;
      }
      if (els.gpuVariantModal && !els.gpuVariantModal.classList.contains("hidden")) {
        els.gpuVariantModal.classList.add("hidden");
        return;
      }
      if (els.installerModal && !els.installerModal.classList.contains("hidden")) {
        closeInstallerModal();
        return;
      }
      if (appsSearchInput && document.activeElement === appsSearchInput) {
        appsSearchInput.value = "";
        appFilterQuery = "";
        if (appsSearchClear) appsSearchClear.classList.add("hidden");
        appsSearchInput.blur();
        renderApps();
        return;
      }
    }

    if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) {
      if (appsSearchInput) {
        e.preventDefault();
        appsSearchInput.focus();
        appsSearchInput.select();
      }
    }
  });

  // ---- Splash Screen Controller ----

  function updateSplash(percent, statusMessage) {
    if (els.splashBar) els.splashBar.style.width = `${percent}%`;
    if (els.splashStatus) els.splashStatus.textContent = statusMessage;
  }

  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function hideSplash() {
    if (!els.splashScreen) return;
    updateSplash(100, "Ready!");
    await delay(120);
    els.splashScreen.classList.add("splash-fade-out");
    await delay(250);
    els.splashScreen.style.display = "none";
  }

  // ---- Initial State Hydration ----

  async function init() {
    renderDailyGreeting();
    const initQuoteCont = document.getElementById("hero-pop-quote");
    const initQuoteContent = document.getElementById("pop-quote-content");
    if (initQuoteCont && initQuoteContent && initQuoteContent.offsetHeight > 0) {
      initQuoteCont.style.height = initQuoteContent.offsetHeight + "px";
    }
    initCollapsiblePanels();
    updateSplash(30, "Initializing system components...");

    updateSplash(60, "Detecting hardware & environment...");

    try {
      const res = await fetch("/api/state");
      const state = await res.json();

      updateSplash(90, "Loading archaeological tools & models...");
      if (state.developer_mode !== undefined) {
        store.developerMode = Boolean(state.developer_mode);
      }
      if (els.launcherVersion) els.launcherVersion.textContent = `v${state.launcher_version}`;
      if (state.hardware) renderHardware(state.hardware);
      if (state.pop_quote) {
        renderPopQuote(state.pop_quote);
      } else {
        fetchWikiquote();
      }
      renderEnvStatus(state.env || { status: "absent", ready: false });
      setApps(state.apps || []);
      (state.console || []).forEach(appendConsoleEntry);
      if (state.models) renderModelCache(state.models);
      rejoinActiveJobs(state.jobs || []);
    } catch (e) {
      // Backend hydration fallback
      fetchWikiquote();
    }

    connectEvents();

    await hideSplash();

    // After splash screen hides, if disclaimer is already accepted and environment is missing, show setup modal
    const disclaimerAccepted = localStorage.getItem("pypottery_disclaimer_accepted") === "1" || !els.disclaimerModal;
    if (!store.developerMode && disclaimerAccepted && !store.envExists && els.firstSetupModal) {
      els.firstSetupModal.classList.remove("hidden");
    }
  }

  init();
});

