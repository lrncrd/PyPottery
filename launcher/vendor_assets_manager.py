"""
Vendor Assets Manager for PyPottery Suite
Handles central downloading, caching, and distribution of offline web assets (Bootstrap, Bootstrap Icons, Fonts)
"""

import os
import shutil
import urllib.request
from pathlib import Path
from typing import Optional


import ssl
import urllib.error


def _open_url_resilient(url_or_req, timeout: int = 20):
    """
    Open URL with automatic SSL context handling (standard certs, certifi, unverified fallback).
    Prevents silent failures on macOS when Python root certs are not configured.
    """
    try:
        return urllib.request.urlopen(url_or_req, timeout=timeout)
    except urllib.error.URLError as e:
        # Check if SSL verification failed
        if isinstance(e.reason, ssl.SSLCertVerificationError) or "certificate verify failed" in str(e):
            ctx = ssl._create_unverified_context()
            return urllib.request.urlopen(url_or_req, timeout=timeout, context=ctx)
        raise
    except ssl.SSLCertVerificationError:
        ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(url_or_req, timeout=timeout, context=ctx)


class VendorAssetsManager:
    """
    Manages offline vendor web assets (CSS, JS, Fonts) for PyPottery Suite.
    Ensures assets exist centrally and propagates them to individual modular apps.
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path).resolve()
        self.shared_vendor_path = self.base_path / "shared_assets" / "vendor"

    def ensure_vendor_assets(self) -> bool:
        """
        Check if shared vendor assets exist. Download them if missing.
        """
        required_files = [
            self.shared_vendor_path / "bootstrap" / "css" / "bootstrap.min.css",
            self.shared_vendor_path / "bootstrap" / "js" / "bootstrap.bundle.min.js",
            self.shared_vendor_path / "bootstrap-icons" / "bootstrap-icons.min.css",
            self.shared_vendor_path / "bootstrap-icons" / "fonts" / "bootstrap-icons.woff2",
            self.shared_vendor_path / "fonts" / "fonts.css",
            self.shared_vendor_path / "fonts" / "files" / "plus-jakarta-sans-v8-latin-400.woff2",
            self.shared_vendor_path / "fonts" / "files" / "jetbrains-mono-v1-latin-400.woff2",
            self.shared_vendor_path / "xlsx" / "xlsx.full.min.js",
        ]

        # Check if all files exist
        if all(f.exists() for f in required_files):
            return True

        print("Offline vendor assets missing or incomplete. Downloading assets...")
        return self._download_vendor_assets()

    def _download_vendor_assets(self) -> bool:
        """
        Download Bootstrap 5, Bootstrap Icons v1.11.3, Plus Jakarta Sans + JetBrains Mono fonts and SheetJS (xlsx).
        """
        try:
            os.makedirs(self.shared_vendor_path / "bootstrap" / "css", exist_ok=True)
            os.makedirs(self.shared_vendor_path / "bootstrap" / "js", exist_ok=True)
            os.makedirs(self.shared_vendor_path / "bootstrap-icons" / "fonts", exist_ok=True)
            os.makedirs(self.shared_vendor_path / "fonts" / "files", exist_ok=True)
            os.makedirs(self.shared_vendor_path / "xlsx", exist_ok=True)

            headers = {'User-Agent': 'PyPotterySuite/1.0'}

            # 1. Download Bootstrap 5 CSS & JS
            print("  [Vendor] Downloading Bootstrap 5 CSS & JS...")
            req = urllib.request.Request('https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css', headers=headers)
            with _open_url_resilient(req, timeout=20) as resp, open(self.shared_vendor_path / "bootstrap" / "css" / "bootstrap.min.css", 'wb') as f:
                f.write(resp.read())

            req = urllib.request.Request('https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js', headers=headers)
            with _open_url_resilient(req, timeout=20) as resp, open(self.shared_vendor_path / "bootstrap" / "js" / "bootstrap.bundle.min.js", 'wb') as f:
                f.write(resp.read())

            # 2. Download Bootstrap Icons v1.11.3
            print("  [Vendor] Downloading Bootstrap Icons v1.11.3...")
            req = urllib.request.Request('https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css', headers=headers)
            with _open_url_resilient(req, timeout=20) as resp:
                css_content = resp.read().decode('utf-8')
                css_content = css_content.replace('url("fonts/', 'url("./fonts/').replace('url(fonts/', 'url(./fonts/')
                with open(self.shared_vendor_path / "bootstrap-icons" / "bootstrap-icons.min.css", 'w', encoding='utf-8') as f:
                    f.write(css_content)

            for font_name in ['bootstrap-icons.woff2', 'bootstrap-icons.woff']:
                req = urllib.request.Request(f'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/{font_name}', headers=headers)
                with _open_url_resilient(req, timeout=20) as resp, open(self.shared_vendor_path / "bootstrap-icons" / "fonts" / font_name, 'wb') as f:
                    f.write(resp.read())

            # 3. Download fonts (Plus Jakarta Sans = UI, JetBrains Mono = code/numbers)
            print("  [Vendor] Downloading Plus Jakarta Sans + JetBrains Mono fonts...")
            font_families = [
                # (CSS family, local file prefix, fontsource package, weights)
                ('Plus Jakarta Sans', 'plus-jakarta-sans-v8', 'plus-jakarta-sans', (400, 500, 600, 700, 800)),
                ('JetBrains Mono', 'jetbrains-mono-v1', 'jetbrains-mono', (400, 500, 600, 700)),
            ]
            fonts_css = "/* Local font definitions (generated by PyPottery launcher) */" + chr(10)
            for family, prefix, package, weights in font_families:
                for weight in weights:
                    fname = f'{prefix}-latin-{weight}.woff2'
                    url = f'https://cdn.jsdelivr.net/npm/@fontsource/{package}@5.0.19/files/{package}-latin-{weight}-normal.woff2'
                    req = urllib.request.Request(url, headers=headers)
                    with _open_url_resilient(req, timeout=20) as resp, open(self.shared_vendor_path / "fonts" / "files" / fname, 'wb') as f:
                        f.write(resp.read())
                    fonts_css += f"""
@font-face {{
  font-family: '{family}';
  font-style: normal;
  font-weight: {weight};
  font-display: swap;
  src: url('./files/{fname}') format('woff2');
}}
"""

            with open(self.shared_vendor_path / "fonts" / "fonts.css", 'w', encoding='utf-8') as f:
                f.write(fonts_css)

            # 4. Download SheetJS (Excel export in PyPotteryScan)
            print("  [Vendor] Downloading SheetJS (xlsx) 0.18.5...")
            req = urllib.request.Request('https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js', headers=headers)
            with _open_url_resilient(req, timeout=30) as resp, open(self.shared_vendor_path / "xlsx" / "xlsx.full.min.js", 'wb') as f:
                f.write(resp.read())

            print("  [Vendor] Offline vendor assets successfully installed!")
            return True
        except Exception as e:
            print(f"  [Vendor] Error downloading vendor assets: {e}")
            return False

    def sync_to_app(self, app_dir: Path) -> bool:
        """
        Synchronize shared vendor assets into a sub-application's static/vendor directory.
        """
        self.ensure_vendor_assets()
        target_vendor = Path(app_dir) / "static" / "vendor"

        try:
            os.makedirs(target_vendor.parent, exist_ok=True)

            # Copy shared_vendor contents to target_vendor
            if target_vendor.exists():
                shutil.rmtree(target_vendor)

            shutil.copytree(self.shared_vendor_path, target_vendor)
            print(f"  [Vendor] Synchronized vendor assets to {target_vendor}")

            # Also sync to app/static/vendor if present (e.g., PyPotteryScan)
            app_static = Path(app_dir) / "app" / "static"
            if app_static.exists():
                app_target = app_static / "vendor"
                if app_target.exists():
                    shutil.rmtree(app_target)
                shutil.copytree(self.shared_vendor_path, app_target)
                print(f"  [Vendor] Synchronized vendor assets to {app_target}")

            # Also sync to interactive_app/static/vendor if present (e.g., PyPotteryTrace)
            interactive_static = Path(app_dir) / "interactive_app" / "static"
            if interactive_static.exists():
                sub_target = interactive_static / "vendor"
                if sub_target.exists():
                    shutil.rmtree(sub_target)
                shutil.copytree(self.shared_vendor_path, sub_target)
                print(f"  [Vendor] Synchronized vendor assets to {sub_target}")

            return True
        except Exception as e:
            print(f"  [Vendor] Failed to sync assets to {app_dir}: {e}")
            return False
