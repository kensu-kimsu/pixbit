#!/usr/bin/env python3
"""Pixbit's first host-side prototype: search a catalog and manage local checkouts."""

from __future__ import annotations

import argparse
import html
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


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
    repo = urllib.parse.urlparse(repo_url).path.strip("/").replace("/", "-")
    readable = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-._")
    return f"{readable or 'game'}--{repo}"


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
    if (checkout / ".git").is_dir():
        print(f"[3/4] Existing clone found; reusing it: {checkout}")
        return checkout
    if checkout.exists() and any(checkout.iterdir()):
        raise RuntimeError(f"The target folder exists but is not a Git checkout: {checkout}")

    folder.mkdir(parents=True, exist_ok=True)
    print(f"[3/4] Cloning {repo_url} into {checkout}")
    print("Git will display clone progress below.")
    subprocess.run(["git", "clone", "--progress", "--recursive", repo_url, str(checkout)], check=True)
    return checkout


def main() -> int:
    parser = argparse.ArgumentParser(description="Pixbit: prototype game catalog and local source library manager")
    parser.add_argument("--library", type=Path, default=Path.home() / "Pixbit" / "library",
                        help="local folder for supported game projects")
    args = parser.parse_args()

    print("Pixbit prototype — local library setup")
    print("This version searches and clones source repositories; game builds and Android streaming are not implemented yet.\n")
    try:
        ensure_git()
        query = input("Game title to search for: ").strip()
        if not query:
            raise RuntimeError("Enter a game title to search for.")
        entries = fetch_catalog()
        title, repo_url = select_game(entries, query)
        checkout = prepare_checkout(title, repo_url, args.library.expanduser())
        print(f"\n[4/4] Added to the local Pixbit library: {checkout}")
        print("Next step: add a project-specific build recipe and user-supplied game data if that project requires it.")
        return 0
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f"\n[!] Pixbit stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
