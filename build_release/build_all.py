"""
Build All Release Packages for PyPottery Suite Launcher

Master build script that creates releases for all platforms.
"""

import sys
import platform
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    print("=" * 70)
    print("🚀 PyPottery Suite Launcher - Release Builder")
    print("=" * 70)
    print()
    
    current_os = platform.system()
    
    print(f"Current platform: {current_os}")
    print()
    
    releases = []
    
    # Build Unix releases (macOS + Linux with embedded Python)
    print("📦 Building Unix (macOS/Linux) releases with embedded Python...")
    print("-" * 50)
    try:
        from build_unix_release import create_unix_release
        unix_packages = create_unix_release()
        for name, path in unix_packages:
            if path and path.exists():
                releases.append((name, path))
    except Exception as e:
        print(f"   ⚠️ Unix build failed: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Build Windows release (requires Windows for embedded Python)
    if current_os == "Windows":
        print("📦 Building Windows release...")
        print("-" * 50)
        try:
            from build_windows_release import create_release_package
            win_zip = create_release_package()
            if win_zip and win_zip.exists():
                releases.append(("Windows", win_zip))
        except Exception as e:
            print(f"   ⚠️ Windows build failed: {e}")
    else:
        print("⚠️  Skipping Windows release (requires Windows to build)")
    
    print()
    print("=" * 70)
    print("🎉 ALL BUILDS COMPLETE!")
    print("=" * 70)
    print()
    
    if releases:
        print("📦 Created packages:")
        for name, path in releases:
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"   • {name}: {path.name} ({size_mb:.1f} MB)")
            except Exception:
                print(f"   • {name}: {path}")
    else:
        print("⚠️  No packages were created.")
    
    print()
    print("📤 Upload these to GitHub Releases!")
    print()


if __name__ == "__main__":
    main()
