"""Where the TUI keeps its files, and its own settings file ``tui.toml``.

Not a port: the original keeps ``settings.cfg`` and ``Data/mycharms.txt``
beside its executable. The TUI keeps the same two files, in the original's
formats, in a saved-data folder, so they can be copied to or from a Windows
install. The TUI's own folder (``config_dir``) is ``~/.config/mhp3-ass`` on
macOS and Linux (``$XDG_CONFIG_HOME`` when set) and ``%APPDATA%\\mhp3-ass``
on Windows; it holds ``tui.toml``, which names the saved-data folder when
it isn't the TUI's own, and the settings ``settings.cfg`` has no line for.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class TuiSettings:
    """``tui.toml``: the saved-data folder (``None``: the TUI's own folder),
    the search's processes (``None``: one per CPU, at most 8), whether the
    results are shown reversed, the colour theme's name (``None``: the
    default) and the folder exported sets go to (``None``: the folder the
    TUI is started from)."""

    data_dir: Path | None = None
    jobs: int | None = None
    reverse: bool = False
    theme: str | None = None
    export_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.jobs is not None and self.jobs < 1:
            raise ValueError(f"jobs must be at least 1, not {self.jobs}")


def config_dir(env: Mapping[str, str], platform: str, home: Path) -> Path:
    """The TUI's own folder for ``platform`` (``sys.platform``), from the
    environment ``env`` and the home folder ``home``."""
    if platform == "win32":
        app_data = env.get("APPDATA")
        if app_data is None:
            raise KeyError("APPDATA isn't set, so there is no folder for the TUI's files")
        folder = Path(app_data) / "mhp3-ass"
        return folder
    xdg = env.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg is not None and xdg != "" else home / ".config"
    folder = base / "mhp3-ass"
    return folder


def read_tui_settings(path: Path) -> TuiSettings:
    """``tui.toml``, or the defaults when there's no such file. Unknown keys
    and values of the wrong type raise ``ValueError``."""
    if not path.exists():
        return TuiSettings()
    try:
        with path.open("rb") as file:
            table = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: {error}") from error
    # A fixed order, not the file's, so a file with several bad values
    # always reports the same one first.
    expected = [
        ("data_dir", _is_text, "a string"),
        ("export_dir", _is_text, "a string"),
        ("jobs", _is_whole_number, "a whole number"),
        ("reverse", _is_true_or_false, "true or false"),
        ("theme", _is_text, "a string"),
    ]
    unknown = set(table) - {key for key, _, _ in expected}
    if unknown:
        raise ValueError(f"{path}: unknown settings {sorted(unknown)}")
    for key, is_valid, kind in expected:
        if key in table and not is_valid(table[key]):
            raise ValueError(f"{path}: {key} must be {kind}, not {table[key]!r}")
    values = dict(table)
    for key in ("data_dir", "export_dir"):
        if key in values:
            values[key] = Path(values[key])
    settings = TuiSettings(**values)
    return settings


def _is_text(value: object) -> bool:
    return isinstance(value, str)


def _is_whole_number(value: object) -> bool:
    whole_number = isinstance(value, int) and not isinstance(value, bool)
    return whole_number


def _is_true_or_false(value: object) -> bool:
    return isinstance(value, bool)


def tui_settings_text(settings: TuiSettings) -> str:
    """``settings`` as ``tui.toml``; defaults are left out."""
    lines = []
    for field in fields(settings):
        value = getattr(settings, field.name)
        if value == field.default:
            continue
        if isinstance(value, bool):
            written = "true" if value else "false"
        elif isinstance(value, int):
            written = str(value)
        elif isinstance(value, (str, Path)):
            # JSON's escapes for quotes, backslashes and control characters
            # are TOML's; other characters stay literal, since TOML rejects
            # JSON's surrogate-pair escapes for characters above U+FFFF.
            written = json.dumps(str(value), ensure_ascii=False)
        else:
            raise TypeError(f"no tui.toml form for {field.name} = {value!r}")
        lines.append(f"{field.name} = {written}")
    text = "".join(f"{line}\n" for line in lines)
    return text


def write_tui_settings(path: Path, settings: TuiSettings) -> None:
    write_atomically(path, tui_settings_text(settings).encode("utf-8"))


def write_atomically(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` through a new temporary file beside it,
    flushed to disk before it replaces ``path``, so a crash or a full disk
    part-way leaves the old file whole. A failed write removes the
    temporary file; the new file is readable only by its owner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        # Gone after a successful replace; left behind by a failed write.
        temporary.unlink(missing_ok=True)


def saved_data_dir(env: Mapping[str, str], settings: TuiSettings, own_dir: Path) -> Path:
    """Where ``settings.cfg`` and ``mycharms.txt`` live: ``MHP3ASS_HOME`` when
    set, else ``tui.toml``'s ``data_dir``, else the TUI's own folder. A
    leading ``~`` is the home folder; a relative ``data_dir`` is under the
    TUI's own folder, so it doesn't depend on where the TUI is started."""
    override = _home_override(env)
    if override is not None:
        return Path(override).expanduser()
    if settings.data_dir is not None:
        chosen = settings.data_dir.expanduser()
        folder = chosen if chosen.is_absolute() else own_dir / chosen
        return folder
    return own_dir


@dataclass(frozen=True)
class TuiFolders:
    """The TUI's own folder, its settings, and ``MHP3ASS_HOME`` if set."""

    own: Path
    settings: TuiSettings
    env: Mapping[str, str]

    @classmethod
    def find(cls, env: Mapping[str, str], platform: str, home: Path) -> TuiFolders:
        """The folders for ``env``, ``platform`` (``sys.platform``) and ``home``,
        with ``tui.toml`` read from the TUI's own folder."""
        own = config_dir(env, platform=platform, home=home)
        folders = cls(own=own, settings=read_tui_settings(own / "tui.toml"), env=env)
        return folders

    @property
    def settings_file(self) -> Path:
        return self.own / "tui.toml"

    @property
    def saved(self) -> Path:
        return saved_data_dir(self.env, self.settings, own_dir=self.own)

    @property
    def saved_set_by_env(self) -> bool:
        """``MHP3ASS_HOME`` chooses the saved-data folder, whatever ``tui.toml`` says."""
        set_by_env = _home_override(self.env) is not None
        return set_by_env


def _home_override(env: Mapping[str, str]) -> str | None:
    """``MHP3ASS_HOME`` when it is set and not empty."""
    override = env.get("MHP3ASS_HOME")
    if override is None or override == "":
        return None
    return override


def my_charms_file(folder: Path, shipped: Path) -> Path:
    """``folder``'s ``mycharms.txt``, copied from the original's shipped list
    (``shipped``) the first time, as a fresh install of the original has it."""
    path = folder / "mycharms.txt"
    if not path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(shipped, path)
    return path
