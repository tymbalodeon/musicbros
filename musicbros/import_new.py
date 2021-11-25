import pickle
from os import system, walk
from pathlib import Path

from tinytag import TinyTag
from typer import echo

from .config import get_config_option, get_ignored_directories
from .helpers import color

AUDIO_FILE_TYPES = ("*.mp3", "*.m4a", "*.flac", "*.aif*")
ERRORS = {
    "escape_error": "Error parsing path name",
    "conflicting_track_totals": "Album tracks include more than one track total number",
    "missing_track_total": "Album does not contain a track total number",
    "missing_tracks": "Album is missing tracks",
    "no_tracks": "Folder does not contain supported audio files",
    "wav_files": "Album is in wav format",
}
IMPORTABLE_ERROR_KEYS = [
    "conflicting_track_totals",
    "missing_track_total",
    "missing_tracks",
    "wav_files",
]


def get_imported_albums():
    with open(get_config_option("pickle_file"), "rb") as raw_pickle:
        unpickled = pickle.load(raw_pickle)["taghistory"]
        albums = {album[0].decode() for album in unpickled}
    return albums


def get_album_directories():
    return [
        root
        for root, dirs, files in walk(get_config_option("shared_directory"))
        if files and not dirs
    ]


def get_tracks(album):
    audio_files = list()
    for file_type in AUDIO_FILE_TYPES:
        audio_files.extend(Path(album).glob(file_type))
    return audio_files


def get_wav_tracks(album):
    return bool([track for track in Path(album).glob("*.wav")])


def get_track_total(tracks):
    track_total = 0
    message = None
    track_totals = {TinyTag.get(track).track_total for track in tracks}
    track_total = next(iter(track_totals))
    if len(track_totals) > 1:
        message = "conflicting_track_totals"
    elif not track_total:
        message = "missing_track_total"
    else:
        track_total = int(track_total)
    return track_total, message


def is_ignored_directory(album):
    for directory in get_ignored_directories():
        if directory in album:
            return True
    return False


def is_already_imported(album):
    return album in get_imported_albums()


def get_import_error_message(album, error_key):
    return f"{ERRORS[error_key]}: {color(album, 'cyan')}"


def get_single_or_double_quote(album):
    if "'" in album and '"' in album:
        return None
    elif '"' in album:
        return "'"
    else:
        return '"'


def beet_import(album):
    quote_character = get_single_or_double_quote(album)
    album = album.replace("$", r"\$")
    if quote_character:
        system(f"beet import {quote_character}{album}{quote_character}")
        return True
    else:
        return False


def import_wav_files(album):
    system(f"open -a '{get_config_option('music_player')}' '{album}'")


def import_album(album, tracks, import_all):
    track_count = len(tracks)
    track_total, message = get_track_total(tracks)
    if import_all or track_count == track_total:
        error = None if beet_import(album) else "escape_error"
    elif message:
        error = message
    elif isinstance(track_total, int) and track_count > track_total:
        error = "conflicting_track_totals"
    else:
        error = "missing_tracks"
    return error


def import_albums(albums, import_all=False):
    errors = {key: list() for key in ERRORS.keys()}
    imports = False
    wav_imports = 0
    skipped_count = 0
    importable_error_albums = list()
    for album in albums:
        if not import_all:
            if is_ignored_directory(album):
                continue
            if is_already_imported(album):
                skipped_count += 1
                continue
        tracks = get_tracks(album)
        wav_tracks = get_wav_tracks(album)
        if tracks:
            error = import_album(album, tracks, import_all)
            if error:
                errors[error].append(get_import_error_message(album, error))
                if error in IMPORTABLE_ERROR_KEYS:
                    importable_error_albums.append(album)
            else:
                imports = True
        if wav_tracks:
            if import_all:
                import_wav_files(album)
                wav_imports += 1
            else:
                errors["wav_files"].append(get_import_error_message(album, "wav_files"))
                importable_error_albums.append(album)
        if not tracks and not wav_tracks:
            errors["no_tracks"].append(get_import_error_message(album, "no_tracks"))
    if wav_imports:
        echo(f"Imported {wav_imports} albums in WAV format.")
    if not import_all:
        echo(f"{skipped_count} albums skipped.")
    for key, error_list in errors.items():
        if error_list:
            color(key.replace("_", " ").upper(), echo=True)
            for error in error_list:
                echo(f"\t{error}")
    return imports, errors, importable_error_albums
