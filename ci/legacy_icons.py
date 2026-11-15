"""Adds PNG copies of the VoidGram launcher icons to the unsigned IPA, for iOS older than 26.

The icons are Icon Composer bundles (`Ayu*.icon`), which iOS 26 draws. An older iOS finds no
image for them and `setAlternateIconName` fails. Here every icon gets loose PNG files in the
app folder and a `<Name>Legacy` entry in CFBundleAlternateIcons; the app asks for that name
when the Icon Composer one is refused (AyuSettingsController, ayuPresentAppIcons).
"""
import plistlib
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from ipa_archive import COMPRESSION_LEVEL, copy_entry

# (file suffix, pixels): iPhone 60 pt at 2x and 3x; iPad 76 pt at 1x and 2x, 83.5 pt at 2x.
PHONE = (("@2x", 120), ("@3x", 180))
PAD = (("Ipad", 76), ("Ipad@2x", 152), ("LargeIpad@2x", 167))


def artwork(source, branding):
    """One full-bleed image per icon: the bundle's single layer, or the glass icons' preview."""
    found = {}
    for bundle in sorted((source / "Telegram/Telegram-iOS").glob("Ayu*.icon")):
        layers = sorted((bundle / "Assets").glob("*.png"))
        preview = branding / (bundle.stem.removeprefix("Ayu") + "-Preview.png")
        if len(layers) == 1:
            found[bundle.stem] = layers[0]
        elif preview.is_file():
            found[bundle.stem] = preview
    return found


def resized(image, pixels, folder):
    output = Path(folder) / f"{image.stem}-{pixels}.png"
    if sys.platform == "darwin":
        subprocess.run(["sips", "-s", "format", "png", "-z", str(pixels), str(pixels), str(image), "--out", str(output)],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        from PIL import Image
        Image.open(image).convert("RGB").resize((pixels, pixels), Image.LANCZOS).save(output)
    return output.read_bytes()


def package(ipa, source, branding):
    ipa = Path(ipa)
    icons = artwork(Path(source), Path(branding))
    with zipfile.ZipFile(ipa) as archive:
        prefix = next(name[:-len("Info.plist")] for name in archive.namelist()
                      if name.startswith("Payload/") and name.count("/") == 2 and name.endswith(".app/Info.plist"))
        info = plistlib.loads(archive.read(prefix + "Info.plist"))
    declared = info.get("CFBundleIcons", {}).get("CFBundleAlternateIcons", {})
    files = {}
    added = []
    with tempfile.TemporaryDirectory(prefix="voidgram-icons-") as folder:
        for name, image in icons.items():
            if name not in declared:
                continue
            base = name + "L"
            for suffix, pixels in PHONE:
                files[f"{base}{suffix}.png"] = resized(image, pixels, folder)
            for suffix, pixels in PAD:
                files[f"{base}{suffix}.png"] = resized(image, pixels, folder)
            phone = info.setdefault("CFBundleIcons", {}).setdefault("CFBundleAlternateIcons", {})
            phone[name + "Legacy"] = {"CFBundleIconFiles": [base], "UIPrerenderedIcon": True}
            pad = info.setdefault("CFBundleIcons~ipad", {}).setdefault("CFBundleAlternateIcons", {})
            pad[name + "Legacy"] = {"CFBundleIconFiles": [base + "Ipad", base + "LargeIpad"], "UIPrerenderedIcon": True}
            added.append(name)
    if not added:
        return []
    files["Info.plist"] = plistlib.dumps(info, fmt=plistlib.FMT_BINARY)
    destination = ipa.with_suffix(".icons.ipa")
    with zipfile.ZipFile(ipa) as old, zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                                                      compresslevel=COMPRESSION_LEVEL) as output:
        output.comment = old.comment
        for item in old.infolist():
            relative = item.filename[len(prefix):] if item.filename.startswith(prefix) else ""
            if relative in files:
                continue
            copy_entry(old, output, item)
        for name, contents in sorted(files.items()):
            item = zipfile.ZipInfo(prefix + name)
            item.create_system = 3
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = (stat.S_IFREG | 0o644) << 16
            output.writestr(item, contents, compresslevel=COMPRESSION_LEVEL)
    with zipfile.ZipFile(destination) as result:
        if result.testzip() is not None:
            raise ValueError("Repacked IPA with legacy icons failed ZIP integrity validation")
    destination.replace(ipa)
    return added
