# Pixbit

**A personal game hub for community decompilation and port projects.**

Pixbit is an early-stage prototype for discovering supported game projects, installing them on a host PC, keeping them in a local library, and eventually playing them from an Android phone over the local network.

> **Status:** The command-line prototype can search the catalog, install an official Windows release when one is available, and reuse or clone source checkouts otherwise. Android playback and generic source builds are not implemented yet.

## Try the prototype on your PC

### Requirements

- Python 3.10 or newer
- Git
- Internet access to the [Samidy Decomps catalog](https://decomps.samidy.com/) and GitHub

On Windows, Pixbit attempts to install Git with winget if Git is missing. If Git is not visible after installation, close and reopen the terminal, then run Pixbit again.

### Run

Open PowerShell in the Pixbit repository folder and run:

    py pixbit.py

Enter a game title and choose a matching catalog entry. Pixbit then:

1. Checks GitHub for the project's latest Windows ZIP or EXE release.
2. Downloads and extracts the official release when one is available, checking its SHA-256 digest when GitHub provides one.
3. Otherwise, clones the project source with submodules, or reuses the existing checkout and initializes missing submodules. Git's long-path option is enabled to reduce Windows filename-length errors.
4. Asks for a local folder containing your legally obtained game files. Pixbit remembers this folder in the config file described below.
5. For an official release, offers to launch the executable now, after a 10-second countdown, or not at all.

Choose a different library folder with:

    py pixbit.py --library "E:\Games\PixbitLibrary"

All release downloads, extracted apps, and source checkouts go under D:\\Games\\Play-decomp\\pixbit by default. Use --library to choose another location.\p.

### Remembered settings

Pixbit saves the local game-data folder in:

    %USERPROFILE%\.pixbit\config.json

To change the folder later, edit the rom_folder value in that file or remove the file to make Pixbit ask again.

## Game files and ROMs

Pixbit does **not** search for or download commercial ROMs from ConsoleRoms or similar websites. It uses a local folder you provide. For source-only projects, Pixbit looks for a likely matching ROM or ZIP by filename and can copy the selected file into the source checkout. It does not claim to identify the correct region or verify a game's identity unless the upstream project provides a hash.

Some projects handle game files differently. **Zelda 64: Recompiled**, for example, provides an official Windows release and asks you to select your North American game file in the game's own menu. Pixbit installs the application release; the ROM remains separate and is not converted into the executable.

Users are responsible for supplying game data they are legally entitled to use. Pixbit should not redistribute copyrighted game data.

## What is not implemented yet

- Generic build recipes for projects that only publish source code
- A full library interface and per-game metadata
- Automatic launch for source-only projects after building
- Android streaming and controller support
- Reliable project-specific game-data filenames and hash validation

A single CMake command will not build every decompilation or port project. Pixbit will need project-specific recipes for source-only games.

## Project boundaries

- Pixbit is a launcher and library prototype, not a tool that creates decompilations from commercial game binaries.
- Each game remains subject to its upstream project's license and requirements.
- Game releases and repositories are maintained by their respective authors. Pixbit should link to and respect those projects rather than imply they are official Pixbit releases.
- The host PC stores and runs the game builds; Android playback is a separate part of the prototype.

## Contributing

This is an experimental personal project. Issues and pull requests describing supported projects, host compatibility, and Android playback approaches are welcome. Do not submit copyrighted game data, links to unauthorized ROM downloads, or credentials.

## License

A project license has not been selected yet. Until one is added, do not assume the Pixbit source is licensed for reuse. Each game project linked by Pixbit has its own license.
