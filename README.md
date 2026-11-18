# Create Economy pack

This repository is where the **Create Economy Launcher** gets the modpack from.
Every time a player opens the launcher it reads `pack.json` here, downloads anything new
(every file is SHA-1 checked) and starts the game. Push a change here and everyone has it
on their next start: no launcher update needed.

The repository must be **public** so launchers can read it without a password.

## Releasing a pack update

1. Update the CurseForge instance you play with (add/remove/update mods, change configs).
2. Build the pack from that instance:

   ```bash
   python tools/build_pack.py "C:/Users/<you>/curseforge/minecraft/Instances/Create Economy 3.0.2 (1)" --version 3.0.3 --notes "Added Create: Steam 'n' Rails 0.3" --add-mod "../ce-launcher/build/libs/Create-Economy-Launcher-1.1.0.jar" --curseforge-zip
   ```

3. Commit and push:

   ```bash
   git add -A && git commit -m "Pack 3.0.3" && git push
   ```

That's it. Launchers pick it up on their next start, and the in-game menu shows
"Pack update 3.0.3 is out" to anyone still on the old version.

## What the builder does

- **Mods** are not stored here. `pack.json` lists each jar with its SHA-1 and where to get it:
  Modrinth first when Modrinth has the exact same file, otherwise CurseForge's CDN.
  Jars that exist nowhere public (your patched `taczaddon` jar, the Create Economy Launcher mod)
  are kept in `mods-extra/`.
- **Config, kubejs, shaders** are copied into `overrides/`. On a player's PC a config file is
  only replaced when *you* changed it, so their own tweaks survive until the server changes that file.
- `options.txt` and `servers.dat` are only written on a player's first install.
- `config/celauncher-pack.txt` holds the version number; the in-game menu compares it with this repo.
- `--curseforge-zip` also writes `dist/Create-Economy-<version>.zip` in CurseForge modpack format.
  In that zip **every mod comes from CurseForge**: no jars are packed inside. A jar that isn't a
  CurseForge file (your patched taczaddon, or the launcher mod before it has its own CurseForge
  page) is left out and named in the output. `dist/` is not committed.
- The CurseForge version never reads this repository for mods. Its in-game "pack update" notice
  compares the installed CurseForge file with the newest file of your CurseForge modpack.

## Android

Minecraft: Java Edition with mods runs on Android only through PojavLauncher-based launchers
(they ship a Java runtime and an OpenGL translation layer). Those launchers can import a
CurseForge modpack zip, so Android players:

1. Install a PojavLauncher-based launcher that supports NeoForge and CurseForge modpack import.
2. Sign in with the Microsoft account that owns Minecraft: Java Edition.
3. Import `Create-Economy-<version>.zip` (or install "Create Economy" from CurseForge inside the launcher).
4. Give it as much memory as the phone allows (4 GB or more). A 200+ mod Create pack needs a
   recent, high-end phone; expect lower frame rates than on a PC.

The Create Economy menu, loading screen and "Play on Create Economy" button come from the
Create Economy Launcher mod inside the pack, so they look the same on Android.
Not tested on a real Android device yet.
