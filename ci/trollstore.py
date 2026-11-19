"""Makes a TrollStore package (.tipa) from the unsigned IPA.

TrollStore keeps the entitlements a binary is signed with. The unsigned build carries none, so the
app and its extensions lost their shared app group (the extensions' data, notifications) and the
keychain group. Here every executable is signed with ldid: the app and each extension with the
entitlements Bazel generated for it (read back from the build's own signature when there is one),
plus the app group, keychain group and team id TrollStore needs; frameworks without entitlements.

    python3 ci/trollstore.py <unsigned.ipa> <out.tipa> <bundle id> <team id>
"""
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def embedded_entitlements(binary):
    result = subprocess.run(["codesign", "-d", "--entitlements", ":-", str(binary)], capture_output=True)
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        return plistlib.loads(result.stdout)
    except Exception:
        return {}


def entitlements_for(bundle, app_bundle_id, team_id):
    info = plistlib.loads((bundle / "Info.plist").read_bytes())
    bundle_id = info["CFBundleIdentifier"]
    binary = bundle / info["CFBundleExecutable"]
    entitlements = embedded_entitlements(binary)
    entitlements.update({
        "application-identifier": f"{team_id}.{bundle_id}",
        "com.apple.developer.team-identifier": team_id,
        "com.apple.security.application-groups": [f"group.{app_bundle_id}"],
        "keychain-access-groups": [f"{team_id}.*"],
    })
    if bundle.suffix == ".app":
        entitlements["get-task-allow"] = True
    return binary, entitlements


def sign(binary, entitlements=None):
    command = ["ldid"]
    if entitlements is not None:
        with tempfile.NamedTemporaryFile(suffix=".plist", delete=False) as file:
            file.write(plistlib.dumps(entitlements))
        command.append("-S" + file.name)
    else:
        command.append("-S")
    subprocess.run(command + [str(binary)], check=True)


def main(ipa, output, app_bundle_id, team_id):
    with tempfile.TemporaryDirectory(prefix="voidgram-tipa-") as folder:
        root = Path(folder)
        with zipfile.ZipFile(ipa) as archive:
            archive.extractall(root)
        app = next((root / "Payload").glob("*.app"))
        for framework in sorted(app.rglob("*.framework")):
            info = framework / "Info.plist"
            name = plistlib.loads(info.read_bytes())["CFBundleExecutable"] if info.exists() else framework.stem
            if (framework / name).exists():
                sign(framework / name)
        for dylib in sorted(app.rglob("*.dylib")):
            sign(dylib)
        bundles = sorted(app.glob("PlugIns/*.appex")) + sorted(app.glob("Extensions/*.appex")) + [app]
        for bundle in bundles:
            binary, entitlements = entitlements_for(bundle, app_bundle_id, team_id)
            assert entitlements["com.apple.security.application-groups"] == [f"group.{app_bundle_id}"]
            sign(binary, entitlements)
            print(f"signed {bundle.name}: {len(entitlements)} entitlements")
        output = Path(output)
        output.unlink(missing_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((root / "Payload").rglob("*")):
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    item = zipfile.ZipInfo(relative)
                    item.create_system = 3
                    item.external_attr = 0o120777 << 16
                    archive.writestr(item, str(path.readlink()))
                elif path.is_file():
                    archive.write(path, relative)
        print(f"TrollStore package: {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 5 or shutil.which("ldid") is None:
        raise SystemExit(__doc__ if len(sys.argv) != 5 else "ldid is not installed (brew install ldid)")
    main(*sys.argv[1:])
