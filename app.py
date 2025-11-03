from flask import Flask, render_template, redirect, url_for
import subprocess
import os
import sys
import threading
import time

app = Flask(__name__)

# Dictionary mapping app names to their folder paths and ports
APP_FOLDERS = {
    'Lens': {'folder': 'PyPotteryLens', 'port': 5001},
    'Scan': {'folder': 'PyPotteryScan', 'port': 5002},
    'Ink': {'folder': 'PyPotteryInk', 'port': 5003},
    'Trace': {'folder': 'PyPotteryTrace', 'port': 5004},
    'Layout': {'folder': 'PyPotteryLayout', 'port': 5005},
}

# Track running apps
running_apps = {}

@app.route('/')
def splash():
    # Placeholder for app logos/buttons
    apps = [
        {'name': 'Lens', 'logo': 'logos/LogoLens.png', 'url': '/launch/Lens', 'desc': '<strong>Lens App</strong><br>Analisi immagini e zoom.<br>Funzioni: filtri, misurazioni, editing.', 'details': '<h3>Lens App</h3><p>App avanzata per l\'analisi e modifica di immagini.</p><ul><li>Zoom ad alta risoluzione</li><li>Filtri avanzati</li><li>Misurazioni precise</li><li>Editing non distruttivo</li></ul>', 'secret': False},
        {'name': 'Scan', 'logo': 'logos/LogoScan.png', 'url': '/launch/Scan', 'desc': '<strong>Scan App</strong><br>Scansione documenti.<br>Funzioni: OCR, conversione PDF, archiviazione.', 'details': '<h3>Scan App</h3><p>Soluzione completa per la scansione di documenti.</p><ul><li>Riconoscimento OCR</li><li>Conversione automatica PDF</li><li>Archiviazione cloud</li><li>Integrazione con database</li></ul>', 'secret': False},
        {'name': 'Ink', 'logo': 'logos/LogoInk.png', 'url': '/launch/Ink', 'desc': '<strong>Ink App</strong><br>Gestione avanzata dell\'inchiostro.<br>Funzioni: calibrazione colori, monitoraggio livelli.', 'details': '<h3>Ink App</h3><p>Applicazione completa per la gestione dell\'inchiostro digitale.</p><ul><li>Calibrazione automatica dei colori</li><li>Monitoraggio livelli in tempo reale</li><li>Supporto per molteplici tipi di inchiostro</li><li>Esportazione report</li></ul>', 'secret': False},
        {'name': 'Trace', 'logo': 'logos/LogoTrace.png', 'url': '/launch/Trace', 'desc': '<strong>Trace App</strong><br>Tracciamento percorsi.<br>Funzioni: GPS, logging dati, visualizzazione mappe.', 'details': '<h3>Trace App</h3><p>Applicazione per il tracciamento e monitoraggio di percorsi.</p><ul><li>GPS ad alta precisione</li><li>Logging dati automatico</li><li>Visualizzazione mappe interattive</li><li>Analisi percorsi</li></ul>', 'secret': False},
        {'name': 'ProfileAnalysis', 'logo': 'logos/LogoTrace.png', 'url': '#', 'desc': '<strong>ProfileAnalysis App</strong><br>Analisi profili avanzata.<br>Funzioni: statistiche, report, insights.', 'details': '<h3>ProfileAnalysis App</h3><p>Strumento per l\'analisi dettagliata dei profili.</p><ul><li>Statistiche avanzate</li><li>Report personalizzati</li><li>Insights predittivi</li><li>Integrazione dati</li></ul>', 'secret': True},
        {'name': 'Layout', 'logo': 'logos/LogoLayout.png', 'url': '/launch/Layout', 'desc': '<strong>Layout App</strong><br>Strumento per design layout.<br>Funzioni: griglie, allineamenti, esportazione.', 'details': '<h3>Layout App</h3><p>Strumento professionale per creare layout di design.</p><ul><li>Griglie responsive</li><li>Allineamenti automatici</li><li>Esportazione in vari formati</li><li>Collaborazione in tempo reale</li></ul>', 'secret': False},
    ]
    return render_template('index.html', apps=apps)

@app.route('/launch/<app_name>')
def launch_app(app_name):
    if app_name not in APP_FOLDERS:
        return redirect(url_for('splash'))
    
    app_info = APP_FOLDERS[app_name]
    app_folder = app_info['folder']
    port = app_info['port']
    app_path = os.path.join(os.path.dirname(__file__), app_folder, 'app.py')
    
    if not os.path.exists(app_path):
        return f'<h1>Error</h1><p>App file not found for {app_name}</p><a href="/">Back to main page</a>'
    
    # Check if already running
    if app_name in running_apps and running_apps[app_name].is_alive():
        return f'''<h1>{app_name} is already running!</h1>
                  <p>Open it at: <a href="http://127.0.0.1:{port}" target="_blank">http://127.0.0.1:{port}</a></p>
                  <a href="/">Back to main page</a>'''
    
    # Start app in a separate thread
    def run_app():
        import sys
        import importlib.util
        
        # Get app directory
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), app_folder))
        
        # CRITICAL: Change to app directory FIRST
        original_dir = os.getcwd()
        os.chdir(app_dir)
        print(f"[PyPottery] Changed directory to: {os.getcwd()}")
        
        # Add app directory to Python path at the beginning
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        
        try:
            # Load the app module with the new working directory
            spec = importlib.util.spec_from_file_location(f"{app_name}_app", app_path)
            sub_app_module = importlib.util.module_from_spec(spec)
            
            # Add to sys.modules to make it importable
            sys.modules[f"{app_name}_app"] = sub_app_module
            
            # Execute in the module's namespace
            spec.loader.exec_module(sub_app_module)
            
            # CRITICAL: Call the start_server function
            if hasattr(sub_app_module, 'start_server'):
                print(f"[PyPottery] Starting Flask app on port {port}...")
                sub_app_module.start_server(port=port, open_browser=False)
            elif hasattr(sub_app_module, 'app'):
                # Fallback: start app directly if start_server not available
                print(f"[PyPottery] Starting Flask app directly on port {port}...")
                sub_app_module.app.run(
                    host='0.0.0.0',
                    port=port,
                    debug=False,
                    threaded=True,
                    use_reloader=False
                )
            else:
                print(f"[PyPottery] ERROR: No 'app' or 'start_server' found in {app_name}")
            
        except Exception as e:
            print(f"[PyPottery] Error starting {app_name}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Don't restore directory - keep it in app folder for the thread
            pass
    
    # Start in daemon thread
    thread = threading.Thread(target=run_app, daemon=True, name=f"PyPottery-{app_name}")
    thread.start()
    running_apps[app_name] = thread
    
    # Wait a moment and redirect
    time.sleep(1)
    
    return f'''<html>
    <head>
        <meta http-equiv="refresh" content="2;url=http://127.0.0.1:{port}">
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto; }}
            h1 {{ color: #333; }}
            .spinner {{ border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            a {{ color: #3498db; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Launching {app_name}...</h1>
            <div class="spinner"></div>
            <p>Starting server on <strong>http://127.0.0.1:{port}</strong></p>
            <p>You will be redirected automatically in 2 seconds...</p>
            <p><a href="http://127.0.0.1:{port}">Click here if not redirected</a></p>
            <hr>
            <p><a href="/">← Back to main page</a></p>
        </div>
    </body>
    </html>'''

if __name__ == '__main__':
    app.run(debug=True)