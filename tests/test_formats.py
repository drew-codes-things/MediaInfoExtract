import main

DVD_REPORT = """General
Complete name                            : Old.Film.1999.mkv

Video
Format                                   : MPEG Video
Format version                           : Version 2
Format profile                           : Main@Main
Bit rate                                 : 6 000 kb/s
Width                                    : 720 pixels
Height                                   : 480 pixels
Display aspect ratio                     : 16:9
Frame rate                               : 29.970 (30000/1001) FPS
Bit depth                                : 8 bits

Audio #1
Format                                   : MPEG Audio
Format version                           : Version 1
Format profile                           : Layer 3
Channel(s)                               : 2 channels
Sampling rate                            : 48.0 kHz
Bit rate                                 : 192 kb/s
Language                                 : en
Language                                 : English

Audio #2
Format                                   : MPEG Audio
Format version                           : Version 1
Format profile                           : Layer 2
Channel(s)                               : 2 channels
Language                                 : fr
Language                                 : French
"""


def extract(tmp_path, text, name="Film.mkv.MediaInfo.txt"):
    path = tmp_path / name
    path.write_text(text)
    return main.extract_info(str(path))


def test_mpeg_video_keeps_its_whole_format_name(tmp_path):
    assert extract(tmp_path, DVD_REPORT)["Format"] == "MPEG Video"


def test_mpeg_audio_layers_are_named_mp3_and_mp2(tmp_path):
    assert [track["Format"] for track in extract(tmp_path, DVD_REPORT)["Audio"]] == ["MP3", "MP2"]


def test_unquoted_windows_path_keeps_its_backslashes():
    assert main.split_dropped_paths(r"C:\Users\me\Show.mkv.MediaInfo.txt", windows=True) == [
        r"C:\Users\me\Show.mkv.MediaInfo.txt"
    ]


def test_quoted_windows_paths_with_spaces_split_on_the_quotes():
    raw = r'"C:\My Shows\A.MediaInfo.txt" "C:\My Shows\B.MediaInfo.txt"'
    assert main.split_dropped_paths(raw, windows=True) == [r"C:\My Shows\A.MediaInfo.txt", r"C:\My Shows\B.MediaInfo.txt"]


def test_unbalanced_apostrophe_is_reported_not_raised(capsys):
    assert main.split_dropped_paths("/media/Show/It's Always.MediaInfo.txt", windows=False) == []
    assert "quote" in capsys.readouterr().out.lower()


def test_posix_drag_and_drop_quoting_still_works():
    assert main.split_dropped_paths("'/media/Show/It'\\''s Always.MediaInfo.txt'", windows=False) == [
        "/media/Show/It's Always.MediaInfo.txt"
    ]


SEVEN_ONE_REPORT = """General
Complete name                            : Film.mkv

Video
Format                                   : HEVC
Width                                    : 3 840 pixels
Height                                   : 2 160 pixels

Audio
Format                                   : E-AC-3
Channel(s)                               : 8 channels
Sampling rate                            : 48.0 kHz
Bit rate                                 : 1 536 kb/s
Language                                 : en
Language                                 : English
"""


def test_seven_one_track_without_a_maximum_uses_its_bit_rate(tmp_path):
    output = main.format_output(extract(tmp_path, SEVEN_ONE_REPORT), False, "BD")
    assert "Audio: English / E-AC-3 / 7.1 / 48.0 kHz / 1536 kbps / BD" in output
