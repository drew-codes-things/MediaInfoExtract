import csv
import sys

import pytest

import main

REPORT = """General
Complete name                            : Show.Name.S01E01 [1080p].mkv

Video
Format                                   : AVC
Format profile                           : High@L4.1
Bit rate                                 : 8 500 kb/s
Width                                    : 1 920 pixels
Height                                   : 1 080 pixels
Display aspect ratio                     : 16:9
Frame rate                               : 23.976 (24000/1001) FPS
Bit depth                                : 8 bits

Audio #1
Format                                   : AC-3
Channel(s)                               : 6 channels
Language                                 : en
Language                                 : English

Audio #2
Format                                   : AAC LC
Channel(s)                               : 2 channels
Language                                 : ja
Language                                 : Japanese

Text #1
Format                                   : PGS
Language                                 : en
Language                                 : English
"""


@pytest.fixture
def library(tmp_path):
    (tmp_path / "Season 1").mkdir()
    (tmp_path / "Season 1" / "Show.Name.S01E01 [1080p].mkv.MediaInfo.txt").write_text(REPORT)
    (tmp_path / "Season 1" / "Show.Name.S01E02 [1080p].mkv.MediaInfo.txt").write_text("﻿" + REPORT)
    (tmp_path / "Formatted - old.txt").write_text("File name: old\n\nVideo: ...")
    (tmp_path / "notes.txt").write_text("shopping list")
    return tmp_path


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_only_mediainfo_reports_are_picked_up(library):
    names = [path.name for path in main.find_reports(library)]
    assert names == ["Show.Name.S01E01 [1080p].mkv.MediaInfo.txt", "Show.Name.S01E02 [1080p].mkv.MediaInfo.txt"]


def test_csv_has_one_row_per_report(library):
    out_path, count, failed = main.write_folder_csv(library)
    assert out_path == library / main.DEFAULT_CSV_NAME
    assert (count, failed) == (2, [])
    first = read_rows(out_path)[0]
    assert first["File"].startswith("Season 1")
    assert first["Name"] == "Show.Name.S01E01"
    assert first["Quality"] == "1080p"
    assert first["Frame rate"] == "23.976 fps"
    assert first["Audio tracks"] == "2"
    assert first["Audio"].count(";") == 1 and "English" in first["Audio"] and "Japanese" in first["Audio"]
    assert first["Subtitle languages"] == "English"


def test_custom_output_path(library, tmp_path_factory):
    target = tmp_path_factory.mktemp("out") / "all.csv"
    main.write_folder_csv(library, target)
    assert len(read_rows(target)) == 2


def test_empty_folder_writes_header_only(tmp_path):
    out_path, count, _ = main.write_folder_csv(tmp_path)
    assert count == 0
    assert out_path.read_text().startswith("File,Name,Quality")


def test_cli_csv_mode_exits_non_zero_for_missing_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--csv", str(tmp_path / "nope")])
    with pytest.raises(SystemExit) as raised:
        main.main()
    assert raised.value.code == 1


def test_cli_csv_mode(library, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--csv", str(library)])
    with pytest.raises(SystemExit) as raised:
        main.main()
    assert raised.value.code == 0
    assert (library / main.DEFAULT_CSV_NAME).exists()
