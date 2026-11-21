"""Builds the VoidGram night theme (Telegram iOS's night palette) from tdesktop's night theme.

    python3 desktop/tools/voidgram_theme.py <tdesktop>/Telegram/Resources/night.tdesktop-theme <out.tdesktop-theme>

Every blue-tinted dark grey of the night theme becomes a neutral grey of about half its lightness, every blue
becomes iOS's blue at the same lightness, and the colours the screens are built from are set to the iOS night
theme's own values (DefaultDarkPresentationTheme): black lists, #1c1c1d groups, #8d8e93 secondary text,
#1D1D1D incoming bubbles, white unread badges.
"""
import colorsys
import io
import re
import sys
import zipfile

from PIL import Image

EXACT = {
    "windowBg": "#000000", "windowBgOver": "#1c1c1d", "windowBgRipple": "#2c2c2e", "windowFg": "#ffffff",
    "windowSubTextFg": "#8d8e93", "windowBgActive": "#0a84ff", "windowFgActive": "#ffffff",
    "activeButtonBg": "#0a84ff", "activeButtonBgOver": "#2a94ff", "activeLineFg": "#0a84ff",
    "filterInputInactiveBg": "#1c1c1d", "filterInputActiveBg": "#1c1c1d",
    "dialogsBg": "#000000", "dialogsBgOver": "#141414", "dialogsBgActive": "#1c1c1d",
    "dialogsNameFg": "#ffffff", "dialogsNameFgActive": "#ffffff", "dialogsNameFgOver": "#ffffff",
    "dialogsTextFg": "#8d8e93", "dialogsTextFgActive": "#8d8e93", "dialogsTextFgOver": "#8d8e93",
    "dialogsDateFg": "#8d8e93", "dialogsDateFgActive": "#8d8e93", "dialogsDateFgOver": "#8d8e93",
    "dialogsUnreadBg": "#ffffff", "dialogsUnreadFg": "#000000", "dialogsUnreadBgMuted": "#666666",
    "dialogsUnreadBgActive": "#ffffff", "dialogsUnreadFgActive": "#000000",
    "topBarBg": "#000000", "historyComposeAreaBg": "#00000000",  # see-through: the composer floats over the messages
    "sideBarBg": "#000000",
    "msgInBg": "#1d1d1d", "msgInBgSelected": "#2c2c2e", "msgOutBg": "#0a7cff", "msgOutBgSelected": "#0a6ad6",
    "msgOutTextFg": "#ffffff", "msgInTextFg": "#ffffff", "msgServiceBg": "#1c1c1dd8",
}


def remap(value):
    hexpart = value[1:]
    r, g, b = (int(hexpart[i:i + 2], 16) / 255 for i in (0, 2, 4))
    alpha = hexpart[6:8]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    hue = h * 360
    if 190 <= hue <= 225 and s > 0.45 and l > 0.35:  # the night theme's blues: iOS blue, same lightness
        h2, l2, s2 = colorsys.rgb_to_hls(10 / 255, 132 / 255, 1.0)
        r, g, b = colorsys.hls_to_rgb(h2, l, min(1.0, s2))
    elif s < 0.5 and l < 0.4:  # blue-tinted dark greys: neutral, darker
        r = g = b = l * 0.55
    elif s < 0.35:  # mid greys (secondary text): neutral
        r = g = b = l
    return "#%02x%02x%02x%s" % (round(r * 255), round(g * 255), round(b * 255), alpha)


def main(source, out):
    with zipfile.ZipFile(source) as archive:
        colors = archive.read("colors.tdesktop-theme").decode()
    lines = []
    for line in colors.split("\n"):
        m = re.match(r"^(\w+):\s*(#[0-9a-fA-F]{6,8})(.*)$", line)
        if m:
            name, value, rest = m.groups()
            value = EXACT.get(name, remap(value.lower()))
            line = f"{name}: {value}{rest}"
        lines.append(line)
    text = "\n".join(lines)
    missing = [k for k in EXACT if not re.search(rf"^{k}:", text, re.M)]
    for k in missing:
        text += f"\n{k}: {EXACT[k]};"
    background = io.BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 0)).save(background, "PNG")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("colors.tdesktop-theme", text)
        archive.writestr("background.png", background.getvalue())
    print(f"{out}: {sum(1 for l in lines if re.match(r'^\\w+:', l))} colours, {len(missing)} added")


if __name__ == "__main__":
    main(*sys.argv[1:])
