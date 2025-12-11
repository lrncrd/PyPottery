"""
Update Checker for PyPottery Suite
Checks GitHub releases for new versions of applications
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import threading


@dataclass
class ReleaseInfo:
    """Information about a GitHub release"""
    tag_name: str
    name: str
    published_at: str
    html_url: str
    body: str  # Release notes
    prerelease: bool
    assets: List[Dict]  # Download assets


@dataclass
class UpdateInfo:
    """Update information for an application"""
    app_id: str
    current_version: Optional[str]
    latest_version: str
    update_available: bool
    release_notes: str
    download_url: str
    published_at: str


class UpdateChecker:
    """
    Checks for updates from GitHub releases.
    Supports caching to avoid excessive API calls.
    """
    
    GITHUB_API_BASE = "https://api.github.com/repos"
    CACHE_DURATION_HOURS = 2  # How long to cache release info
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".pypottery" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache_file = self.cache_dir / "releases_cache.json"
        self._cache: Dict = self._load_cache()
        
        # GitHub API token (optional, for higher rate limits)
        self._github_token = os.environ.get("GITHUB_TOKEN")
    
    def _load_cache(self) -> Dict:
        """Load cached release information"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"releases": {}, "last_check": {}}
    
    def _save_cache(self):
        """Save release information to cache"""
        try:
            with open(self._cache_file, "w") as f:
                json.dump(self._cache, f, indent=2)
        except IOError:
            pass
    
    def _is_cache_valid(self, repo_key: str) -> bool:
        """Check if cached data is still valid"""
        if repo_key not in self._cache.get("last_check", {}):
            return False
        
        last_check = datetime.fromisoformat(self._cache["last_check"][repo_key])
        return datetime.now() - last_check < timedelta(hours=self.CACHE_DURATION_HOURS)
    
    def _make_request(self, url: str) -> Optional[Dict]:
        """Make HTTP request to GitHub API"""
        headers = {
            "User-Agent": "PyPottery-Launcher",
            "Accept": "application/vnd.github.v3+json"
        }
        
        if self._github_token:
            headers["Authorization"] = f"token {self._github_token}"
        
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            if e.code == 404:
                return None  # Repo or release not found
            raise
        except (URLError, json.JSONDecodeError):
            return None
    
    def get_latest_release(self, owner: str, repo: str, 
                           include_prerelease: bool = False) -> Optional[ReleaseInfo]:
        """
        Get the latest release for a repository.
        
        Args:
            owner: GitHub repository owner
            repo: Repository name
            include_prerelease: Include pre-release versions
            
        Returns:
            ReleaseInfo or None if no releases found
        """
        repo_key = f"{owner}/{repo}"
        
        # Check cache first
        if self._is_cache_valid(repo_key):
            cached = self._cache["releases"].get(repo_key)
            if cached:
                return ReleaseInfo(**cached)
        
        # Fetch from GitHub API
        url = f"{self.GITHUB_API_BASE}/{owner}/{repo}/releases"
        
        releases = self._make_request(url)
        if not releases or not isinstance(releases, list):
            return None
        
        # Find latest release
        for release in releases:
            if release.get("draft"):
                continue
            if not include_prerelease and release.get("prerelease"):
                continue
            
            release_info = ReleaseInfo(
                tag_name=release.get("tag_name", ""),
                name=release.get("name", ""),
                published_at=release.get("published_at", ""),
                html_url=release.get("html_url", ""),
                body=release.get("body", ""),
                prerelease=release.get("prerelease", False),
                assets=release.get("assets", [])
            )
            
            # Cache the result
            self._cache["releases"][repo_key] = {
                "tag_name": release_info.tag_name,
                "name": release_info.name,
                "published_at": release_info.published_at,
                "html_url": release_info.html_url,
                "body": release_info.body,
                "prerelease": release_info.prerelease,
                "assets": release_info.assets
            }
            self._cache["last_check"][repo_key] = datetime.now().isoformat()
            self._save_cache()
            
            return release_info
        
        return None
    
    def get_all_releases(self, owner: str, repo: str, limit: int = 10) -> List[ReleaseInfo]:
        """
        Get all releases for a repository.
        
        Args:
            owner: GitHub repository owner
            repo: Repository name
            limit: Maximum number of releases to return
            
        Returns:
            List of ReleaseInfo objects
        """
        url = f"{self.GITHUB_API_BASE}/{owner}/{repo}/releases"
        releases = self._make_request(url)
        
        if not releases or not isinstance(releases, list):
            return []
        
        result = []
        for release in releases[:limit]:
            if release.get("draft"):
                continue
            
            result.append(ReleaseInfo(
                tag_name=release.get("tag_name", ""),
                name=release.get("name", ""),
                published_at=release.get("published_at", ""),
                html_url=release.get("html_url", ""),
                body=release.get("body", ""),
                prerelease=release.get("prerelease", False),
                assets=release.get("assets", [])
            ))
        
        return result
    
    def compare_versions(self, current: str, latest: str) -> int:
        """
        Compare version strings.
        
        Returns:
            -1 if current < latest (update available)
             0 if current == latest
             1 if current > latest
        """
        # Remove 'v' prefix if present
        current = current.lstrip("v").strip()
        latest = latest.lstrip("v").strip()
        
        # Handle "main" or "master" as always needing update from releases
        if current in ("main", "master"):
            return -1 if latest else 0
        
        try:
            # Split into parts and compare numerically
            current_parts = [int(x) for x in current.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]
            
            # Pad shorter version
            while len(current_parts) < len(latest_parts):
                current_parts.append(0)
            while len(latest_parts) < len(current_parts):
                latest_parts.append(0)
            
            for c, l in zip(current_parts, latest_parts):
                if c < l:
                    return -1
                if c > l:
                    return 1
            
            return 0
            
        except ValueError:
            # Fallback to string comparison
            if current < latest:
                return -1
            if current > latest:
                return 1
            return 0
    
    def check_for_update(self, owner: str, repo: str, 
                         current_version: Optional[str]) -> UpdateInfo:
        """
        Check if an update is available for an application.
        
        Args:
            owner: GitHub repository owner
            repo: Repository name
            current_version: Currently installed version
            
        Returns:
            UpdateInfo with update status
        """
        app_id = repo
        
        release = self.get_latest_release(owner, repo)
        
        if not release:
            return UpdateInfo(
                app_id=app_id,
                current_version=current_version,
                latest_version="unknown",
                update_available=False,
                release_notes="",
                download_url="",
                published_at=""
            )
        
        # Compare versions
        update_available = False
        if current_version:
            update_available = self.compare_versions(current_version, release.tag_name) < 0
        else:
            update_available = True  # Not installed = update available
        
        return UpdateInfo(
            app_id=app_id,
            current_version=current_version,
            latest_version=release.tag_name,
            update_available=update_available,
            release_notes=release.body or "",
            download_url=release.html_url,
            published_at=release.published_at
        )
    
    def check_all_updates(self, apps: Dict[str, Tuple[str, str, Optional[str]]],
                          callback: Optional[callable] = None) -> Dict[str, UpdateInfo]:
        """
        Check updates for multiple applications.
        
        Args:
            apps: Dict of {app_id: (owner, repo, current_version)}
            callback: Optional callback(app_id, update_info) for each result
            
        Returns:
            Dict of {app_id: UpdateInfo}
        """
        results = {}
        
        for app_id, (owner, repo, current_version) in apps.items():
            try:
                update_info = self.check_for_update(owner, repo, current_version)
                results[app_id] = update_info
                
                if callback:
                    callback(app_id, update_info)
                    
            except Exception as e:
                results[app_id] = UpdateInfo(
                    app_id=app_id,
                    current_version=current_version,
                    latest_version="error",
                    update_available=False,
                    release_notes=str(e),
                    download_url="",
                    published_at=""
                )
        
        return results
    
    def check_updates_async(self, apps: Dict[str, Tuple[str, str, Optional[str]]],
                           callback: callable) -> threading.Thread:
        """
        Check updates asynchronously in background thread.
        
        Args:
            apps: Dict of {app_id: (owner, repo, current_version)}
            callback: Callback(results: Dict[str, UpdateInfo]) when complete
            
        Returns:
            Thread object (already started)
        """
        def worker():
            results = self.check_all_updates(apps)
            callback(results)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread
    
    def clear_cache(self):
        """Clear all cached release information"""
        self._cache = {"releases": {}, "last_check": {}}
        if self._cache_file.exists():
            self._cache_file.unlink()
    
    def format_release_notes(self, body: str, max_length: int = 500) -> str:
        """Format release notes for display"""
        if not body:
            return "No release notes available."
        
        # Clean up markdown
        lines = body.strip().split("\n")
        cleaned = []
        
        for line in lines:
            # Remove markdown headers
            line = line.lstrip("#").strip()
            # Keep non-empty lines
            if line:
                cleaned.append(line)
        
        text = "\n".join(cleaned)
        
        if len(text) > max_length:
            text = text[:max_length-3] + "..."
        
        return text


# Convenience function for checking updates
def check_pypottery_updates(apps_config: Dict, 
                           installed_versions: Dict[str, Optional[str]]) -> Dict[str, UpdateInfo]:
    """
    Check for updates across all PyPottery applications.
    
    Args:
        apps_config: Application configuration from apps.json
        installed_versions: Dict of {app_id: installed_version or None}
        
    Returns:
        Dict of {app_id: UpdateInfo}
    """
    checker = UpdateChecker()
    
    apps = {}
    for app_id, config in apps_config.items():
        owner = config.get("repo_owner", "lrncrd")
        repo = config.get("repo_name", app_id)
        current = installed_versions.get(app_id)
        apps[app_id] = (owner, repo, current)
    
    return checker.check_all_updates(apps)


if __name__ == "__main__":
    # Test update checker
    print("Testing PyPottery Update Checker\n")
    
    checker = UpdateChecker()
    
    # Test repos
    test_repos = [
        ("lrncrd", "PyPotteryLayout"),
        ("lrncrd", "PyPotteryLens"),
        ("lrncrd", "PyPotteryInk"),
    ]
    
    for owner, repo in test_repos:
        print(f"Checking {owner}/{repo}...")
        
        update = checker.check_for_update(owner, repo, "0.1.0")
        
        print(f"  Current: {update.current_version}")
        print(f"  Latest:  {update.latest_version}")
        print(f"  Update available: {'Yes' if update.update_available else 'No'}")
        
        if update.release_notes:
            notes = checker.format_release_notes(update.release_notes, 200)
            print(f"  Notes: {notes}")
        
        print()
