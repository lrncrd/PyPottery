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
        ]

        # Check if all files exist
        if all(f.exists() for f in required_files):
            return True

        print("Offline vendor assets missing or incomplete. Downloading assets...")
        return self._download_vendor_assets()

    def _download_vendor_assets(self) -> bool:
        """
        Download Bootstrap 5, Bootstrap Icons v1.11.3, and Plus Jakarta Sans fonts.
        """
        try:
            os.makedirs(self.shared_vendor_path / "bootstrap" / "css", exist_ok=True)
            os.makedirs(self.shared_vendor_path / "bootstrap" / "js", exist_ok=True)
            os.makedirs(self.shared_vendor_path / "bootstrap-icons" / "fonts", exist_ok=True)
            os.makedirs(self.shared_vendor_path / "fonts" / "files", exist_ok=True)

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

            # 3. Download Plus Jakarta Sans Fonts
            print("  [Vendor] Downloading Plus Jakarta Sans fonts...")
            font_files = {
                'plus-jakarta-sans-v8-latin-700.woff2': 'https://cdn.jsdelivr.net/npm/@fontsource/plus-jakarta-sans@5.0.19/files/plus-jakarta-sans-latin-700-normal.woff2',
                'plus-jakarta-sans-v8-latin-800.woff2': 'https://cdn.jsdelivr.net/npm/@fontsource/plus-jakarta-sans@5.0.19/files/plus-jakarta-sans-latin-800-normal.woff2'
            }

            for fname, url in font_files.items():
                req = urllib.request.Request(url, headers=headers)
                with _open_url_resilient(req, timeout=20) as resp, open(self.shared_vendor_path / "fonts" / "files" / fname, 'wb') as f:
                    f.write(resp.read())

            fonts_css = '''/* Local Plus Jakarta Sans Font Definition */
@font-face {
  font-family: 'Plus Jakarta Sans';
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url('./files/plus-jakarta-sans-v8-latin-700.woff2') format('woff2');
}

@font-face {
  font-family: 'Plus Jakarta Sans';
  font-style: normal;
  font-weight: 800;
  font-display: swap;
  src: url('./files/plus-jakarta-sans-v8-latin-800.woff2') format('woff2');
}
'''
            with open(self.shared_vendor_path / "fonts" / "fonts.css", 'w', encoding='utf-8') as f:
                f.write(fonts_css)

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
