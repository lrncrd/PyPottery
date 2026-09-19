# PyPottery Suite — Moduli Auto-Shutdown, Beacon & Tab Lock Guide

Questo documento descrive l'architettura e la procedura passo-passo per implementare il sistema di **Auto-Shutdown pulito (Heartbeat + Beacon)**, la **Finestra di Conferma Chiusura** e il **Blocco Schede senza Progetto Attivo** su tutte le applicazioni della suite PyPottery:

* [x] **PyPotteryLens** *(già implementato, testato e rilasciato)*
* [x] **PyPotteryLayout** *(implementato e rilasciato in v0.3.3, 2026-09-19)*
* [x] **PyPotteryInk** *(committato su `beta` il 2026-09-19, test HTTP ok; non ancora in `main`/rilasciato)*
* [x] **PyPotteryScan** *(committato su `beta` il 2026-09-19, test HTTP ok; `.gitignore` corretto con `/static/`, `beacon.js` ora tracciato; non ancora in `main`/rilasciato)*
* [x] **PyPotteryTrace** *(committato su `beta` il 2026-09-19, test HTTP ok; non ancora in `main`/rilasciato)*

Il "Blocco Schede senza Progetto Attivo" (sezione 4) non è stato applicato a Ink/Scan/Trace/Layout per scelta esplicita (solo Lens ce l'ha).

---

## 1. Obiettivo e Architettura

### Il problema originale
Le app della suite sono applicazioni Flask locali con interfaccia web nel browser. Quando un utente chiude la scheda del browser con la "X":
1. Il browser interrompe solo la connessione visiva, ma **non termina il processo Python**.
2. Modelli AI pesanti (PyTorch, YOLO, SAM2, OCR) rimangono caricati in memoria RAM e nella VRAM della GPU (4–16+ GB occupati).
3. Le porte locali (es. 5001, 5002, 5005) restano bloccate.
4. L'utente doveva tornare sul Launcher e cliccare manualmente "Stop App", oppure aprire il Task Manager / terminale.

### La soluzione adottata
Una combinazione robusta di:
* **Heartbeat (battito cardiaco)**: la pagina web invia un ping leggero ogni 2.5 secondi a `/api/heartbeat`.
* **Conferma di Uscita (`beforeunload`)**: quando l'utente chiude la scheda o il browser, compare la finestra nativa di conferma (*"Vuoi abbandonare il sito? Le modifiche potrebbero non essere salvate"*). Se clicca su "Rimani", la sessione continua normalmente.
* **Beacon di Disconnessione (`pagehide`)**: solo se l'utente conferma l'uscita, il browser invia un beacon HTTP asincrono a `/api/beacon_shutdown`.
* **Grace Period Countdown (5 secondi)**: all'arrivo del beacon, parte un conto alla rovescia di 5 secondi. Se era un semplice refresh della pagina (F5), la nuova pagina invia subito un heartbeat e cancella il timer; se la scheda è stata davvero chiusa, il server Flask esegue la terminazione pulita (`torch.cuda.empty_cache()` + `os._exit(0)`).
* **Watchdog di sicurezza (60 secondi)**: controlla periodicamente schede abbandonate (es. crash improvviso del browser o PC spento). La soglia di 60 secondi garantisce che le schede messe in secondo piano o in "sleep" da Chrome/Edge non vengano terminate per errore.

---

## 2. Implementazione Backend (`app.py`)

Aggiungere le seguenti sezioni al file `app.py` del modulo.

### A. Import necessari
Assicurarsi che in cima a `app.py` siano presenti:
```python
from typing import Dict, Optional
import sys
import os
import json
import threading
import time
```

### B. Blocco Watchdog e Route di Spegnimento
Inserire questo blocco subito prima delle route principali (es. prima di `# ROUTES`):

```python
# ==================== AUTO-SHUTDOWN WATCHDOG & BEACON ====================
_shutdown_lock = threading.Lock()
_active_tabs: Dict[str, float] = {}  # tab_id -> timestamp
_shutdown_timer: Optional[threading.Timer] = None
_initial_heartbeat_received = False
_start_time = time.time()

# Disabilitabile con variabile d'ambiente per debug/test:
AUTO_SHUTDOWN_ENABLED = os.environ.get("PYPOTTERY_DISABLE_AUTO_SHUTDOWN", "0") != "1"

# Secondi di grazia alla chiusura prima di terminare (consente anche il refresh F5)
AUTO_SHUTDOWN_GRACE_SECONDS = 5.0

# Timeout per schede orfane senza beacon (60s previene falsi allarmi su schede in background/sleep)
TAB_STALE_TIMEOUT_SECONDS = 60.0

# Tempo concesso all'avvio affinché il browser si apra e si connetta
STARTUP_GRACE_SECONDS = 60.0


def _perform_graceful_shutdown():
    """Rilascia la memoria GPU/RAM e termina il processo di sistema."""
    print("[PyPottery] 🛑 Auto-shutdown: Nessuna scheda attiva. Terminazione processo...")
    try:
        import torch, gc
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
    except Exception:
        pass

    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass

    # os._exit(0) termina immediatamente il processo Python, liberando porte e memoria
    os._exit(0)


def _cancel_shutdown_timer_locked():
    global _shutdown_timer
    if _shutdown_timer is not None:
        _shutdown_timer.cancel()
        _shutdown_timer = None


def _arm_shutdown_timer_locked(delay_seconds: float = AUTO_SHUTDOWN_GRACE_SECONDS):
    global _shutdown_timer
    if not AUTO_SHUTDOWN_ENABLED:
        return
    if _shutdown_timer is not None:
        _shutdown_timer.cancel()
    _shutdown_timer = threading.Timer(delay_seconds, _perform_graceful_shutdown)
    _shutdown_timer.daemon = True
    _shutdown_timer.start()


def _watchdog_loop():
    """Loop di background per gestire crash o disconnessioni anomale del browser."""
    while True:
        time.sleep(3.0)
        if not AUTO_SHUTDOWN_ENABLED:
            continue

        now = time.time()
        if not _initial_heartbeat_received:
            if now - _start_time < STARTUP_GRACE_SECONDS:
                continue
            with _shutdown_lock:
                if not _initial_heartbeat_received and _shutdown_timer is None:
                    print("[PyPottery] ⚠️ Nessun browser connesso entro la finestra di avvio.")
                    _arm_shutdown_timer_locked(10.0)
            continue

        with _shutdown_lock:
            stale_keys = [k for k, v in _active_tabs.items() if now - v > TAB_STALE_TIMEOUT_SECONDS]
            for k in stale_keys:
                del _active_tabs[k]

            if not _active_tabs and _shutdown_timer is None:
                print(f"[PyPottery] Watchdog: Tutte le schede sono chiuse. Arresto programmato ({AUTO_SHUTDOWN_GRACE_SECONDS}s)...")
                _arm_shutdown_timer_locked(AUTO_SHUTDOWN_GRACE_SECONDS)


threading.Thread(target=_watchdog_loop, daemon=True, name="AutoShutdownWatchdog").start()


@app.route('/api/heartbeat', methods=['POST'])
def handle_heartbeat():
    """Ping periodico dalla scheda attiva del browser."""
    global _initial_heartbeat_received
    data = request.get_json(silent=True) or {}
    tab_id = data.get('tab_id') or request.remote_addr or 'default'
    now = time.time()

    with _shutdown_lock:
        _initial_heartbeat_received = True
        _active_tabs[tab_id] = now
        _cancel_shutdown_timer_locked()

    return jsonify({'status': 'ok', 'active_tabs': len(_active_tabs)})


@app.route('/api/beacon_shutdown', methods=['POST'])
def handle_beacon_shutdown():
    """Inviato via navigator.sendBeacon su pagehide alla chiusura definitiva."""
    try:
        raw = request.get_data()
        data = json.loads(raw.decode('utf-8')) if raw else {}
    except Exception:
        data = request.get_json(silent=True) or {}

    tab_id = data.get('tab_id')
    with _shutdown_lock:
        if tab_id and tab_id in _active_tabs:
            del _active_tabs[tab_id]
        elif not tab_id and _active_tabs:
            if len(_active_tabs) <= 1:
                _active_tabs.clear()

        if not _active_tabs:
            print(f"[PyPottery] Beacon di chiusura ricevuto. Nessuna scheda attiva. Arresto in {AUTO_SHUTDOWN_GRACE_SECONDS}s...")
            _arm_shutdown_timer_locked(AUTO_SHUTDOWN_GRACE_SECONDS)

    return Response(status=204)
```

### C. Blocco `__main__`
Assicurarsi che nel blocco finale `if __name__ == '__main__':` la porta sia letta da `PORT` / `PYPOTTERY_PORT` e il browser venga aperto in un thread separato:

```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', os.environ.get('PYPOTTERY_PORT', DEFAULT_PORT)))
    
    import webbrowser
    import threading

    def open_browser():
        time.sleep(1)
        webbrowser.open(f'http://localhost:{port}')

    threading.Thread(target=open_browser, daemon=True).start()

    app.run(
        host='127.0.0.1',
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False
    )
```

---

## 3. Implementazione Frontend (`main.js`)

Aggiungere in fondo al file JavaScript principale dell'app (`static/js/main.js`):

```javascript
// ==========================================
// Auto-Shutdown Heartbeat & Beacon System
// ==========================================
(function initAutoShutdownBeacon() {
    const tabSessionId = 'tab_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now();
    const HEARTBEAT_INTERVAL_MS = 2500;

    function sendHeartbeat() {
        fetch('/api/heartbeat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tab_id: tabSessionId }),
            keepalive: true
        }).catch(() => {});
    }

    // Ping iniziale immediato
    sendHeartbeat();

    // Ping periodico
    const intervalId = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);

    // Re-ping al ritorno del focus sulla scheda
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') sendHeartbeat();
    });
    window.addEventListener('focus', sendHeartbeat);

    // 1. Finestra di conferma alla chiusura della scheda o del browser
    window.addEventListener('beforeunload', (e) => {
        e.preventDefault();
        e.returnValue = '';
        return '';
    });

    // 2. Invio del beacon SOLO quando l'utente ha effettivamente confermato l'uscita
    let beaconSent = false;
    function sendShutdownBeacon() {
        if (beaconSent) return;
        beaconSent = true;
        clearInterval(intervalId);
        const payload = JSON.stringify({ tab_id: tabSessionId });

        if (navigator.sendBeacon) {
            const blob = new Blob([payload], { type: 'application/json' });
            navigator.sendBeacon('/api/beacon_shutdown', blob);
        } else {
            fetch('/api/beacon_shutdown', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
                keepalive: true
            }).catch(() => {});
        }
    }

    window.addEventListener('pagehide', sendShutdownBeacon);
    window.addEventListener('unload', sendShutdownBeacon);
})();
```

---

## 4. Blocco Schede Senza Progetto Attivo

Per i moduli basati su progetti (come *PyPotteryLens* e altri che hanno un Project Manager iniziale), le schede di elaborazione devono restare bloccate finché l'utente non seleziona o crea un progetto.

### A. JavaScript (`main.js`)
```javascript
// Verifica se c'è un progetto attivo (da window.projectManager o localStorage)
function hasActiveProject() {
    if (window.projectManager && typeof window.projectManager.getCurrentProject === 'function') {
        const p = window.projectManager.getCurrentProject();
        if (p && p.project_id) return true;
    }
    const savedId = localStorage.getItem('currentProjectId');
    return Boolean(savedId && savedId !== 'null' && savedId !== 'undefined');
}

// Nel TabManager:
class TabManager {
    init() {
        this.tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabId = tab.dataset.tab;
                if (tabId !== 'projects' && !hasActiveProject()) {
                    e.preventDefault();
                    if (typeof showToast === 'function') {
                        showToast('Seleziona o crea prima un progetto per accedere alle altre sezioni.', 'warning');
                    }
                    return;
                }
                this.switchTab(tab);
            });
        });
    }

    switchTab(clickedTab) {
        const tabId = clickedTab.dataset.tab;
        if (tabId !== 'projects' && !hasActiveProject()) {
            if (typeof showToast === 'function') {
                showToast('Seleziona o crea prima un progetto per accedere alle altre sezioni.', 'warning');
            }
            return;
        }
        // ... cambio scheda normale ...
    }
}

// Funzione di aggiornamento visivo dello stato delle schede
function updateTabsState(project) {
    const hasProject = Boolean(project && project.project_id) || hasActiveProject();
    const otherTabs = document.querySelectorAll('.tab-button:not([data-tab="projects"])');
    
    otherTabs.forEach(tab => {
        tab.classList.toggle('tab-locked', !hasProject);
        if (!hasProject) {
            tab.setAttribute('title', 'Seleziona o crea prima un progetto per sbloccare questa sezione');
        } else {
            tab.removeAttribute('title');
        }
    });

    if (!hasProject) {
        const activeTab = document.querySelector('.tab-button.active');
        if (activeTab && activeTab.dataset.tab !== 'projects') {
            const projectsTab = document.querySelector('.tab-button[data-tab="projects"]');
            if (projectsTab) projectsTab.click();
        }
    }
}

// In DOMContentLoaded:
window.addEventListener('projectChanged', (event) => {
    updateTabsState(event.detail.project);
});
updateTabsState(window.projectManager ? window.projectManager.getCurrentProject() : null);
```

### B. Stili CSS (`static/css/style.css`)
```css
/* Stato Scheda Bloccata (senza progetto attivo) */
.tab-button.tab-locked {
    opacity: 0.45;
    cursor: not-allowed;
    background: #fbf9f5;
    color: var(--text-muted);
}

.tab-button.tab-locked:hover {
    color: var(--text-muted) !important;
    background: #fbf9f5 !important;
    border-color: var(--border) !important;
    box-shadow: none !important;
}

.tab-button.tab-locked i {
    color: var(--text-muted) !important;
}
```

---

## 5. Checklist Applicazioni della Suite

| Applicazione | Default Port | Auto-Shutdown & Beacon | Conferma Uscita | Project Lock | Note |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **PyPotteryLens** | `5001` | ✅ Implementato | ✅ Implementato | ✅ Implementato | Rilascia VRAM modelli YOLO/VLM |
| **PyPotteryLayout** | `5005` | ✅ Rilasciato (v0.3.3) | ✅ Rilasciato (v0.3.3) | — | Rilascio VRAM non applicabile (no modelli AI) |
| **PyPotteryInk** | `5003` | ✅ Su `beta` (non rilasciato) | ✅ Su `beta` (non rilasciato) | — | Rilascio modelli PyTorch/SD |
| **PyPotteryScan** | `5002` | ✅ Su `beta` (non rilasciato) | ✅ Su `beta` (non rilasciato) | — | Rilascio modelli OCR |
| **PyPotteryTrace** | `5004` | ✅ Su `beta` (non rilasciato) | ✅ Su `beta` (non rilasciato) | — | Rilascio modelli SAM2/CUDA |