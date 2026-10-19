# Pixbit

**A personal game hub for community decompilation and port projects.**

Pixbit is an early-stage prototype exploring a simple idea: choose a supported game, let a host computer prepare and build its community project, keep it in a local library, then play it from an Android phone over the local network.

> **Status:** Prototype. The workflow below describes the project goal; support for individual games, host setup, Android playback, and automatic builds is still being developed.

## The idea

Pixbit aims to bring a Roblox-like library-and-launcher experience to supported decompilation and native-port projects, while the games run on computers you control.

1. Search for a game by title.
2. Find its community source repository and supported build instructions.
3. Check the host computer for the tools that project needs.
4. Install missing tools and show progress and errors.
5. Clone the source into the local game library, or reuse the existing clone.
6. Prepare the game using its documented build process and user-provided game data where required.
7. Add the finished build to the library.
8. Launch it immediately or start it automatically after a 10-second countdown.
9. Connect from Android to play a game running on your host computer.

## Planned workflow

### 1. Search the game catalog

The prototype uses [Samidy's Decomps catalog](https://decomps.samidy.com/) as a discovery source. The user enters a title, reviews matching games, and selects one.

Catalog entries should include the game title, source repository, platform, and project-specific setup notes. Catalog pages and repository metadata can change, so Pixbit should validate links before starting a build.

### 2. Check host requirements

Before preparing a project, Pixbit should check for the requirements it actually needs, such as Git, a compiler toolchain, CMake, or Ninja. Requirements should be determined by the selected game's build instructions rather than assumed to be identical for every project.

For missing requirements, Pixbit should explain what it will install, show installation progress, and report failures clearly. The host owner remains in control of system-level changes.

### 3. Create or reuse the local game

Pixbit should keep a configurable library directory on the host computer.

- If the selected project's repository is already cloned in the library, reuse it instead of downloading a second copy.
- If it is not present, clone the repository and its required submodules.
- Keep project build files, logs, and library metadata organized per game.
- Make updates to an existing checkout explicit and avoid overwriting user changes.

### 4. Prepare game data and build

Some projects require original game data to build or run. Pixbit should let the user select a locally supplied copy, check the required filename and any project-documented hashes, and explain where it needs to go.

Pixbit does **not** provide or link to downloads of commercial game ROMs. Users are responsible for supplying game data they are legally entitled to use. Pixbit should not redistribute copyrighted game data.

Build steps must follow the selected project's own documentation. A single generic CMake command will not work for every decompilation or port project.

### 5. Show progress and launch

All lengthy operations should provide visible progress, including catalog lookup, dependency checks, repository cloning, game-data validation, and building. Errors should identify the failed step and offer a useful log or next action.

When a build completes, Pixbit should offer:

- **Launch now**
- **Launch automatically in 10 seconds**, with a way to cancel the countdown

### 6. Play from Android

The intended setup runs the game on a host computer and lets an Android phone connect to it over the local network. The exact streaming, controller, pairing, and network-security approach is still to be chosen and implemented.

## Project boundaries

- Pixbit is a launcher and library prototype, not a tool that creates decompilations from commercial game binaries.
- Each game remains subject to its upstream project's license and build requirements.
- Game source repositories are maintained by their respective authors. Pixbit should link to and respect those projects rather than implying they are official Pixbit releases.
- The host computer stores and runs the game builds; Android playback is a separate part of the prototype.

## Current status

This repository is at the planning and prototyping stage. The main areas to build are:

- Catalog search and reliable game metadata
- Per-project build recipes and dependency checks
- A local library that detects and reuses existing checkouts
- Clear progress reporting and recoverable errors
- Host-to-Android playback and controller support
- A safe, user-controlled flow for any required game data

## Contributing

This is an experimental personal project. Issues and pull requests describing supported decompilation or port projects, host compatibility, and Android playback approaches are welcome. Please do not submit copyrighted game data, download links to unauthorized ROM sources, or credentials.

## License

A project license has not been selected yet. Until one is added, do not assume the Pixbit source is licensed for reuse. Each game project linked by Pixbit has its own license.
