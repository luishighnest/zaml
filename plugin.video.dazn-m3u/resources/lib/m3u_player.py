import sys, os, re, urllib.request, urllib.parse, json
import xbmc, xbmcgui, xbmcplugin, xbmcaddon

ADDON = xbmcaddon.Addon()
M3U = r"C:\Users\alecl\Desktop\OOODIIIKKK\dazn_kodi.m3u"
TELEGRAM_CFG = r"C:\Users\alecl\Desktop\OOODIIIKKK\dazn_telegram.json"


def log(msg):
    xbmc.log(f"[DAZN M3U] {msg}", xbmc.LOGINFO)


def load_m3u():
    cfg = {}
    try:
        if os.path.exists(TELEGRAM_CFG):
            with open(TELEGRAM_CFG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
    except Exception:
        pass

    token = cfg.get("bot_token", "")
    chat_id = cfg.get("chat_id", "")
    if token and chat_id:
        try:
            params = urllib.parse.urlencode({"allowed_updates": json.dumps(["channel_post", "message"]), "limit": 10})
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/getUpdates?{params}",
                headers={"User-Agent": "Kodi/21"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            if data.get("ok") and data.get("result"):
                for upd in reversed(data["result"]):
                    msg = upd.get("channel_post") or upd.get("message") or {}
                    if str(msg.get("chat", {}).get("id", "")) == chat_id:
                        doc = msg.get("document")
                        if doc and doc.get("file_id"):
                            file_id = doc["file_id"]
                            fr = urllib.request.urlopen(
                                f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}",
                                timeout=10,
                            )
                            fd = json.loads(fr.read().decode("utf-8"))
                            if fd.get("ok") and fd["result"].get("file_path"):
                                fp = fd["result"]["file_path"]
                                dl = urllib.request.urlopen(
                                    f"https://api.telegram.org/file/bot{token}/{fp}",
                                    timeout=20,
                                )
                                return dl.read().decode("utf-8")
            xbmc.log("[DAZN M3U] Nessun documento M3U trovato su Telegram.", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[DAZN M3U] Telegram fetch fallito: {e}", xbmc.LOGINFO)

    try:
        with open(M3U, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def parse_m3u(content):
    if not content:
        return []
    entries = []
    for block in re.split(r"\n\s*\n", content):
        block = block.strip()
        if not block or block.startswith("#EXTM3U"):
            continue
        props = {}
        full_url = None
        extinf = None
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("#KODIPROP:"):
                rest = line[10:]
                if "=" in rest:
                    k, v = rest.split("=", 1)
                    props[k.strip()] = v.strip()
            elif line.startswith("#EXTINF:"):
                extinf = line
            elif line.startswith("http"):
                full_url = line
        if not full_url:
            continue
        title = "Sconosciuto"
        logo = ""
        group = "Altri"
        if extinf:
            if "," in extinf:
                title = extinf.rsplit(",", 1)[1].strip()
            m = re.search(r'tvg-logo="([^"]*)"', extinf)
            if m:
                logo = m.group(1)
            m = re.search(r'group-title="([^"]*)"', extinf)
            if m:
                group = m.group(1)
        entries.append({"title": title, "url": full_url, "logo": logo, "group": group, "props": props})
    return entries


def main():
    try:
        handle = int(sys.argv[1])
        q = (sys.argv[2] if len(sys.argv) > 2 else "").lstrip("?")
        log(f"call: {q}")

        params = {}
        for p in q.split("&"):
            if "=" in p:
                k, v = p.split("=", 1)
                params[urllib.parse.unquote(k)] = urllib.parse.unquote(v)

        content = load_m3u()
        if not content:
            xbmcgui.Dialog().ok("DAZN M3U", "File M3U non trovato né su rentry né localmente.\n\nEsegui estrazione DAZN.")
            return

        channels = parse_m3u(content)

        if "play" in params:
            idx = int(params["play"])
            if 0 <= idx < len(channels):
                ch = channels[idx]
                li = xbmcgui.ListItem(path=ch["url"])
                for k, v in ch["props"].items():
                    li.setProperty(k, v)
                xbmcplugin.setResolvedUrl(handle, True, li)
            return
        if not channels:
            xbmcgui.Dialog().ok("DAZN M3U", "Nessun canale trovato.")
            return

        if "group" in params:
            show_channels(handle, channels, params["group"])
        else:
            show_groups(handle, channels)

    except Exception as e:
        log(f"ERRORE: {e}")
        import traceback
        for line in traceback.format_exc().split("\n"):
            log(line)
        xbmcgui.Dialog().ok("DAZN M3U", f"Errore:\n{e}")


def show_groups(handle, channels):
    groups = {}
    for ch in channels:
        g = ch["group"]
        if g not in groups:
            groups[g] = []
        groups[g].append(ch)
    cat_logo = os.path.join(os.path.dirname(ADDON.getAddonInfo("path")), "dazn_cat.png")
    for name in sorted(groups):
        count = len(groups[name])
        li = xbmcgui.ListItem(label=f"{name}  [COLOR=grey]({count})[/COLOR]")
        li.setArt({"thumb": cat_logo, "icon": cat_logo})
        xbmcplugin.addDirectoryItem(handle, f"plugin://plugin.video.dazn-m3u/?group={urllib.parse.quote(name)}", li, isFolder=True)
    xbmcplugin.setContent(handle, "files")
    xbmcplugin.endOfDirectory(handle)


def show_channels(handle, channels, group_name):
    filtered = [c for c in channels if c["group"] == group_name]
    for ch in filtered:
        idx = channels.index(ch)
        li = xbmcgui.ListItem(label=ch["title"])
        if ch["logo"]:
            li.setArt({"thumb": ch["logo"], "icon": ch["logo"]})
        li.setInfo("video", {"title": ch["title"]})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(
            handle,
            f"plugin://plugin.video.dazn-m3u/?play={idx}",
            li,
            isFolder=False,
        )
    xbmcplugin.setContent(handle, "files")
    xbmcplugin.endOfDirectory(handle)


if __name__ == "__main__":
    main()
