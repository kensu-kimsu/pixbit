#!/usr/bin/env python3
"""Pixbit's first host-side prototype: search a catalog and manage local checkouts."""

from __future__ import annotations

import argparse
import html
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import hashlib
import json
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from shutil import copyfileobj


CATALOG_URL = "https://decomps.samidy.com/"
USER_AGENT = "Pixbit/0.1 (+https://github.com/kensu-kimsu/pixbit)"


class CatalogParser(HTMLParser):
    """Collect links whose destination is a public GitHub repository."""

    def __init__(self) -> None:
        super().__init__()
        self._href = ""
        self._text: list[str] = []
        self.entries: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a":
            return
        href = urllib.parse.urljoin(CATALOG_URL, html.unescape(self._href.strip()))
        parsed = urllib.parse.urlparse(href)
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc.lower() not in {"github.com", "www.github.com"} or len(parts) < 2:
            self._href = ""
            self._text = []
            return
        owner, repo = parts[0], parts[1].removesuffix(".git")
        if owner.lower() in {"features", "topics", "sponsors", "login", "signup"}:
            self._href = ""
            self._text = []
            return
        title = " ".join("".join(self._text).split()) or repo.replace("-", " ")
        repo_url = f"https://github.com/{owner}/{repo}"
        self.entries.append((title, repo_url))
        self._href = ""
        self._text = []


def ensure_git() -> str:
    git = shutil.which("git")
    if git:
        print(f"[✓] Git found: {git}")
        return git

    if platform.system() != "Windows":
        raise RuntimeError("Git is required. Install Git, reopen the terminal, and run Pixbit again.")
    if not shutil.which("winget"):
        raise RuntimeError("Git is missing and winget was not found. Install Git for Windows, then retry.")

    print("[!] Git is missing. Installing Git for Windows with winget...")
    subprocess.run(
        ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget",
         "--accept-package-agreements", "--accept-source-agreements"],
        check=True,
    )
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git was installed, but this terminal cannot find it yet. Reopen the terminal and retry.")
    return git


def fetch_catalog() -> list[tuple[str, str]]:
    print("[1/4] Loading the community game catalog...")
    request = urllib.request.Request(CATALOG_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            page = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not load {CATALOG_URL}: {exc}") from exc

    parser = CatalogParser()
    parser.feed(page)
    unique: dict[str, tuple[str, str]] = {}
    for title, url in parser.entries:
        unique[url.lower()] = (title, url)
    entries = sorted(unique.values(), key=lambda item: item[0].casefold())
    if not entries:
        raise RuntimeError("No GitHub project links were found. The catalog page may have changed.")
    print(f"[✓] Found {len(entries)} GitHub project links.")
    return entries


def game_folder_name(title: str, repo_url: str) -> str:
    """Use a short stable name to leave room for deep Windows submodule paths."""
    path_parts = [part for part in urllib.parse.urlparse(repo_url).path.strip("/").split("/") if part]
    repo = path_parts[-1].removesuffix(".git") if path_parts else "game"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", repo).strip("-._")[:24] or "game"
    suffix = hashlib.sha1(repo_url.lower().encode("utf-8")).hexdigest()[:7]
    return f"{slug}-{suffix}"


def select_game(entries: list[tuple[str, str]], query: str) -> tuple[str, str]:
    matches = [(title, url) for title, url in entries if query.casefold() in title.casefold()]
    if not matches:
        raise RuntimeError(f"No catalog entries matched {query!r}.")
    print(f"\n[2/4] Matches for {query!r}:")
    for index, (title, url) in enumerate(matches[:30], start=1):
        print(f"  {index:>2}. {title}  ({url})")
    while True:
        choice = input("Select a game number (or Q to quit): ").strip()
        if choice.lower() == "q":
            raise SystemExit(0)
        if choice.isdigit() and 1 <= int(choice) <= min(len(matches), 30):
            return matches[int(choice) - 1]
        print("Enter one of the listed numbers, or Q to quit.")


def prepare_checkout(title: str, repo_url: str, library: Path) -> Path:
    folder = library / game_folder_name(title, repo_url)
    checkout = folder / "src"
    existing = checkout if (checkout / ".git").is_dir() else folder if (folder / ".git").is_dir() else None
    if existing is not None:
        checkout = existing
        print(f"[3/5] Existing clone found; reusing it: {checkout}")
        status = subprocess.run(
            ["git", "-C", str(checkout), "submodule", "status", "--recursive"],
            capture_output=True, text=True,
        )
        if status.returncode != 0:
            raise RuntimeError(f"Could not inspect existing checkout submodules:\n{status.stderr.strip()}")
        if any(line.startswith("-") for line in status.stdout.splitlines()):
            print("Some submodules are missing; fetching only those submodules...")
            subprocess.run(
                ["git", "-c", "core.longpaths=true", "-C", str(checkout),
                 "submodule", "update", "--init", "--recursive", "--progress"],
                check=True,
            )
        return checkout
    if checkout.exists() and any(checkout.iterdir()):
        raise RuntimeError(f"The target folder exists but is not a Git checkout: {checkout}")

    folder.mkdir(parents=True, exist_ok=True)
    print(f"[3/5] Cloning {repo_url} into {checkout}")
    print("Git will display clone progress below.")
    try:
        subprocess.run(
            ["git", "-c", "core.longpaths=true", "clone", "--progress", "--recursive", repo_url, str(checkout)],
            check=True,
        )
    except subprocess.CalledProcessError:
        # The target is a short, Pixbit-generated directory. Remove only this failed partial clone
        # so the next run does not mistake an incomplete checkout for a completed one.
        if checkout.exists():
            shutil.rmtree(checkout, ignore_errors=True)
        raise
    return checkout


def get_windows_release(repo_url: str) -> dict | None:
    parsed = urllib.parse.urlparse(repo_url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.netloc.lower() != "github.com" or len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    request = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            release = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    assets = release.get("assets", [])
    windows_assets = [
        asset for asset in assets
        if re.search(r"windows|win(?:32|64|[-_ ]?x64)", asset.get("name", ""), re.IGNORECASE)
        and Path(asset.get("name", "")).suffix.lower() in {".zip", ".exe"}
    ]
    if not windows_assets:
        return None
    # Prefer a ZIP because Windows releases commonly bundle runtime files with the executable.
    asset = next((a for a in windows_assets if a["name"].lower().endswith(".zip")), windows_assets[0])
    return {"tag": release.get("tag_name", "latest"), "asset": asset}


def download_with_progress(url: str, destination: Path, total_size: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    destination.parent.mkdir(parents=True, exist_ok=True)
    received = 0
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            received += len(chunk)
            if total_size:
                percent = min(100, int(received * 100 / total_size))
                bar = "#" * (percent // 5) + "-" * (20 - percent // 5)
                print(f"\rDownloading [{bar}] {percent:3d}%", end="", flush=True)
    print()
    if total_size and received != total_size:
        raise RuntimeError(f"Download size mismatch: expected {total_size} bytes, received {received}.")


def safe_extract_zip(archive_path: Path, destination: Path) -> None:
    base = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            target = (destination / info.filename).resolve()
            if target != base and base not in target.parents:
                raise RuntimeError(f"Unsafe path in release ZIP: {info.filename}")
        archive.extractall(destination)


def find_executable(folder: Path) -> Path | None:
    candidates = sorted(
        (path for path in folder.rglob("*.exe") if "uninstall" not in path.name.casefold()),
        key=lambda path: ("setup" in path.name.casefold(), len(path.parts), path.name.casefold()),
    )
    return candidates[0] if candidates else None


def install_official_windows_release(title: str, repo_url: str, library: Path) -> Path | None:
    release = get_windows_release(repo_url)
    if release is None:
        print("[i] No latest Windows ZIP/EXE release found; falling back to the source repository.")
        return None

    folder = library / game_folder_name(title, repo_url)
    app_dir = folder / "app"
    existing_exe = find_executable(app_dir) if app_dir.is_dir() else None
    if existing_exe:
        print(f"[3/5] Existing official app found; reusing it: {existing_exe}")
        return existing_exe

    asset = release["asset"]
    archive_path = folder / asset["name"]
    print(f"[3/5] Downloading official Windows release {release['tag']} from GitHub...")
    download_with_progress(asset["browser_download_url"], archive_path, int(asset.get("size", 0)))
    digest = asset.get("digest", "")
    if digest.startswith("sha256:"):
        hasher = hashlib.sha256()
        with archive_path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                hasher.update(block)
        if hasher.hexdigest().lower() != digest.split(":", 1)[1].lower():
            archive_path.unlink(missing_ok=True)
            raise RuntimeError("GitHub release SHA-256 check failed; the downloaded file was removed.")

    staging = folder / "app-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix.lower() == ".zip":
        safe_extract_zip(archive_path, staging)
    else:
        shutil.copy2(archive_path, staging / archive_path.name)
    executable = find_executable(staging)
    if executable is None:
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError("The official release package did not contain a Windows .exe file.")
    if app_dir.exists():
        shutil.rmtree(app_dir)
    staging.rename(app_dir)
    archive_path.unlink(missing_ok=True)
    installed = app_dir / executable.relative_to(staging)
    print(f"[✓] Official app installed: {installed}")
    return installed


def configure_rom_folder_for_app() -> Path | None:
    folder = configure_rom_folder()
    if folder:
        print(f"When the game opens, choose your game file from: {folder}")
    return folder


def launch_choice(executable: Path) -> None:
    choice = input("Launch now, launch in 10 seconds, or skip? [now/10/skip]: ").strip().lower()
    if choice in {"now", "n", "yes", "y"}:
        delay = 0
    elif choice in {"10", "wait", "later"}:
        delay = 10
    else:
        print("[i] Launch skipped.")
        return
    for remaining in range(delay, 0, -1):
        print(f"Launching in {remaining} seconds... (Ctrl+C to cancel)")
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[i] Launch cancelled.")
            return
    subprocess.Popen([str(executable)], cwd=str(executable.parent))
    print(f"[✓] Launched: {executable}")


ROM_EXTENSIONS = {".z64", ".v64", ".n64", ".iso", ".bin", ".wad", ".rom"}
CONFIG_PATH = Path.home() / ".pixbit" / "config.json"


def load_config() -> dict[str, str]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict[str, str]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def configure_rom_folder() -> Path | None:
    config = load_config()
    saved = config.get("rom_folder", "")
    if saved and Path(saved).is_dir():
        print(f"[✓] Using saved local game-data folder: {saved}")
        return Path(saved)

    print("Pixbit can remember a local folder containing your legally obtained game data.")
    print("It cannot search or download commercial ROMs from ConsoleRoms or similar sites.")
    value = input("Local ROM folder (Enter to skip): ").strip().strip('"')
    if not value:
        return None
    folder = Path(value).expanduser()
    if not folder.is_dir():
        raise RuntimeError(f"ROM folder does not exist: {folder}")
    config["rom_folder"] = str(folder.resolve())
    save_config(config)
    print(f"[✓] Saved game-data folder in {CONFIG_PATH}")
    return folder


def find_game_data(folder: Path, title: str) -> list[Path]:
    """Find likely local game files by filename, without contacting ROM sites."""
    words = set(re.findall(r"[a-z0-9]+", title.casefold()))
    words -= {"the", "a", "an", "native", "port", "decomp", "decompilation", "recomp", "usa", "n64"}
    if not words:
        return []
    found: list[tuple[int, Path]] = []
    try:
        for path in folder.rglob("*"):
            if not path.is_file() or (path.suffix.lower() != ".zip" and path.suffix.lower() not in ROM_EXTENSIONS):
                continue
            filename_words = set(re.findall(r"[a-z0-9]+", path.stem.casefold()))
            overlap = len(words & filename_words)
            if overlap >= max(2, (len(words) + 1) // 2):
                found.append((overlap, path))
    except OSError as exc:
        raise RuntimeError(f"Could not search local ROM folder {folder}: {exc}") from exc
    return [path for _, path in sorted(found, key=lambda item: (-item[0], str(item[1]).casefold()))]


def _rom_candidates(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    return [
        info for info in archive.infolist()
        if not info.is_dir() and Path(info.filename).suffix.lower() in ROM_EXTENSIONS
    ]


def prepare_user_game_data(checkout: Path, title: str) -> None:
    """Find a user-provided ROM locally and copy/extract it into the project root."""
    print("[4/5] Game data setup")
    folder = configure_rom_folder()
    if folder is None:
        print("[i] Skipped game data setup.")
        return
    candidates = find_game_data(folder, title)
    if not candidates:
        print(f"[i] No local ROM or ZIP filename matched {title!r} in {folder}.")
        print("Add your legally obtained game data to that folder and run Pixbit again.")
        return
    print("Matching local game-data files:")
    for index, path in enumerate(candidates[:20], 1):
        print(f"  {index}. {path}")
    if len(candidates) == 1:
        source = candidates[0]
    else:
        while True:
            choice = input(f"Select a file (1-{min(len(candidates), 20)}): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= min(len(candidates), 20):
                source = candidates[int(choice) - 1]
                break
            print("Enter one of the listed numbers.")

    chosen_name = source.name
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            candidates = _rom_candidates(archive)
            if not candidates:
                raise RuntimeError("The ZIP contains no supported ROM file (.z64, .v64, .n64, .iso, .bin, .wad, .rom).")
            if len(candidates) == 1:
                selected = candidates[0]
            else:
                print("ROM files found in the archive:")
                for index, info in enumerate(candidates, 1):
                    print(f"  {index}. {Path(info.filename).name} ({info.file_size:,} bytes)")
                while True:
                    choice = input(f"Choose a file (1-{len(candidates)}): ").strip()
                    if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                        selected = candidates[int(choice) - 1]
                        break
                    print("Enter one of the listed numbers.")
            chosen_name = Path(selected.filename).name
            default_target = chosen_name
            target_name = input(f"Filename required by this project [{default_target}]: ").strip() or default_target
            if Path(target_name).name != target_name or Path(target_name).suffix.lower() not in ROM_EXTENSIONS:
                raise RuntimeError("Enter a ROM filename only, with a supported extension, such as baserom.z64.")
            destination = checkout / target_name
            if destination.exists():
                overwrite = input(f"{destination.name} already exists. Replace it? (y/N): ").strip().lower()
                if overwrite != "y":
                    print("[i] Kept existing game data file.")
                    return
            with archive.open(selected) as source_file, destination.open("wb") as target_file:
                copyfileobj(source_file, target_file)
    else:
        target_name = input(f"Filename required by this project [{chosen_name}]: ").strip() or chosen_name
        if Path(target_name).name != target_name or Path(target_name).suffix.lower() not in ROM_EXTENSIONS:
            raise RuntimeError("Enter a ROM filename only, with a supported extension, such as baserom.z64.")
        destination = checkout / target_name
        if destination.exists():
            overwrite = input(f"{destination.name} already exists. Replace it? (y/N): ").strip().lower()
            if overwrite != "y":
                print("[i] Kept existing game data file.")
                return
        shutil.copy2(source, destination)

    print(f"[✓] Game data copied to: {destination}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pixbit: prototype game catalog and local source library manager")
    parser.add_argument("--library", type=Path, default=Path.home() / "p",
                        help="local folder for supported game projects")
    args = parser.parse_args()

    print("Pixbit prototype — local library setup")
    print("Pixbit prefers official Windows app releases where available, then falls back to source checkouts.\n")
    try:
        ensure_git()
        query = input("Game title to search for: ").strip()
        if not query:
            raise RuntimeError("Enter a game title to search for.")
        entries = fetch_catalog()
        title, repo_url = select_game(entries, query)
        library = args.library.expanduser()
        executable = install_official_windows_release(title, repo_url, library)
        if executable:
            configure_rom_folder_for_app()
            launch_choice(executable)
            print(f"\n[5/5] Ready in the local Pixbit library: {executable.parent}")
        else:
            checkout = prepare_checkout(title, repo_url, library)
            prepare_user_game_data(checkout, title)
            print(f"\n[5/5] Added source to the local Pixbit library: {checkout}")
            print("This source-only path still needs a project-specific build recipe before it can make an EXE.")
        print("Android streaming is not implemented yet.")
        return 0
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f"\n[!] Pixbit stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
