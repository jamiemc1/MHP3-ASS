"""The TUI's keys and the command palette's commands.

Not a port: the TUI's own keys. The app-wide keys are few (search, quit,
options, the region keys and help); the results' keys belong to the sets
region, so they only fire, and only show in the footer, while it has focus.
Everything else, the form's fields included, is reached by name from the
command palette.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.binding import Binding


def app_keys() -> list[Binding]:
    """The keys that work anywhere on the main screen, outside a text box."""
    keys = [
        Binding("ctrl+s", "search", "Search"),
        Binding("question_mark", "toggle_keys", "Keys"),
        Binding("q", "quit", "Quit"),
        Binding("o", "options", "Options"),
        Binding("escape", "cancel_search", "Cancel", show=False),
        Binding("1", "region(1)", "Query", show=False),
        Binding("2", "region(2)", "Charms", show=False),
        Binding("3", "region(3)", "Sets", show=False),
        Binding("e", "edit_query", "Edit query", show=False),
        # Ahead of the screen's own Tab, which visits every widget.
        Binding("tab", "cycle(1)", "Next region", show=False, priority=True),
        Binding("shift+tab", "cycle(-1)", "Previous region", show=False, priority=True),
    ]
    return keys


def results_keys() -> list[Binding]:
    """The sets region's keys; their actions are the app's."""
    keys = [
        Binding("s", "app.sort", "Sort"),
        Binding("S", "app.reverse_sort", "Reverse"),
        Binding("slash", "app.find", "Find"),
        Binding("n", "app.find_next(1)", "Next", show=False),
        Binding("N", "app.find_next(-1)", "Previous", show=False),
    ]
    return keys


@dataclass(frozen=True)
class PaletteCommand:
    """A command palette entry: its ``title`` and ``help``, and the app
    ``action`` it runs (as a binding names one)."""

    title: str
    help: str
    action: str


def palette_commands() -> list[PaletteCommand]:
    """Every action by name, in the order the palette lists them before
    anything is typed. Textual adds its own (Theme, Quit, Keys, Screenshot)."""
    commands = [
        PaletteCommand("Search", "Search with the query as edited", "search"),
        PaletteCommand("Cancel search", "Stop the running search", "cancel_search"),
        PaletteCommand("Edit query", "Open the query editor at the skills", "edit_query"),
        PaletteCommand("Add skill…", "Type a skill's name to add it", "edit_field('skill_search')"),
        PaletteCommand("Set hunter…", "Blademaster or gunner", "set_field('hunter_type')"),
        PaletteCommand("Set gender…", "The hunter's gender", "set_field('gender')"),
        PaletteCommand("Set HR…", "The hunter rank", "set_field('hr')"),
        PaletteCommand("Set village…", "The village quest stars", "set_field('elder_star')"),
        PaletteCommand("Set weapon slots…", "The weapon's slots", "set_field('weapon_slots')"),
        PaletteCommand(
            "Set charm mode…", "Which charms the search uses", "set_field('charm_mode')"
        ),
        PaletteCommand("Sort…", "Choose what the sets are sorted by", "sort"),
        PaletteCommand("Reverse sort", "Turn the sort the other way round", "reverse_sort"),
        PaletteCommand("Find…", "Find sets by piece, jewel, charm or skill", "find"),
        PaletteCommand("Find next", "The next set the find text matches", "find_next(1)"),
        PaletteCommand("Find previous", "The previous set the find text matches", "find_next(-1)"),
        PaletteCommand("Go to the query", "Focus the query region (1)", "region(1)"),
        PaletteCommand("Go to the charms", "Focus the charm sidebar (2)", "region(2)"),
        PaletteCommand("Go to the sets", "Focus the sets table (3)", "region(3)"),
        PaletteCommand("Options", "Armour options, language, theme and processes", "options"),
    ]
    return commands
