#!/usr/bin/env python3
"""Build the Create Economy pack repository from a CurseForge instance.

    python tools/build_pack.py "<path to CurseForge instance>" --version 3.0.3 [--notes "..."]

What it writes (all inside this repository):
  pack.json            the manifest the Create Economy Launcher reads
  overrides/...        config/, kubejs/, shaderpacks/, defaultconfigs/ copied from the instance
  mods-extra/...       any mod jar that has no public download (not on CurseForge or Modrinth)

Every mod is downloaded by the launcher from Modrinth when Modrinth has the exact
same file (matched by SHA-1), otherwise from CurseForge's CDN. Each file is SHA-1
checked after download, so a wrong or tampered file is never used.
Commit + push the result and every launcher picks it up on its next start.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import os
import shutil
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDE_DIRS = ["config", "kubejs", "defaultconfigs", "shaderpacks", "resourcepacks"]
# Files the player owns after the first install (keybinds, video settings, server list).
SEED_ONCE = ["options.txt"]  # servers.dat left out: the in-game menu adds play.create-economy.net itself
SKIP_SUFFIXES = (".bak", ".log", ".tmp", ".lock")
SKIP_PARTS = {"__pycache__", ".git", "crash_assistant"}
UA = {"User-Agent": "create-economy-pack-tool/1.0", "Content-Type": "application/json"}


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def modrinth_lookup(hashes):
    """sha1 -> modrinth file url (exact file only)."""
    out = {}
    hashes = list(hashes)
    for i in range(0, len(hashes), 200):
        body = json.dumps({"hashes": hashes[i:i + 200], "algorithm": "sha1"}).encode()
        req = urllib.request.Request("https://api.modrinth.com/v2/version_files", data=body, headers=UA)
        try:
            res = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:  # Modrinth down: CurseForge links still work.
            print("  modrinth lookup failed:", e)
            return out
        for h, ver in res.items():
            for f in ver.get("files", []):
                if f.get("hashes", {}).get("sha1") == h:
                    out[h] = f["url"]
    return out


def write_cf_zip(pack):
    """CurseForge modpack zip. Every mod comes from CurseForge (manifest.json); no jars are packed inside.
    Jars that aren't CurseForge files are left out and listed, so they can be uploaded/added on CurseForge first."""
    import zipfile
    dist = os.path.join(REPO, "dist")
    os.makedirs(dist, exist_ok=True)
    out = os.path.join(dist, f"Create-Economy-{pack['version']}.zip")
    cf_files, extra = [], []
    for f in pack["files"]:
        if f.get("mode"):
            continue
        if f.get("curseforge"):
            cf_files.append({"projectID": f["curseforge"]["project"], "fileID": f["curseforge"]["file"], "required": True})
        else:
            extra.append(f)
    manifest = {
        "minecraft": {"version": pack["minecraft"],
                      "modLoaders": [{"id": f"{pack['loader']['type']}-{pack['loader']['version']}", "primary": True}],
                      "recommendedRam": pack["memory"]["recommendedMB"]},
        "manifestType": "minecraftModpack", "manifestVersion": 1,
        "name": pack["name"], "version": pack["version"], "author": "mr_vew",
        "files": cf_files, "overrides": "overrides",
    }
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=1))
        z.writestr("modlist.html", "<ul>" + "".join(f"<li>{x['title']}</li>" for x in pack["files"] if not x.get("mode")) + "</ul>")
        for f in pack["files"]:
            if f.get("mode"):
                z.write(os.path.join(REPO, f["repo"]), "overrides/" + f["path"])
    print(f"  CurseForge zip: {out} ({len(cf_files)} mods, all from CurseForge)")
    if extra:
        print("  NOT in the CurseForge zip (not CurseForge files - add them to the pack in the CurseForge app first): "
              + ", ".join(os.path.basename(x["path"]) for x in extra))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--version", required=True, help="pack version shown in the launcher, e.g. 3.0.3")
    ap.add_argument("--notes", default="", help="one-line change note shown in the launcher")
    ap.add_argument("--no-modrinth", action="store_true")
    ap.add_argument("--skip", action="append", default=[],
                    help="leave a jar out (file name prefix), e.g. a mod you aren't allowed to redistribute")
    ap.add_argument("--curseforge-zip", action="store_true",
                    help="also write dist/Create-Economy-<version>.zip (CurseForge modpack format: CurseForge upload, Android launchers, Prism)")
    ap.add_argument("--add-mod", action="append", default=[],
                    help="extra jar (your own mod) to ship from this repo, e.g. the Create Economy Launcher mod")
    a = ap.parse_args()

    inst = os.path.abspath(a.instance)
    meta = json.load(open(os.path.join(inst, "minecraftinstance.json"), encoding="utf-8"))
    loader = meta["baseModLoader"]["name"]  # neoforge-21.1.251
    ltype, lver = loader.split("-", 1)

    mods_dir = os.path.join(inst, "mods")
    on_disk = {f for f in os.listdir(mods_dir) if f.endswith(".jar")}
    files = []
    addons = {}
    for ad in meta.get("installedAddons", []):
        f = ad["installedFile"]
        name = f.get("fileNameOnDisk") or f["fileName"]
        if name not in on_disk:
            continue
        s1 = next((h["value"] for h in f.get("hashes", []) if h["type"] == 1), None)
        real = sha1(os.path.join(mods_dir, name))
        if s1 != real:
            print("  hash differs from CurseForge record, re-hashed:", name)
        addons[name] = {"sha1": real, "size": os.path.getsize(os.path.join(mods_dir, name)),
                        "cf": f.get("downloadUrl") if s1 == real else None,
                        "title": ad.get("name"), "projectId": ad.get("addonID"), "fileId": f.get("id")}

    mr = {} if a.no_modrinth else modrinth_lookup(v["sha1"] for v in addons.values())

    extra_dir = os.path.join(REPO, "mods-extra")
    shutil.rmtree(extra_dir, ignore_errors=True)
    for name in sorted(on_disk, key=str.lower):
        if any(name.lower().startswith(x.lower()) for x in a.skip):
            print("  skipped (--skip):", name)
            continue
        path = os.path.join(mods_dir, name)
        info = addons.get(name) or {"sha1": sha1(path), "size": os.path.getsize(path), "cf": None, "title": name}
        urls = []
        if info["sha1"] in mr:
            urls.append(mr[info["sha1"]])
        if info.get("cf"):
            urls.append(info["cf"])
        entry = {"path": "mods/" + name, "sha1": info["sha1"], "size": info["size"], "title": info.get("title") or name}
        if info.get("projectId"):
            entry["curseforge"] = {"project": info["projectId"], "file": info["fileId"]}
        if not urls:
            os.makedirs(extra_dir, exist_ok=True)
            shutil.copy2(path, os.path.join(extra_dir, name))
            entry["repo"] = "mods-extra/" + name
            print("  no public download, stored in repo:", name)
        entry["urls"] = urls
        files.append(entry)

    for extra in a.add_mod:
        name = os.path.basename(extra)
        os.makedirs(extra_dir, exist_ok=True)
        shutil.copy2(extra, os.path.join(extra_dir, name))
        files = [x for x in files if x["path"] != "mods/" + name]
        files.append({"path": "mods/" + name, "sha1": sha1(extra), "size": os.path.getsize(extra),
                      "title": name, "repo": "mods-extra/" + name, "urls": []})
        print("  added from repo:", name)

    # Overrides (config, scripts, shaders). Replaced fully on every build.
    ov_root = os.path.join(REPO, "overrides")
    shutil.rmtree(ov_root, ignore_errors=True)
    overrides = []
    for d in OVERRIDE_DIRS + SEED_ONCE:
        src = os.path.join(inst, d)
        if os.path.isfile(src):
            items = [(src, d)]
        elif os.path.isdir(src):
            items = []
            for root, dirs, fns in os.walk(src):
                dirs[:] = [x for x in dirs if x not in SKIP_PARTS]
                for fn in fns:
                    if fn.endswith(SKIP_SUFFIXES):
                        continue
                    full = os.path.join(root, fn)
                    items.append((full, os.path.relpath(full, inst).replace(os.sep, "/")))
        else:
            continue
        for full, rel in items:
            dst = os.path.join(ov_root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(full, dst)
            if rel == "config/fml.toml":
                # Use the Create Economy loading window (provided by the Create Economy Launcher mod).
                raw = open(dst, "rb").read()
                raw = re.sub(rb'(?m)^(\s*earlyWindowProvider\s*=\s*)"fmlearlywindow"', lambda m: m.group(1) + b'"createeconomy"', raw)
                open(dst, "wb").write(raw)
            overrides.append({"path": rel, "sha1": sha1(dst), "size": os.path.getsize(dst),
                              "repo": "overrides/" + rel, "mode": "once" if rel in SEED_ONCE else "managed"})

    # The in-game menu compares this with pack.json on GitHub to show "pack update available".
    ver_rel = "config/celauncher-pack.txt"
    ver_file = os.path.join(ov_root, ver_rel)
    os.makedirs(os.path.dirname(ver_file), exist_ok=True)
    with open(ver_file, "w", encoding="utf-8", newline=chr(10)) as f:
        f.write(a.version + chr(10))
    overrides = [o for o in overrides if o["path"] != ver_rel]
    overrides.append({"path": ver_rel, "sha1": sha1(ver_file), "size": os.path.getsize(ver_file),
                      "repo": "overrides/" + ver_rel, "mode": "managed"})

    prev = {}
    pj = os.path.join(REPO, "pack.json")
    if os.path.exists(pj):
        prev = json.load(open(pj, encoding="utf-8"))

    pack = {
        "format": 1,
        "name": "Create Economy",
        "version": a.version,
        "released": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": a.notes,
        "minecraft": meta["gameVersion"],
        "loader": {"type": ltype, "version": lver},
        "java": 21,
        "memory": {"minimumMB": 4096, "recommendedMB": max(6144, int(meta.get("allocatedMemory") or 0))},
        "server": {"name": "Create Economy", "address": "play.create-economy.net", "port": 25565},
        "website": "https://create-economy.net",
        "files": files + overrides,
        "history": ([{"version": prev["version"], "released": prev.get("released"), "notes": prev.get("notes", "")}]
                    + prev.get("history", []))[:20] if prev.get("version") and prev.get("version") != a.version
        else prev.get("history", []),
    }
    with open(pj, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pack, f, indent=1)
        f.write("\n")
    if a.curseforge_zip:
        write_cf_zip(pack)
    mods_from_mr = sum(1 for x in files if x["urls"] and "modrinth" in x["urls"][0])
    print(f"pack.json: {pack['name']} {a.version}, {ltype} {lver}, {len(files)} mods "
          f"({mods_from_mr} Modrinth first, {sum(1 for x in files if 'repo' in x)} stored here), "
          f"{len(overrides)} override files")


if __name__ == "__main__":
    sys.exit(main())
