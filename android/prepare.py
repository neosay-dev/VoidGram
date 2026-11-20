#!/usr/bin/env python3
"""Turns the pinned Telegram for Android source tree into VoidGram for Android.

Like ci/prepare.py for iOS: refuses any other upstream commit, applies android/patches in order,
copies the resource overlay (android/res → the standalone app module) and brands the build:
application id, name, version, API credentials, no update checks against Telegram's own APKs.

    python3 android/prepare.py <telegram-android checkout>

TELEGRAM_API_ID / TELEGRAM_API_HASH must be set (the same repository secrets the iOS build uses).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "android"
PACKAGE = "one.voidgram.android"
APP_NAME = "VoidGram"

PATCHES = [
    "voidgram-android-features.patch",
]


def replace_once(path, pattern, replacement, flags=0):
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"{path}: pattern not found: {pattern}")
    path.write_text(updated, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--allow-missing-credentials", action="store_true", help="local checks only: keep the upstream API id")
    args = parser.parse_args()
    source = args.source.resolve()

    pin = json.loads((ANDROID / "upstream.json").read_text())
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if actual != pin["commit"]:
        raise SystemExit("Upstream commit differs from android/upstream.json; refusing to apply a mismatched patch")

    for name in PATCHES:
        patch = ANDROID / "patches" / name
        if not patch.exists():
            continue
        subprocess.run(["git", "apply", "--recount", "--check", str(patch)], cwd=source, check=True)
        subprocess.run(["git", "apply", "--recount", str(patch)], cwd=source, check=True)

    # Launcher icon and colours for the standalone APK.
    shutil.copytree(ANDROID / "res", source / "TMessagesProj_AppStandalone/src/main/res", dirs_exist_ok=True)

    # Easter egg (Settings → VoidGram → Other): @natsuk1n_dev's music, shared with iOS.
    raw = source / "TMessagesProj/src/main/res/raw"
    raw.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "assets/easter/NatsukinMusic.mp3", raw / "voidgram_natsukin_music.mp3")

    # Application id, version and name. The standalone build adds ".web" to the id.
    version = (ANDROID / "VERSION").read_text().strip()
    properties = source / "gradle.properties"
    replace_once(properties, r"^APP_PACKAGE=.*$", f"APP_PACKAGE={PACKAGE}", re.M)
    replace_once(properties, r"^APP_VERSION_NAME=(.*)$", lambda m: f"APP_VERSION_NAME={version} ({m.group(1)})", re.M)
    keystore = os.environ.get("ANDROID_KEYSTORE_PASSWORD")
    alias = os.environ.get("ANDROID_KEY_ALIAS")
    if keystore and alias and (source / "TMessagesProj/config/release.keystore").exists():
        replace_once(properties, r"^RELEASE_KEY_PASSWORD=.*$", f"RELEASE_KEY_PASSWORD={keystore}", re.M)
        replace_once(properties, r"^RELEASE_STORE_PASSWORD=.*$", f"RELEASE_STORE_PASSWORD={keystore}", re.M)
        replace_once(properties, r"^RELEASE_KEY_ALIAS=.*$", f"RELEASE_KEY_ALIAS={alias}", re.M)

    for strings in (source / "TMessagesProj/src/main/res").glob("values*/strings.xml"):
        text = strings.read_text(encoding="utf-8")
        text = re.sub(r'(<string name="AppName">)[^<]*(</string>)', rf"\g<1>{APP_NAME}\g<2>", text)
        text = re.sub(r'(<string name="AppNameBeta">)[^<]*(</string>)', rf"\g<1>{APP_NAME} Beta\g<2>", text)
        strings.write_text(text, encoding="utf-8")

    # VoidGram's own API credentials; no update prompts that would install Telegram's APK over it.
    build_vars = source / "TMessagesProj/src/main/java/org/telegram/messenger/BuildVars.java"
    api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    if api_id and api_hash:
        if not api_id.isdigit() or not re.fullmatch(r"[0-9a-f]{32}", api_hash):
            raise SystemExit("TELEGRAM_API_ID must be a number and TELEGRAM_API_HASH 32 hex digits")
        replace_once(build_vars, r"public static int APP_ID = \d+;", f"public static int APP_ID = {api_id};")
        replace_once(build_vars, r'public static String APP_HASH = "[0-9a-f]+";', f'public static String APP_HASH = "{api_hash}";')
    elif not args.allow_missing_credentials:
        raise SystemExit("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")
    replace_once(build_vars, r"public static boolean CHECK_UPDATES = true;", "public static boolean CHECK_UPDATES = false;")
    replace_once(build_vars, r'public static String PLAYSTORE_APP_URL = "[^"]*";', 'public static String PLAYSTORE_APP_URL = "https://github.com/neosay-dev/VoidGram/releases/latest";')

    # Google services needs a client entry for every application id; push notifications go through
    # Telegram's Firebase project and do not reach a different id, so they stay off in VoidGram.
    for module in ("TMessagesProj_AppStandalone", "TMessagesProj_App", "TMessagesProj_AppHuawei", "TMessagesProj"):
        services = source / module / "google-services.json"
        if not services.exists():
            continue
        data = json.loads(services.read_text())
        clients = data["client"]
        added = []
        for client in clients:
            name = client["client_info"]["android_client_info"]["package_name"]
            if name.startswith("org.telegram.messenger"):
                copy = json.loads(json.dumps(client))
                copy["client_info"]["android_client_info"]["package_name"] = PACKAGE + name[len("org.telegram.messenger"):]
                added.append(copy)
        clients.extend(added)
        services.write_text(json.dumps(data, indent=2) + "\n")

    # The contacts sync account type must not collide with an installed Telegram.
    for relative in ("TMessagesProj/src/main/res/xml/auth.xml", "TMessagesProj/src/main/res/xml/sync_contacts.xml", "TMessagesProj/src/main/java/org/telegram/messenger/ContactsController.java"):
        path = source / relative
        text = path.read_text(encoding="utf-8")
        if 'accountType="org.telegram.messenger"' not in text and '"org.telegram.messenger")' not in text and 'ByType("org.telegram.messenger")' not in text:
            raise SystemExit(f"{relative}: account type not found")
        text = text.replace('accountType="org.telegram.messenger"', f'accountType="{PACKAGE}"')
        text = text.replace('getAccountsByType("org.telegram.messenger")', f'getAccountsByType("{PACKAGE}")')
        text = text.replace('getClientUserId(), "org.telegram.messenger")', f'getClientUserId(), "{PACKAGE}")')
        path.write_text(text, encoding="utf-8")

    # Two ABIs (every phone from the last decade) halve the native build time.
    standalone = source / "TMessagesProj_AppStandalone/build.gradle"
    replace_once(standalone, r'abiFilters "armeabi-v7a", "arm64-v8a", "x86", "x86_64"', 'abiFilters "armeabi-v7a", "arm64-v8a"')

    print(f"Applied VoidGram for Android {version} to {actual}")


if __name__ == "__main__":
    main()
