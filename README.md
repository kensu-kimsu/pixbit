# Pixbit

**A personal game hub for community decompilation and port projects.**

Pixbit is an early-stage prototype exploring a simple idea: choose a supported game, prepare its community source on a host computer, keep it in a local library, and eventually play it from an Android phone over the local network.

> **Status:** The command-line prototype can search the catalog, clone or reuse a local source checkout, and copy a user-supplied ROM or ROM archive into the project folder. Building games, Android playback, and the full library experience are not implemented yet.

## Try the prototype on your PC

### Requirements

- Python 3.10 or newer
- Git
- Internet access to the [Samidy Decomps catalog](https://decomps.samidy.com/) and GitHub

On Windows, Pixbit attempts to install Git with winget if Git is missing. If the new Git install is not visible in the current terminal, close and reopen the terminal, then run Pixbit again.

### Run

Download or clone this repository, open a terminal in its folder, and run:

```powershell
py pixbit.py
```

Pixbit asks for a game title, shows matching catalog entries that link directly to GitHub, and asks you to select one. It clones the selected repository into your local library and includes its Git submodules. Git's long-path option is enabled for the clone to reduce Windows filename-length failures.

After the clone step, Pixbit asks for a local ROM file or ZIP archive. If you provide a ZIP, it lists supported ROM files inside and asks which one to use. It then asks for the filename required by the project (for example, baserom.z64) and copies the file into that project's checkout. Press Enter to skip this step.

Pixbit reuses an existing matching clone and tries to initialize any missing submodules. The library uses short, repository-based folder names to leave more room for deep submodule paths.

By default, the library is stored at:

```
%USERPROFILE%\p
```

Choose a different library folder with:

```powershell
py pixbit.py --library "D:\p"
```

### What this prototype currently does

1. Checks for Git and attempts to install it on Windows with winget if it is missing.
2. Loads the Samidy Decomps page and finds direct GitHub repository links.
3. Searches matching link titles for the game title you enter.
4. Lets you choose a match.
5. Clones the project with submodules, or reuses its existing local clone and fetches missing submodules.
6. Accepts a locally supplied ROM file or ZIP archive and copies a selected ROM file into the project folder.

The catalog page may change its HTML or link structure. If no project links are found, Pixbit reports that and stops.

## Project goal

Pixbit aims to bring a Roblox-like library-and-launcher experience to supported decompilation and native-port projects, while games run on computers you control.

The longer-term workflow is:

1. Search for a game by title.
2. Find its community source repository and project-specific build instructions.
3. Check the host computer for the tools that project needs.
4. Install missing tools and show progress and errors.
5. Clone the source into the local game library, or reuse the existing clone.
6. Prepare the game using its documented build process and user-provided game data where required.
7. Add the finished build to the library.
8. Launch it immediately or start it automatically after a 10-second countdown.
9. Connect from Android to play a game running on your host computer.

## Planned work

### Project-specific setup and builds

Requirements differ across projects. Pixbit will need per-project build recipes rather than assuming every project uses the same compiler or CMake command. The eventual setup flow should check required tools, explain missing dependencies, install them where appropriate, and report progress and failures.

### Game data

Some projects require original game data to build or run. Pixbit accepts a local file or ZIP archive, but currently relies on the user to know the filename the selected project requires. Project-specific ROM-name detection, hashes, and clearer validation are future work.

Pixbit does **not** provide or link to downloads of commercial game ROMs. Users are responsible for supplying game data they are legally entitled to use. Pixbit should not redistribute copyrighted game data.

### Android playback

The intended setup runs a game on the host computer and lets an Android phone connect to it over the local network. Streaming, controller support, pairing, and network security still need to be designed and implemented.

## Project boundaries

- Pixbit is a launcher and library prototype, not a tool that creates decompilations from commercial game binaries.
- Each game remains subject to its upstream project's license and build requirements.
- Game source repositories are maintained by their respective authors. Pixbit should link to and respect those projects rather than implying they are official Pixbit releases.
- The host computer stores and runs game builds; Android playback is a separate part of the prototype.

## Contributing

This is an experimental personal project. Issues and pull requests describing supported decompilation or port projects, host compatibility, and Android playback approaches are welcome. Please do not submit copyrighted game data, download links to unauthorized ROM sources, or credentials.

## License

A project license has not been selected yet. Until one is added, do not assume the Pixbit source is licensed for reuse. Each game project linked by Pixbit has its own license.
