import os
from datetime import datetime
from functools import partial

import instructor
from openai import OpenAI

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, RichLog, Static
from textual.worker import Worker, WorkerState

from pet import (
    load_game,
    create_default_world,
    save_game,
    PetAgent,
    EnvironmentAgent,
    SAVE_FILE,
)

AMBER = "#ffb454"
DIM = "#8a7a63"
OK = "#a9dc76"
WARN = "#ffd866"
BAD = "#ff5c57"

MOOD_COLORS = {
    "Starving": BAD,
    "Lonely": BAD,
    "Exhausted": WARN,
    "Hungry": WARN,
}

GAUGE_WIDTH = 20


def render_gauge(label: str, value: int) -> str:
    filled = round(value / 100 * GAUGE_WIDTH)

    if value >= 70:
        color = OK
    elif value >= 40:
        color = WARN
    else:
        color = BAD

    bar = "█" * filled + "░" * (GAUGE_WIDTH - filled)

    return f"{label:<9}[{color}]{bar}[/] [dim]{value:>3}%[/]"


class PetSetupScreen(ModalScreen[tuple[str, str] | None]):
    """First-run dialog to choose a name and species."""

    CSS = """
    PetSetupScreen {
        align: center middle;
        background: #100d0a;
    }

    #setup-dialog {
        width: 56;
        height: auto;
        border: round #ffb454;
        background: #1c1712;
        padding: 1 2;
    }

    #setup-dialog Input {
        margin-top: 1;
        height: 3;
        border: none;
        background: transparent;
    }

    #setup-dialog Button {
        margin-top: 1;
        width: 100%;
        background: #ffb454;
        color: #14100c;
        text-style: bold;
    }

    #setup-dialog Button:hover {
        background: #ffd866;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-dialog"):
            yield Static(f"[bold {AMBER}]FIRST LIFE INITIALIZATION[/]")
            yield Static(f"[{DIM}]Name your pet and choose its species.[/]")
            yield Input(placeholder="Pet name", id="setup-name")
            yield Input(placeholder="Pet species", id="setup-species")
            yield Button("Wake it up", id="create-pet")

    def on_mount(self) -> None:
        self.query_one("#setup-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        name = self.query_one("#setup-name", Input).value.strip()
        species = self.query_one("#setup-species", Input).value.strip()

        if not name or not species:
            self.notify("Enter both a name and a species.", severity="error")
            return

        self.dismiss((name, species))


class DaemonagotchiApp(App):
    """Presentation layer; simulation and AI live in pet.py."""

    TITLE = "DAEMONAGOTCHI"

    CSS = """
    Screen {
        background: #14100c;
        color: #e8dcc0;
    }

    #titlebar {
        dock: top;
        height: 3;
        padding: 0 2;
        background: #1c1712;
        border-bottom: solid #3d3226;
    }

    #app-title {
        width: auto;
        color: #ffb454;
        text-style: bold;
    }

    #titlebar-info {
        width: 1fr;
        text-align: right;
        color: #8a7a63;
    }

    #game {
        height: 1fr;
        width: 100%;
    }

    #left-column {
        width: 40;
        height: 100%;
        padding: 1;
    }

    #ascii-frame {
        height: 11;
        border: round #3d3226;
        background: #100d0a;
        content-align: center middle;
        text-style: bold;
    }

    .gauge {
        height: 1;
        margin-top: 1;
    }

    #status-box {
        margin-top: 1;
        padding: 0 2;
        border-left: thick #ffb454;
        background: #1c1712;
        color: #8a7a63;
    }

    #center-column {
        width: 1fr;
        height: 100%;
        padding: 1 0 1 1;
    }

    #world-panel {
        height: 42%;
        border: round #3d3226;
        background: #100d0a;
        padding: 0 2;
    }

    #world-map {
        height: 1fr;
        scrollbar-size: 0 0;
    }

    #event-log {
        height: 1fr;
        border: round #3d3226;
        background: #100d0a;
        padding: 0 2;
        color: #cccccc;
        scrollbar-size: 0 0;
    }

    #right-column {
        width: 34;
        height: 100%;
        padding: 1;
    }

    #memory-log {
        height: 1fr;
        border: round #3d3226;
        background: #100d0a;
        color: #999999;
        padding: 0 2;
        scrollbar-size: 0 0;
    }

    #controls {
        height: 10;
        margin-top: 1;
        color: #8a7a63;
    }

    #command-area {
        dock: bottom;
        height: 3;
        padding: 0 2;
        background: #1c1712;
        border-top: solid #3d3226;
    }

    #prompt {
        width: 2;
        height: 3;
        color: #ffb454;
        text-style: bold;
    }

    #cmd-input {
        width: 1fr;
        height: 3;
        border: none;
        background: transparent;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+r", "reset_game", "Reset"),
    ]

    def __init__(self):
        super().__init__()

        self.engine = None
        self.pet_agent = None
        self.env_agent = None
        self.reset_requested = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="titlebar"):
            yield Static("DAEMONAGOTCHI", id="app-title")
            yield Static("", id="titlebar-info")

        with Horizontal(id="game"):
            with Vertical(id="left-column"):
                yield Static("", id="ascii-frame")

                yield Static("", id="gauge-hunger", classes="gauge")
                yield Static("", id="gauge-energy", classes="gauge")
                yield Static("", id="gauge-happiness", classes="gauge")

                yield Static("", id="status-box")

            with Vertical(id="center-column"):
                with Vertical(id="world-panel"):
                    yield Static("", id="world-map")

                event_log = RichLog(
                    id="event-log",
                    highlight=True,
                    markup=True,
                    wrap=True,
                )
                event_log.border_title = f"[{DIM}]EVENT LOG[/]"
                yield event_log

            with Vertical(id="right-column"):
                memory_log = RichLog(
                    id="memory-log",
                    highlight=False,
                    markup=True,
                    wrap=True,
                )
                memory_log.border_title = f"[{DIM}]MEMORIES[/]"
                yield memory_log

                yield Static(
                    f"[{DIM}]COMMANDS[/]\n"
                    "  step             let it think\n"
                    "  create <thing>   grow the world\n"
                    "  status           redraw\n"
                    "  reset            new life\n"
                    "  exit             save + quit\n"
                    f"\n[{DIM}]KEYS[/]\n"
                    "  ctrl+r reset · ctrl+c quit",
                    id="controls",
                )

        with Horizontal(id="command-area"):
            yield Static("❯", id="prompt")
            yield Input(
                placeholder="enter a command...",
                id="cmd-input",
            )

    def on_mount(self) -> None:
        log = self.query_one("#event-log", RichLog)

        self.set_interval(1.0, self.update_clock)
        self.update_clock()

        api_key = os.environ.get("GROQ_API_KEY")

        if not api_key:
            log.write(
                f"[{BAD}]✖ GROQ_API_KEY is missing.[/] "
                f"[{DIM}]Export it and restart.[/]"
            )
            return

        try:
            client = instructor.from_openai(
                OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=api_key,
                ),
                mode=instructor.Mode.JSON,
            )

            self.pet_agent = PetAgent(client)
            self.env_agent = EnvironmentAgent(client)

        except Exception as exc:
            log.write(
                f"[{BAD}]✖ Failed to initialise AI:[/] {exc}"
            )
            return

        self.engine = load_game()

        if not self.engine:
            log.write(
                f"[{DIM}]▸ No save found — configure your new pet.[/]"
            )

            self.push_screen(
                PetSetupScreen(),
                self.finish_pet_setup,
            )

            return
        else:
            log.write(f"[{DIM}]▸ Save loaded.[/]")

        self.refresh_ui()

        self.query_one("#cmd-input", Input).focus()

    def update_clock(self) -> None:
        info = datetime.now().strftime("%H:%M:%S")

        if self.engine:
            location = self.engine.world.locations[
                self.engine.pet.current_location_id
            ]
            info = f"{location.name} · {info}"

        self.query_one("#titlebar-info", Static).update(info)

    def get_log(self) -> RichLog:
        return self.query_one("#event-log", RichLog)

    def finish_pet_setup(
        self,
        pet_details: tuple[str, str] | None,
    ) -> None:
        if pet_details is None:
            self.reset_requested = False
            return

        name, species = pet_details

        log = self.get_log()

        if self.reset_requested:
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)

            log.clear()
            log.write(f"[{DIM}]▸ World reset.[/]")

            self.reset_requested = False

        self.engine = create_default_world(name, species)

        log.write(
            f"[{DIM}]◌ Waking {name} the {species}...[/]"
        )

        self.run_worker(
            partial(
                self.async_initialize_pet,
                name,
                species,
            ),
            thread=True,
            name="initialize_pet",
        )

        self.refresh_ui()
        self.query_one("#cmd-input", Input).focus()

    def refresh_ui(self) -> None:
        if not self.engine:
            return

        pet = self.engine.pet

        current_location = self.engine.world.locations[
            pet.current_location_id
        ]

        frame = self.query_one("#ascii-frame", Static)

        formatted_ascii = (
            pet.ascii_art
            .replace("\\n", "\n")
            .replace('"', "")
        )

        frame.update(formatted_ascii)
        frame.border_title = f"{pet.name} the {pet.species}"
        frame.border_subtitle = pet.mood
        frame.styles.border_color = MOOD_COLORS.get(pet.mood, DIM)

        self.query_one(
            "#gauge-hunger", Static
        ).update(render_gauge("HUNGER", pet.hunger))

        self.query_one(
            "#gauge-energy", Static
        ).update(render_gauge("ENERGY", pet.energy))

        self.query_one(
            "#gauge-happiness", Static
        ).update(render_gauge("JOY", pet.happiness))

        self.query_one(
            "#status-box", Static
        ).update(
            f"NAME       {pet.name}\n"
            f"SPECIES    {pet.species}\n"
            f"LOCATION   {current_location.name}\n"
            f"MOOD       {pet.mood}\n"
            f"MEMORIES   {len(pet.memories)}"
        )

        self.refresh_world(current_location)

        memory_log = self.query_one(
            "#memory-log", RichLog
        )

        memory_log.clear()

        if not pet.memories:
            memory_log.write(f"[{DIM}]No memories yet.[/]")
        else:
            for memory in pet.memories:
                memory_log.write(f"[{DIM}]•[/] {memory}")

    def refresh_world(self, location) -> None:
        lines = [
            "",
            f"[bold {AMBER}]◈ {location.name.upper()}[/]",
            "",
            f"  {location.description}",
            "",
        ]

        if location.objects:
            lines.append(f"[{DIM}]OBJECTS[/]")

            for object_id in location.objects:
                obj = self.engine.world.objects.get(object_id)

                if obj:
                    lines.append(f"  ▸ {obj.name}")
        else:
            lines.append(f"[{DIM}]nothing here but dust[/]")

        lines.append("")

        if location.exits:
            lines.append(f"[{DIM}]EXITS[/]")

            for direction, destination in location.exits.items():
                dest = self.engine.world.locations.get(destination)

                if dest:
                    lines.append(f"  → {direction} — {dest.name}")

        self.query_one("#world-map", Static).update(
            "\n".join(lines)
        )

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:

        command = event.value.strip()

        input_box = self.query_one(
            "#cmd-input", Input
        )

        input_box.value = ""
        input_box.focus()

        if not command:
            return

        log = self.get_log()

        log.write(f"[bold]> {command}[/]")

        command_lower = command.lower()

        if command_lower == "exit":
            if self.engine:
                save_game(self.engine)

            log.write(f"[{DIM}]Saving world... goodbye.[/]")

            self.exit()
            return

        if command_lower in ("reset", "clear"):
            self.action_reset_game()
            return

        if command_lower == "step":
            if not self.pet_agent:
                log.write(f"[{BAD}]✖ Pet AI is unavailable.[/]")
                return

            log.write(f"[{DIM}]◌ The pet is thinking...[/]")

            self.run_worker(
                self.async_step_pet,
                thread=True,
                name="async_step_pet",
            )

            return

        if command_lower.startswith("create "):
            prompt = command[7:].strip()

            if not prompt:
                log.write(f"[{DIM}]Usage: create <description>[/]")
                return

            if not self.env_agent:
                log.write(f"[{BAD}]✖ Environment AI unavailable.[/]")
                return

            log.write(f"[{DIM}]◌ World agent: {prompt}[/]")

            self.run_worker(
                partial(
                    self.async_modify_world,
                    prompt,
                ),
                thread=True,
                name="modify_world",
            )

            return

        if command_lower == "status":
            self.refresh_ui()

            log.write(f"[{DIM}]▸ Interface refreshed.[/]")

            return

        if command_lower in ("help", "?"):
            log.write(
                f"[{WARN}]COMMANDS[/]\n\n"
                "  step\n"
                "      Let the pet perceive its surroundings\n"
                "      and choose an action.\n\n"
                "  create <description>\n"
                "      Ask the environment agent to change\n"
                "      the world.\n\n"
                "  status\n"
                "      Refresh the interface.\n\n"
                "  reset\n"
                "      Destroy the current save and create\n"
                "      a new world.\n\n"
                "  exit\n"
                "      Save and exit."
            )

            return

        log.write(f"[{BAD}]Unknown:[/] {command}")
        log.write(f"[{DIM}]Type 'help' for available commands.[/]")

    def async_step_pet(self):
        self.engine.tick()

        thought, result, dialogue = (
            self.pet_agent.perceive_and_act(
                self.engine
            )
        )

        save_game(self.engine)

        return thought, result, dialogue

    def async_initialize_pet(
        self,
        name: str,
        species: str,
    ) -> str:
        ascii_art = self.pet_agent.generate_initial_ascii(
            name,
            species,
        )

        if ascii_art:
            self.engine.pet.ascii_art = ascii_art

        save_game(self.engine)
        return ascii_art

    def async_modify_world(
        self,
        prompt: str,
    ) -> str:

        result = self.env_agent.modify_world(
            prompt,
            self.engine,
        )

        save_game(self.engine)

        return result

    def on_worker_state_changed(
        self,
        event: Worker.StateChanged,
    ) -> None:

        log = self.get_log()

        if (
            event.state == WorkerState.SUCCESS
            and event.worker.name == "async_step_pet"
        ):
            thought, result, dialogue = (
                event.worker.result
            )

            pet_name = self.engine.pet.name

            log.write(f"[{WARN}]✦[/] {thought}")

            if dialogue:
                log.write(
                    f"[{OK}]❝ {dialogue}[/] "
                    f"[{DIM}]— {pet_name}[/]"
                )

            log.write(f"[{DIM}]{result}[/]")

            self.refresh_ui()

        elif (
            event.state == WorkerState.SUCCESS
            and event.worker.name == "modify_world"
        ):
            result = event.worker.result

            log.write(f"[{AMBER}]◆[/] {result}")

            self.refresh_ui()

        elif (
            event.state == WorkerState.SUCCESS
            and event.worker.name == "initialize_pet"
        ):
            log.write(
                f"[{OK}]✦ Your pet has awakened.[/]"
            )
            self.refresh_ui()

        elif event.state == WorkerState.ERROR:
            log.write(
                f"[{BAD}]✖ worker failed:[/] "
                f"{event.worker.error}"
            )

    def action_reset_game(self) -> None:
        log = self.get_log()

        self.reset_requested = True
        log.clear()
        log.write(f"[{DIM}]▸ Choose your new pet.[/]")

        self.push_screen(
            PetSetupScreen(),
            self.finish_pet_setup,
        )


if __name__ == "__main__":
    app = DaemonagotchiApp()
    app.run()
