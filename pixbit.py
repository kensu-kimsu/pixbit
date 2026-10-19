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
import urllib.error
import urllib.parse
import urllib.request
import hashlib
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
    checkout = folder
    if (checkout / ".git").is_dir():
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


ROM_EXTENSIONS = {".z64", ".v64", ".n64", ".iso", ".bin", ".wad", ".rom"}


def _rom_candidates(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    return [
        info for info in archive.infolist()
        if not info.is_dir() and Path(info.filename).suffix.lower() in ROM_EXTENSIONS
    ]


def prepare_user_game_data(checkout: Path) -> None:
    """Copy a user-provided ROM or extract one from ZIP into the project root."""
    print("[4/5] Game data setup")
    print("If this project needs a ROM, provide a local copy you are legally entitled to use.")
    print("Pixbit does not download commercial ROMs. Press Enter to skip this step for now.")
    source_text = input("Path to your ROM file or ZIP archive: ").strip().strip('"')
    if not source_text:
        print("[i] Skipped game data setup.")
        return

    source = Path(source_text).expanduser()
    if not source.is_file():
        raise RuntimeError(f"Game data file not found: {source}")

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
    print("This prototype searches and clones source repositories and can place a user-supplied ROM in the project folder.\n")
    try:
        ensure_git()
        query = input("Game title to search for: ").strip()
        if not query:
            raise RuntimeError("Enter a game title to search for.")
        entries = fetch_catalog()
        title, repo_url = select_game(entries, query)
        checkout = prepare_checkout(title, repo_url, args.library.expanduser())
        prepare_user_game_data(checkout)
        print(f"\n[5/5] Added to the local Pixbit library: {checkout}")
        print("Project-specific builds, automatic launch, and Android streaming are not implemented yet.")
        return 0
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f"\n[!] Pixbit stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
