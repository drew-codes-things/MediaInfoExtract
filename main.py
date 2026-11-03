import argparse
import csv
import os
import re
import shlex
from pathlib import Path

ASCII_ART = r"""
    __  ___         ___       ____      ____         ______                           __  __
   /  |/  /__  ____/ (_)___ _/  _/___  / __/___     / ____/___  _________ ___  ____ _/ /_/ /____  _____
  / /|_/ / _ \/ __  / / __ `// // __ \/ /_/ __ \   / /_  / __ \/ ___/ __ `__ \/ __ `/ __/ __/ _ \/ ___/
 / /  / /  __/ /_/ / / /_/ // // / / / __/ /_/ /  / __/ / /_/ / /  / / / / / / /_/ / /_/ /_/  __/ /
/_/  /_/\___/\__,_/_/\__,_/___/_/ /_/_/  \____/  /_/    \____/_/  /_/ /_/ /_/\__,_/\__/\__/\___/_/
"""

DEFAULT_SOURCES = [
    "BD", "DVD", "NF", "CR", "AMZN", "HULU", "DSNP", "ATVP",
    "PMTP", "PCOK", "MAX", "STAN",
    "HMAX", "ITVX", "BBCIPLAYER", "PEACOCK",
]


def load_sources():
    sources_file = Path(__file__).parent / "sources.txt"
    if sources_file.is_file():
        try:
            lines = [l.strip() for l in sources_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                return lines
        except OSError:
            pass
    return DEFAULT_SOURCES


def extract_info(file_path: str) -> dict:
    info = {"Audio": [], "Subtitles": []}
    section = None
    audio_info = subtitle_info = None
    language_cnt = format_cnt = 0

    base = os.path.basename(file_path)
    if base.endswith(".MediaInfo.txt"):
        stem = base[:-13]
        stem = stem.rstrip('.')
    else:
        stem = ".".join(base.split(".")[:-1])

    for ext in (".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"):
        if stem.endswith(ext):
            stem = stem[:-len(ext)]
            break
    stem = stem.rstrip(".")

    bracket_parts = [part.split("]")[0].strip()
                     for part in base.split("[") if "]" in part]
    quality_parts = [q for q in bracket_parts if re.fullmatch(r"\d+p|\d+K", q, re.I)]
    info["Quality"] = " ".join(quality_parts) if quality_parts else "N/A"
    info["Complete name"] = stem

    with open(file_path, encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()

    for line in lines:
        stripped = line.strip()
        key = line.split(":", 1)[0].strip() if ":" in line else line.strip()
        if re.match(r'^Video\b', stripped):
            section = "Video"
        elif re.match(r'^Audio\b', stripped):
            if audio_info:
                info["Audio"].append(audio_info)
            audio_info = {}
            section = "Audio"; language_cnt = format_cnt = 0
        elif re.match(r'^Text\b', stripped):
            if subtitle_info:
                info["Subtitles"].append(subtitle_info)
            subtitle_info = {}
            section = "Text"; language_cnt = 0
        elif not stripped:
            section = None

        if section == "Video":
            if key == "Bit rate":
                info["Bit rate"] = _norm_bitrate(line)
            elif line.startswith("Frame rate"):
                fps = line.split(":", 1)[1].split("(")[0].strip()
                info["Frame rate"] = f"{fps} fps"
            elif line.startswith("Format profile"):
                info["Format profile"] = line.split(":", 1)[1].strip()
            elif line.startswith("HDR format"):
                _handle_hdr(info, line)
            elif key == "Format":
                vals = line.split(":", 1)[1].split()
                info["Format"] = vals[1] if len(vals) > 1 else vals[0]
            elif line.startswith("Bit depth"):
                info["Bit depth"] = line.split(":", 1)[1].strip().replace("bits", "Bit")
            elif "Display aspect ratio" in line and "active" not in line.lower():
                raw = line.split(":", 1)[1].strip()
                info["Display aspect ratio"] = _norm_aspect_ratio(raw)

        elif section == "Audio":
            if "Language" in line and "Language_More" not in line:
                language_cnt += 1
                if language_cnt == 2:
                    audio_info["Language"] = line.split(":", 1)[1].strip()
            elif key == "Format":
                format_cnt += 1
                if _use_this_format(format_cnt, audio_info):
                    audio_info["Format"] = _audio_fmt(line)
            elif "Channel(s)" in line:
                audio_info["Channels"] = _norm_channels(line)
            elif "Sampling rate" in line:
                audio_info["Sampling rate"] = line.split(":", 1)[1].strip()
            elif key == "Bit rate":
                audio_info["Bit rate"] = _clean_kbps(line)
            elif key == "Maximum bit rate":
                audio_info["Maximum bit rate"] = _clean_kbps(line)
            elif "Bit depth" in line:
                m = re.search(r"\d+", line.split(":", 1)[1])
                audio_info["Bit depth"] = f"{m.group()}-bit" if m else line.split(":", 1)[1].strip()

        elif section == "Text":
            if "Language" in line and "Language_More" not in line:
                language_cnt += 1
                if language_cnt == 2:
                    subtitle_info["Language"] = line.split(":", 1)[1].strip()
            elif key == "Format":
                raw = line.split(":", 1)[1].strip()
                if raw == "UTF-8" or "ffdshow" in raw.lower():
                    subtitle_info["Format"] = "ASS"
                else:
                    subtitle_info["Format"] = raw

    if audio_info:
        info["Audio"].append(audio_info)
    if subtitle_info:
        info["Subtitles"].append(subtitle_info)

    if info["Quality"] == "N/A":
        _, h = _resolution(lines)
        if h:
            info["Quality"] = _height_to_quality(h)
    return info


def _norm_bitrate(line):
    raw = line.split(":", 1)[1].strip()
    num_match = re.search(r'(\d[\d\s,]*(?:\.\d+)?)', raw)
    try:
        if not num_match:
            return raw.replace("bits", "Bit")
        val_str = num_match.group(1).replace(" ", "").replace(",", "")
        val = float(val_str)
        lower = raw.lower()
        if "mb/s" in lower or "mbps" in lower:
            return f"{int(val * 1000)} kbps"
        if "kb/s" in lower or "kbps" in lower:
            return f"{int(val)} kbps"
        if val > 100000:
            return f"{int(val / 1000)} kbps"
        return f"{int(val)} kbps" if val > 0 else raw
    except (ValueError, IndexError):
        return raw.replace("bits", "Bit")


def _handle_hdr(info, line):
    for part in line.split(":", 1)[1].split("/"):
        part = part.strip()
        if "Dolby Vision" in part:
            info["Dolby Vision"] = "Dolby Vision"
        elif "HDR10+" in part:
            info["HDR format"] = "HDR10+"
        elif "HDR10" in part and "HDR format" not in info:
            info["HDR format"] = "HDR10"


def _use_this_format(cnt, ainfo):
    return cnt == 1


def _audio_fmt(line):
    raw = line.split(":", 1)[1].lower()
    parts = line.split(":", 1)[1].split()

    if "truehd" in raw or "mlp fba" in raw:
        if "16-ch" in raw or "atmos" in raw:
            return "MLP FBA 16-ch"
        return "MLP FBA"
    if "dts" in raw:
        if "xll" in raw or "hd master" in raw:
            return "DTS XLL"
        if "x" in raw:
            return "DTS XLL X"
        return "DTS"
    if "e-ac-3" in raw or "eac3" in raw:
        if "joc" in raw:
            return "E-AC-3 JOC"
        return "E-AC-3"
    if "ac-3" in raw or "ac3" in raw:
        return "AC-3"
    if "flac" in raw:
        return "FLAC"
    if "aac" in raw:
        return "AAC"
    if "opus" in raw:
        return "OPUS"
    if "vorbis" in raw:
        return "VORBIS"
    if "mp3" in raw:
        return "MP3"

    fmt = parts[1] if len(parts) > 1 else parts[0]
    return fmt.replace("JOC", "E-AC-3 JOC")


def _norm_channels(line):
    txt = line.split(":", 1)[1].strip()
    m = re.search(r"\d+", txt)
    if not m:
        return txt
    n = int(m.group())
    return {8: "7.1", 6: "5.1", 2: "2"}.get(n, txt)


def _clean_kbps(line):
    val = line.split(":", 1)[1].strip().replace("kb/s", "kbps").replace("Kb/s", "kbps")
    numeric_part = val.replace(" ", "").replace("kbps", "")
    if numeric_part.isdigit():
        return f"{numeric_part} kbps"
    return val


def _resolution(lines):
    w = h = None
    for ln in lines:
        if w is None and "Width" in ln:
            parts = ln.split(":", 1)
            if len(parts) > 1:
                digits = "".join(filter(str.isdigit, parts[1]))
                if digits:
                    w = int(digits)
        if h is None and "Height" in ln:
            parts = ln.split(":", 1)
            if len(parts) > 1:
                digits = "".join(filter(str.isdigit, parts[1]))
                if digits:
                    h = int(digits)
    return w, h


def _height_to_quality(h):
    return ("2160p" if h >= 2160 else "1440p" if h >= 1440 else
            "1080p" if h >= 1080 else "720p" if h >= 720 else
            "480p" if h >= 480 else f"{h}p")


def _norm_aspect_ratio(txt):
    return txt.strip()


def format_output(info, is_remux, src):
    display_name = re.sub(r'\s*\[[^\]]*\]', '', info['Complete name']).strip()
    vline = (f"Video: {display_name} / {info.get('Bit rate','N/A')} / "
             f"{info['Quality']} / {info.get('Frame rate','N/A')} / "
             f"{info.get('Format profile','N/A')} /")
    if "Dolby Vision" in info:
        vline += f" {info['Dolby Vision']} /"
    if "HDR format" in info:
        vline += f" {info['HDR format']} /"
    vline += (f" {info.get('Bit depth','N/A')} / "
              f"{info.get('Display aspect ratio','N/A')} / "
              f"{info.get('Format','N/A')} / {src}")

    audio = []
    for a in info["Audio"]:
        ln = "Audio:"
        for k in ("Language", "Format", "Channels", "Sampling rate"):
            if k in a:
                ln += f" {a[k]} /"
        rate_key = "Maximum bit rate" if a.get("Channels") in {"7.1"} else "Bit rate"
        if rate_key in a:
            ln += f" {a[rate_key].replace(' ', '').replace('kbps', ' kbps')} /"
        if "Bit depth" in a:
            ln += f" {a['Bit depth']} /"
        ln += f" {src}"
        audio.append(ln)

    subs = []
    for s in info["Subtitles"]:
        if {"Language", "Format"} <= s.keys():
            subs.append(f"Subtitle: {s['Language']} / {s['Format']} / {src}")

    clean_name = re.sub(r'\s*\[\d+[pK]\]', '', info['Complete name'], flags=re.IGNORECASE).strip()
    fname = clean_name
    if info.get('Quality') and info['Quality'] != "N/A":
        fname += f" [{info['Quality']}]"
    if "Dolby Vision" in info:
        fname += f" [{info['Dolby Vision']}]"
    if "HDR format" in info:
        fname += f" [{info['HDR format']}]"
    if is_remux:
        fname += " [Remux]"

    return f"File name: {fname}\n\n{vline}\n\n" + "\n".join(audio) + "\n\n" + "\n".join(subs)


def process_file(path, is_remux, src):
    p = Path(path.strip('"'))
    if not p.is_file():
        print(f"[!] Not found: {p}")
        return
    try:
        info = extract_info(str(p))
        out_text = format_output(info, is_remux, src)
        out_path = p.with_name(f"Formatted - {p.stem}{p.suffix}")
        try:
            out_path.write_text(out_text, encoding="utf-8")
            print(f"[OK] {out_path}")
        except OSError as e:
            print(f"[!] Could not write output file '{out_path}': {e}")
            print("    Tip: check that the folder is not read-only or network-mounted.")
    except Exception as e:
        print(f"[!] Error processing {p.name}: {e}")


CSV_COLUMNS = [
    "File", "Name", "Quality", "Video format", "Video bit rate", "Frame rate", "Format profile",
    "HDR", "Dolby Vision", "Bit depth", "Aspect ratio", "Audio tracks", "Audio", "Subtitle languages",
]
DEFAULT_CSV_NAME = "mediainfo-summary.csv"


def is_mediainfo_report(path):
    try:
        with open(path, encoding="utf-8-sig", errors="ignore") as fh:
            for line in fh:
                if line.strip():
                    return line.strip() == "General"
    except OSError:
        return False
    return False


def find_reports(folder):
    return sorted(p for p in Path(folder).rglob("*.txt") if is_mediainfo_report(p))


def audio_summary(track):
    return " ".join(track[key] for key in ("Language", "Format", "Channels") if key in track)


def csv_row(path, folder, info):
    return {
        "File": str(Path(path).relative_to(folder)),
        "Name": re.sub(r"\s*\[[^\]]*\]", "", info["Complete name"]).strip(),
        "Quality": info.get("Quality", "N/A"),
        "Video format": info.get("Format", ""),
        "Video bit rate": info.get("Bit rate", ""),
        "Frame rate": info.get("Frame rate", ""),
        "Format profile": info.get("Format profile", ""),
        "HDR": info.get("HDR format", ""),
        "Dolby Vision": info.get("Dolby Vision", ""),
        "Bit depth": info.get("Bit depth", ""),
        "Aspect ratio": info.get("Display aspect ratio", ""),
        "Audio tracks": len(info["Audio"]),
        "Audio": "; ".join(audio_summary(track) for track in info["Audio"]),
        "Subtitle languages": ", ".join(sub["Language"] for sub in info["Subtitles"] if "Language" in sub),
    }


def write_folder_csv(folder, output=None):
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(f"Folder not found: {folder}")
    out_path = Path(output) if output else folder / DEFAULT_CSV_NAME
    rows = []
    failed = []
    for report in find_reports(folder):
        try:
            rows.append(csv_row(report, folder, extract_info(str(report))))
        except Exception as e:
            failed.append(report)
            print(f"[!] Error processing {report.name}: {e}")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] {len(rows)} report(s) written to {out_path}" + (f", {len(failed)} failed" if failed else ""))
    return out_path, len(rows), failed


def ask_yes_no(prompt, default="y"):
    default = default.lower()
    assert default in {"y", "n"}
    suffix = "[Y/n]" if default == "y" else "[y/N]"
    ans = input(f"{prompt} {suffix}: ").strip().lower()
    if not ans:
        ans = default
    return ans == "y"


def choose_source(sources):
    print("\nChoose media source:")
    for i, s in enumerate(sources, 1):
        print(f"{i}. {s}")
    choice = input(f"Enter (1-{len(sources)}) [1]: ").strip() or "1"
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(sources):
            return sources[idx]
    except ValueError:
        pass
    return sources[0]


def parse_args():
    parser = argparse.ArgumentParser(description="Format MediaInfo text reports for release notes.")
    parser.add_argument("--csv", metavar="FOLDER", default=None,
                        help="Write one CSV row per MediaInfo report found in FOLDER (and its subfolders), then exit")
    parser.add_argument("-o", "--output", default=None,
                        help=f"CSV path for --csv (default: FOLDER/{DEFAULT_CSV_NAME})")
    return parser.parse_args()


def run_csv_mode(folder, output=None):
    try:
        write_folder_csv(folder, output)
    except (NotADirectoryError, OSError) as e:
        print(f"[!] {e}")
        return False
    return True


def main():
    args = parse_args()
    if args.csv:
        raise SystemExit(0 if run_csv_mode(args.csv, args.output) else 1)

    print(ASCII_ART)
    sources = load_sources()

    print("Select run mode:")
    print("1. Batch - drag and drop files or paste quoted paths")
    print("2. Interactive - one path at a time")
    print("3. Folder - one CSV summary of every MediaInfo report in a folder")
    mode = input("Choose 1, 2 or 3 [1]: ").strip() or "1"

    if mode == "3":
        folder = input("\nFolder path: ").strip().strip('"')
        run_csv_mode(folder)

    elif mode == "1":
        print("\nDrag and drop your file(s) here (quoted paths are supported), then press Enter:")
        raw = input("> ").strip()
        files = shlex.split(raw)
        if not files:
            print("No files given."); return

        same = ask_yes_no("\nUse the SAME settings for every file?", default="y")
        if same:
            is_remux = ask_yes_no("Remux?", default="n")
            src = choose_source(sources)
            for f in files:
                process_file(f, is_remux, src)
        else:
            for f in files:
                print(f"\n--- {f} ---")
                is_remux = ask_yes_no("Remux?", default="n")
                src = choose_source(sources)
                process_file(f, is_remux, src)

    else:
        while True:
            f = input("\nEnter path to MediaInfo.txt file: ").strip()
            if not f:
                break
            is_remux = ask_yes_no("Remux?", default="n")
            src = choose_source(sources)
            process_file(f, is_remux, src)
            if not ask_yes_no("Process another file?", default="y"):
                break

    input("\nDone. Press Enter to exit...")


if __name__ == "__main__":
    main()
