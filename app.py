from flask import Flask, render_template, jsonify
import os
import time
import subprocess
import sys

app = Flask(__name__)
app.secret_key = 'pypottery-main-secret-key-change-in-production'

# App configuration
APP_CONFIG = {
    'Layout': {
        'name': 'PyPotteryLayout',
        'directory': 'PyPotteryLayout',
        'port': 5005,
        'script': 'app.py',
        'batch_script': 'launch_layout.bat'
    },
    # Add other apps here as they become available
    # 'Lens': {'name': 'PyPotteryLens', 'directory': 'PyPotteryLens', 'port': 5006, 'script': 'app.py', 'batch_script': 'launch_lens.bat'},
    # 'Scan': {'name': 'PyPotteryScan',  'directory': 'PyPotteryScan', 'port': 5007, 'script': 'app.py', 'batch_script': 'launch_scan.bat'},
}

@app.route('/')
def splash():
    # Placeholder for app logos/buttons
    apps = [
        {'name': 'Lens', 'logo': 'logos/LogoLens.png', 'url': '#', 'desc': '<strong>Lens App</strong><br>Analisi immagini e zoom.<br>Funzioni: filtri, misurazioni, editing.', 'details': '<h3>Lens App</h3><p>App avanzata per l\'analisi e modifica di immagini.</p><ul><li>Zoom ad alta risoluzione</li><li>Filtri avanzati</li><li>Misurazioni precise</li><li>Editing non distruttivo</li></ul>', 'secret': False},
        {'name': 'Scan', 'logo': 'logos/LogoScan.png', 'url': '#', 'desc': '<strong>Scan App</strong><br>Scansione documenti.<br>Funzioni: OCR, conversione PDF, archiviazione.', 'details': '<h3>Scan App</h3><p>Soluzione completa per la scansione di documenti.</p><ul><li>Riconoscimento OCR</li><li>Conversione automatica PDF</li><li>Archiviazione cloud</li><li>Integrazione con database</li></ul>', 'secret': False},
        {'name': 'Ink', 'logo': 'logos/LogoInk.png', 'url': '#', 'desc': '<strong>Ink App</strong><br>Gestione avanzata dell\'inchiostro.<br>Funzioni: calibrazione colori, monitoraggio livelli.', 'details': '<h3>Ink App</h3><p>Applicazione completa per la gestione dell\'inchiostro digitale.</p><ul><li>Calibrazione automatica dei colori</li><li>Monitoraggio livelli in tempo reale</li><li>Supporto per moltiplici tipi di inchiostro</li><li>Esportazione report</li></ul>', 'secret': False},
        {'name': 'Trace', 'logo': 'logos/LogoTrace.png', 'url': '#', 'desc': '<strong>Trace App</strong><br>Tracciamento percorsi.<br>Funzioni: GPS, logging dati, visualizzazione mappe.', 'details': '<h3>Trace App</h3><p>Applicazione per il tracciamento e monitoraggio di percorsi.</p><ul><li>GPS ad alta precisione</li><li>Logging dati automatico</li><li>Visualizzazione mappe interattive</li><li>Analisi percorsi</li></ul>', 'secret': False},
        {'name': 'ProfileAnalysis', 'logo': 'logos/LogoTrace.png', 'url': '#', 'desc': '<strong>ProfileAnalysis App</strong><br>Analisi profili avanzata.<br>Funzioni: statistiche, report, insights.', 'details': '<h3>ProfileAnalysis App</h3><p>Strumento per l\'analisi dettagliata dei profili.</p><ul><li>Statistiche avanzate</li><li>Report personalizzati</li><li>Insights predittivi</li><li>Integrazione dati</li></ul>', 'secret': True},
        {'name': 'Layout', 'logo': 'logos/LogoLayout.png', 'url': '/launch/Layout', 'desc': '<strong>Layout App</strong><br>Strumento per design layout.<br>Funzioni: griglie, allineamenti, esportazione.', 'details': '<h3>Layout App</h3><p>Strumento professionale per creare layout di design.</p><ul><li>Griglie responsive</li><li>Allineamenti automatici</li><li>Esportazione in vari formati</li><li>Collaborazione in tempo reale</li></ul>', 'secret': False},
    ]
    return render_template('index.html', apps=apps)

@app.route('/launch/<app_name>')
def launch_app(app_name):
    """Launch a sub-application using batch script"""
    try:
        # Check if app_name exists in configuration
        if app_name not in APP_CONFIG:
            return jsonify({'error': f'App {app_name} not found'}), 404
        
        config = APP_CONFIG[app_name]
        batch_script = os.path.join(os.path.dirname(__file__), config.get('batch_script', ''))
        
        # Check if batch script exists
        if not os.path.exists(batch_script):
            return jsonify({'error': f'Batch script {config.get("batch_script", "not specified'")} not found'}), 404
        
        #Launch the batch script in a new console window
        print(f"[PyPottery] Launching {config['name']} via {config['batch_script']}...")
        
        # Use subprocess.Popen with CREATE_NEW_CONSOLE to run batch file in separate window
        # This is more reliable than os.system('start')
        creation_flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        
        subprocess.Popen(
            [batch_script],
            cwd=os.path.dirname(__file__),
            creationflags=creation_flags,
            shell=True  # Needed for .bat files on Windows
        )
        
        # Wait a bit longer to ensure the app starts
        time.sleep(3)
        
        app_url = f"http://localhost:{config['port']}"
        print(f"[PyPottery] {config['name']} launch command sent. Expected URL: {app_url}")
        
        return jsonify({
            'status': 'started',
            'url': app_url,
            'message': f"{config['name']} is starting..."
        })
        
    except Exception as e:
        print(f"[PyPottery] Error launching {app_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("[PyPottery] Starting PyPottery Wrapper...")
    print("[PyPottery] Main page: http://localhost:5000")
    
    try:
        app.run(host='localhost', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n[PyPottery] Shutting down...")