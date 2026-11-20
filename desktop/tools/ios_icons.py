"""Redraws desktop icons with Telegram iOS's glyphs (Images.xcassets PDFs), at the desktop's own sizes.

    python3 desktop/tools/ios_icons.py <telegram-ios checkout> <tdesktop checkout> [--sheet out.png]

Each desktop icon is a PNG mask (1x, @2x, @3x) the style system tints; the iOS glyph (PDF, or @3x PNG)
is fitted into the area the old icon drew, so its size and position on screen stay. Icons the desktop keeps as SVG are left alone.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

MAP = {
    # desktop icon (Resources/icons/...)  ->  iOS imageset (Images.xcassets/...)
    "menu/add": "Chat/Context Menu/Add", "menu/add_account": "Chat/Context Menu/AddUser",
    "menu/add_to_folder": "Chat/Context Menu/AddToFolder", "menu/antispam": "Chat/Context Menu/AntiSpam",
    "menu/archive": "Chat/Context Menu/Archive", "menu/unarchive": "Chat/Context Menu/Unarchive",
    "menu/block": "Chat/Context Menu/Ban", "menu/boosts": "Chat/Context Menu/Boost", "menu/bot": "Chat/Context Menu/Bots",
    "menu/calendar": "Chat/Context Menu/Calendar", "menu/channel": "Chat/Context Menu/Channels",
    "menu/chat_bubble": "Chat/Context Menu/MessageBubble", "menu/chats": "Chat/Context Menu/Chats",
    "menu/clear": "Chat/Context Menu/Clear", "menu/collapse": "Chat/Context Menu/Collapse", "menu/expand": "Chat/Context Menu/Expand",
    "menu/copy": "Chat/Context Menu/Copy", "menu/customize": "Chat/Context Menu/Customize", "menu/delete": "Chat/Context Menu/Delete",
    "menu/download": "Chat/Context Menu/Download", "menu/download_locked": "Chat/Context Menu/DownloadLocked",
    "menu/edit": "Chat/Context Menu/Edit", "menu/factcheck": "Chat/Context Menu/FactCheck",
    "menu/favorite": "Chat/Context Menu/Fave", "menu/unfavorite": "Chat/Context Menu/Unfave",
    "menu/file": "Chat/Context Menu/File", "menu/forward": "Chat/Context Menu/Forward", "menu/groups": "Chat/Context Menu/Groups",
    "menu/image": "Chat/Context Menu/Image", "menu/info": "Chat/Context Menu/Info", "menu/link": "Chat/Context Menu/Link",
    "menu/lock": "Chat/Context Menu/Lock", "menu/mute": "Chat/Context Menu/Muted", "menu/unmute": "Chat/Context Menu/Unmute",
    "menu/night_mode": "Chat/Context Menu/NightMode", "menu/palette": "Chat/Context Menu/Palette",
    "menu/pin": "Chat/Context Menu/Pin", "menu/unpin": "Chat/Context Menu/Unpin", "menu/profile": "Chat/Context Menu/User",
    "menu/quality_hd": "Chat/Context Menu/QualityHd", "menu/read": "Chat/Context Menu/Read", "menu/unread": "Chat/Context Menu/MarkAsUnread",
    "menu/remove": "Chat/Context Menu/Remove", "menu/reply": "Chat/Context Menu/Reply", "menu/report": "Chat/Context Menu/Report",
    "menu/copyright": "Chat/Context Menu/ReportCopyright", "menu/drugs": "Chat/Context Menu/ReportDrugs",
    "menu/fake": "Chat/Context Menu/ReportFake", "menu/personal": "Chat/Context Menu/ReportPersonal",
    "menu/porn": "Chat/Context Menu/ReportXxx", "menu/violence": "Chat/Context Menu/ReportViolence",
    "menu/search": "Chat/Context Menu/Search", "menu/select": "Chat/Context Menu/Select", "menu/settings": "Chat/Context Menu/Settings",
    "menu/share": "Chat/Context Menu/Share", "menu/stats": "Chat/Context Menu/Statistics",
    "menu/stories_archive": "Chat/Context Menu/StoryArchive", "menu/timer": "Chat/Context Menu/Timer",
    "menu/translate": "Chat/Context Menu/Translate", "menu/zoom_in": "Chat/Context Menu/ZoomIn", "menu/zoom_out": "Chat/Context Menu/ZoomOut",
    "menu/tag_filter": "Chat/Context Menu/TagFilter", "menu/tag_remove": "Chat/Context Menu/TagRemove",
    "menu/tag_rename": "Chat/Context Menu/TagEditName", "menu/phone": "Chat/Context Menu/PhoneCall",
    "menu/video_chat": "Chat/Context Menu/VoiceChat", "menu/gift_premium": "Chat/Context Menu/Gift",
    "menu/emoji": "Chat/Context Menu/Smile", "menu/stickers": "Chat/Context Menu/Sticker",
    "menu/show_in_chat": "Chat/Context Menu/GoToMessage", "menu/view_replies": "Chat/Context Menu/Replies",
    "menu/reschedule": "Chat/Context Menu/Schedule", "menu/leave": "Chat/Context Menu/Logout",
    "menu/admin_promote": "Chat/Context Menu/Promote", "menu/send": "Chat/Context Menu/Resend",
    "chat/input_attach": "Chat/Input/Text/IconAttachment", "chat/input_record": "Chat/Input/Text/IconMicrophone",
    "chat/input_video": "Chat/Input/Text/IconVideo", "chat/input_smile_face": "Chat/Context Menu/Smile",
    "settings/lock": "Chat/Context Menu/Lock", "settings/folders": "Chat/Context Menu/Folder",
    "settings/language": "Chat/Context Menu/Globe", "settings/faq": "Chat/Context Menu/Help",
    "settings/stickers": "Chat/Context Menu/Sticker", "settings/calls": "Chat/Context Menu/PhoneCall",
    "settings/archive": "Chat/Context Menu/Archive", "settings/user": "Chat/Context Menu/User",
    "settings/channel": "Chat/Context Menu/Channels", "settings/group": "Chat/Context Menu/Groups",
    "settings/palette": "Chat/Context Menu/Palette", "settings/night": "Chat/Context Menu/NightMode",
    "settings/timer": "Chat/Context Menu/Timer", "settings/reload": "Chat/Context Menu/Reload",
    "settings/gift": "Chat/Context Menu/Gift", "settings/photo": "Chat/Context Menu/Camera",
    "settings/download": "Chat/Context Menu/Download", "settings/mention": "Chat/Context Menu/Mention",
    "settings/pin": "Chat/Context Menu/Pin", "settings/emoji": "Chat/Context Menu/Smile",
    "settings/forward": "Chat/Context Menu/Forward",
}


def glyph(source):
    """The iOS glyph as a white alpha mask, trimmed to its drawn pixels, from a PDF (large) or an @3x PNG."""
    if source.suffix == ".pdf":
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder) / "icon"
            subprocess.run(["pdftocairo", "-png", "-singlefile", "-transp", "-scale-to", "480", str(source), str(base)], check=True)
            image = Image.open(f"{base}.png").convert("RGBA")
    else:
        image = Image.open(source).convert("RGBA")
    alpha = image.getchannel("A")
    box = alpha.getbbox()
    assert box, f"{source} is empty"
    return alpha.crop(box)


def render(alpha, original, out):
    """Fits the glyph into the drawn area of the desktop icon it replaces, so size and position stay.

    Desktop icons are greyscale masks with no alpha (a white shape on black, saved as RGB): the style
    code generator converts them to RGB32 and reads the brightness, so a transparent PNG becomes a square.
    """
    old = Image.open(original).convert("L")
    box = old.getbbox() or (0, 0, old.width, old.height)
    bw, bh = box[2] - box[0], box[3] - box[1]
    scale = min(bw / alpha.width, bh / alpha.height)
    size = (max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale)))
    fitted = alpha.resize(size, Image.LANCZOS)
    mask = Image.new("L", old.size, 0)
    mask.paste(fitted, (box[0] + (bw - size[0]) // 2, box[1] + (bh - size[1]) // 2))
    mask.convert("RGB").save(out)


def main(ios_root, desk_root, sheet=None):
    assets = Path(ios_root) / "submodules/TelegramUI/Images.xcassets"
    icons = Path(desk_root) / "Telegram/Resources/icons"
    done, skipped = [], []
    for desk, ios in MAP.items():
        imageset = assets / f"{ios}.imageset"
        sources = sorted(imageset.glob("*.pdf")) or sorted(imageset.glob("*@3x.png"))
        variants = [icons / f"{desk}{suffix}.png" for suffix in ("", "@2x", "@3x")]
        if not sources or not all(v.exists() for v in variants) or (icons / f"{desk}.svg").exists():
            skipped.append(desk)
            continue
        alpha = glyph(sources[0])
        for variant in variants:
            render(alpha, variant, variant)
        done.append(desk)
    print(f"redrawn {len(done)}, skipped {len(skipped)}: {' '.join(skipped)}")
    if sheet:
        tiles = [Image.open(icons / f"{d}@2x.png").convert("L") for d in done]
        cols = 12
        cell = 64
        out = Image.new("RGBA", (cols * cell, ((len(tiles) + cols - 1) // cols) * cell), (24, 24, 26, 255))
        for i, tile in enumerate(tiles):
            white = Image.new("RGBA", tile.size, (255, 255, 255, 255))
            white.putalpha(tile)
            out.alpha_composite(white, ((i % cols) * cell + (cell - tile.width) // 2, (i // cols) * cell + (cell - tile.height) // 2))
        out.save(sheet)


if __name__ == "__main__":
    args = sys.argv[1:]
    sheet = args[args.index("--sheet") + 1] if "--sheet" in args else None
    main(args[0], args[1], sheet)
