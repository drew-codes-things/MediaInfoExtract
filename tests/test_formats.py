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
