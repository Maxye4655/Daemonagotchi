import os
from functools import partial

import instructor
from openai import OpenAI

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    ProgressBar,
    RichLog,
    Static,
)
from textual.worker import Worker, WorkerState

from pet import (
    load_game,
    create_default_world,
    save_game,
    PetAgent,
    EnvironmentAgent,
    SAVE_FILE,
)


class PetSetupScreen(ModalScreen[tuple[str, str] | None]):
    """Collect the pet identity during the first launch."""

    CSS = """
    PetSetupScreen {
        align: center middle;
    }

    #setup-dialog {
        width: 52;
        height: auto;
        border: double #ffffff;
        background: #000000;
        padding: 2;
    }

    #setup-dialog Input {
        margin-top: 1;
    }

    #setup-dialog Button {
        margin-top: 1;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-dialog"):
            yield Static("FIRST LIFE INITIALIZATION", classes="section-title")
            yield Static("Choose a name and species for your pet.")
            yield Input(placeholder="Pet name", id="setup-name")
            yield Input(placeholder="Pet species", id="setup-species")
            yield Button("Create pet", variant="primary", id="create-pet")

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
    """
    Main Textual interface for Daemonagotchi.

    The simulation and AI logic live in pet.py.
    This file is responsible only for presentation and input.
    """

    TITLE = "DAEMONAGOTCHI"
    SUB_TITLE = "A DIGITAL LIFE SIMULATION"

    CSS = """
    /* ============================================================
       GLOBAL
       ============================================================ */

    Screen {
        background: #000000;
        color: #ffffff;
    }

    #game,
    #left-column,
    #center-column,
    #right-column,
    #world-view,
    #event-log,
    #memory-log {
        scrollbar-size: 0 0;
    }

    Header {
        background: #000000;
        color: #ffffff;
        height: 1;
    }

    Footer {
        background: #000000;
        color: #aaaaaa;
    }

    /* ============================================================
       MAIN LAYOUT
       ============================================================ */

    #game {
        height: 1fr;
        width: 100%;
    }

    #left-column {
        width: 32%;
        height: 100%;
        border: solid #666666;
        padding: 1;
    }

    #center-column {
        width: 43%;
        height: 100%;
        border-top: solid #666666;
        border-bottom: solid #666666;
        padding: 1;
    }

    #right-column {
        width: 25%;
        height: 100%;
        border: solid #666666;
        padding: 1;
    }

    /* ============================================================
       SECTION HEADERS
       ============================================================ */

    .section-title {
        width: 100%;
        height: 1;
        color: #ffffff;
        text-style: bold;
        background: #222222;
        padding-left: 1;
        margin-bottom: 1;
    }

    .subtle {
        color: #888888;
    }

    /* ============================================================
       PET VIEW
       ============================================================ */

    #ascii-frame {
        height: 12;
        width: 100%;
        border: double #ffffff;
        background: #000000;
        color: #ffffff;
        content-align: center middle;
        margin-bottom: 1;
    }

    #pet-name {
        height: 1;
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #ffffff;
    }

    #pet-description {
        height: 2;
        width: 100%;
        text-align: center;
        color: #999999;
        margin-bottom: 1;
    }

    /* ============================================================
       STATS
       ============================================================ */

    .stat-name {
        height: 1;
        color: #bbbbbb;
        margin-top: 1;
    }

    ProgressBar {
        height: 1;
        width: 100%;
        color: #ffffff;
        background: #222222;
    }

    ProgressBar > .bar--complete {
        color: #ffffff;
        background: #ffffff;
    }

    ProgressBar > .bar--indeterminate {
        color: #ffffff;
        background: #ffffff;
    }

    /* ============================================================
       WORLD VIEW
       ============================================================ */

    #world-view {
        height: 1fr;
        width: 100%;
        border: solid #444444;
        background: #000000;
        padding: 1;
    }

    #world-map {
        height: 1fr;
        width: 100%;
        color: #ffffff;
    }

    #location-info {
        height: 7;
        width: 100%;
        border-top: solid #333333;
        margin-top: 1;
        padding-top: 1;
        color: #aaaaaa;
    }

    /* ============================================================
       EVENT LOG
       ============================================================ */

    #event-title {
        height: 1;
        width: 100%;
        background: #222222;
        color: #ffffff;
        text-style: bold;
        padding-left: 1;
    }

    #event-log {
        height: 1fr;
        border: solid #444444;
        background: #000000;
        padding: 1;
        color: #cccccc;
    }

    /* ============================================================
       MEMORY LOG
       ============================================================ */

    #memory-title {
        height: 1;
        width: 100%;
        background: #222222;
        color: #ffffff;
        text-style: bold;
        padding-left: 1;
        margin-bottom: 1;
    }

    #memory-log {
        height: 1fr;
        border: solid #444444;
        background: #000000;
        color: #999999;
        padding: 1;
    }

    /* ============================================================
       COMMAND CONSOLE
       ============================================================ */

    #command-area {
        height: 5;
        width: 100%;
        border: solid #ffffff;
        background: #000000;
        padding: 1;
    }

    #command-prompt {
        width: 3;
        height: 3;
        content-align: center middle;
        color: #ffffff;
        text-style: bold;
    }

    #cmd-input {
        width: 1fr;
        height: 3;
        border: none;
        background: #000000;
        color: #ffffff;
    }

    #cmd-input:focus {
        border: none;
    }

    /* ============================================================
       STATUS INFORMATION
       ============================================================ */

    #status-box {
        height: 8;
        width: 100%;
        border: solid #444444;
        padding: 1;
        margin-top: 1;
    }

    #controls {
        height: 5;
        width: 100%;
        border: solid #444444;
        padding: 1;
        margin-top: 1;
        color: #777777;
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

    # ============================================================
    # UI COMPOSITION
    # ============================================================

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="game"):

            # ----------------------------------------------------
            # LEFT: PET
            # ----------------------------------------------------

            with Vertical(id="left-column"):
                yield Static(" PET ", classes="section-title")

                yield Static("", id="ascii-frame")

                yield Static("UNKNOWN", id="pet-name")

                yield Static(
                    "Waiting for simulation...",
                    id="pet-description",
                )

                yield Static("HUNGER", classes="stat-name")
                yield ProgressBar(
                    total=100,
                    show_percentage=True,
                    id="hunger-bar",
                )

                yield Static("ENERGY", classes="stat-name")
                yield ProgressBar(
                    total=100,
                    show_percentage=True,
                    id="energy-bar",
                )

                yield Static("HAPPINESS", classes="stat-name")
                yield ProgressBar(
                    total=100,
                    show_percentage=True,
                    id="happiness-bar",
                )

                with Vertical(id="status-box"):
                    yield Static("", id="pet-status")

            # ----------------------------------------------------
            # CENTER: WORLD + EVENTS
            # ----------------------------------------------------

            with Vertical(id="center-column"):
                yield Static(" WORLD ", classes="section-title")

                with Vertical(id="world-view"):
                    yield Static("", id="world-map")
                    yield Static("", id="location-info")

                yield Static(" EVENT LOG ", id="event-title")
                yield RichLog(
                    id="event-log",
                    highlight=True,
                    markup=True,
                    wrap=True,
                )

            # ----------------------------------------------------
            # RIGHT: MEMORIES
            # ----------------------------------------------------

            with Vertical(id="right-column"):
                yield Static(" MEMORIES ", id="memory-title")

                yield RichLog(
                    id="memory-log",
                    highlight=False,
                    markup=True,
                    wrap=True,
                )

                yield Static(
                    """
CONTROLS
────────────────
step
create <thing>
status
reset
exit

CTRL+C   Quit
CTRL+R   Reset
""",
                    id="controls",
                )

        # --------------------------------------------------------
        # COMMAND LINE
        # --------------------------------------------------------

        with Horizontal(id="command-area"):
            yield Static("> ", id="command-prompt")
            yield Input(
                placeholder="Enter command...",
                id="cmd-input",
            )

        yield Footer()

    # ============================================================
    # STARTUP
    # ============================================================

    def on_mount(self) -> None:
        event_log = self.query_one("#event-log", RichLog)

        api_key = os.environ.get("GROQ_API_KEY")

        if not api_key:
            event_log.write(
                "[bold]ERROR[/bold]  GROQ_API_KEY is missing."
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
            event_log.write(
                f"[bold]ERROR[/bold]  Failed to initialise AI: {exc}"
            )
            return

        self.engine = load_game()

        if not self.engine:
            event_log.write(
                "[bold]SYSTEM[/bold]  Configure your new pet."
            )

            self.push_screen(
                PetSetupScreen(),
                self.finish_pet_setup,
            )

            return
        else:
            event_log.write(
                "[bold]SYSTEM[/bold]  Save loaded."
            )

        self.refresh_ui()

        self.query_one("#cmd-input", Input).focus()

    def finish_pet_setup(
        self,
        pet_details: tuple[str, str] | None,
    ) -> None:
        if pet_details is None:
            self.reset_requested = False
            return

        name, species = pet_details

        log = self.query_one("#event-log", RichLog)

        if self.reset_requested:
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)

            log.clear()
            log.write(
                "[bold]SYSTEM[/bold]  World reset."
            )

            self.reset_requested = False

        self.engine = create_default_world(name, species)

        log.write(
            f"[bold]SYSTEM[/bold]  Creating {name}, the {species}..."
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

    # ============================================================
    # UI REFRESH
    # ============================================================

    def refresh_ui(self) -> None:
        if not self.engine:
            return

        pet = self.engine.pet

        current_location = self.engine.world.locations[
            pet.current_location_id
        ]

        # --------------------------------------------------------
        # ASCII ART
        # --------------------------------------------------------

        formatted_ascii = (
            pet.ascii_art
            .replace("\\n", "\n")
            .replace('"', "")
        )

        self.query_one(
            "#ascii-frame",
            Static,
        ).update(formatted_ascii)

        # --------------------------------------------------------
        # PET INFORMATION
        # --------------------------------------------------------

        self.query_one(
            "#pet-name",
            Static,
        ).update(
            f"{pet.name.upper()}  //  {pet.species.upper()}"
        )

        self.query_one(
            "#pet-description",
            Static,
        ).update(
            f"Location: {current_location.name}\n"
            f"Mood: {pet.mood}"
        )

        # --------------------------------------------------------
        # STATS
        # --------------------------------------------------------

        self.query_one(
            "#hunger-bar",
            ProgressBar,
        ).progress = pet.hunger

        self.query_one(
            "#energy-bar",
            ProgressBar,
        ).progress = pet.energy

        self.query_one(
            "#happiness-bar",
            ProgressBar,
        ).progress = pet.happiness

        # --------------------------------------------------------
        # STATUS
        # --------------------------------------------------------

        self.query_one(
            "#pet-status",
            Static,
        ).update(
            f"NAME       {pet.name}\n"
            f"SPECIES    {pet.species}\n"
            f"LOCATION   {current_location.name}\n"
            f"MOOD       {pet.mood}\n"
            f"MEMORIES   {len(pet.memories)}"
        )

        # --------------------------------------------------------
        # WORLD
        # --------------------------------------------------------

        self.refresh_world(current_location)

        # --------------------------------------------------------
        # MEMORIES
        # --------------------------------------------------------

        memory_log = self.query_one(
            "#memory-log",
            RichLog,
        )

        memory_log.clear()

        if not pet.memories:
            memory_log.write(
                "[dim]No memories yet.[/dim]"
            )
        else:
            for memory in pet.memories:
                memory_log.write(
                    f"[dim]•[/dim] {memory}"
                )

    # ============================================================
    # WORLD DISPLAY
    # ============================================================

    def refresh_world(self, location) -> None:
        world_map = self.query_one(
            "#world-map",
            Static,
        )

        location_info = self.query_one(
            "#location-info",
            Static,
        )

        # Current location
        world_text = [
            "",
            f"        [bold][ {location.name.upper()} ][/bold]",
            "",
            f"        {location.description}",
            "",
        ]

        # Objects
        if location.objects:
            world_text.append("        OBJECTS")
            world_text.append("        ───────")

            for object_id in location.objects:
                obj = self.engine.world.objects.get(object_id)

                if obj:
                    world_text.append(
                        f"        [ ] {obj.name}"
                    )

        else:
            world_text.append(
                "        [dim]The area is empty.[/dim]"
            )

        world_text.append("")

        # Exits
        if location.exits:
            world_text.append("        EXITS")
            world_text.append("        ─────")

            for direction, destination in location.exits.items():
                destination_location = (
                    self.engine.world.locations.get(destination)
                )

                if destination_location:
                    world_text.append(
                        f"        -> {direction.upper():<7} "
                        f"{destination_location.name}"
                    )

        world_map.update("\n".join(world_text))

        # Location information
        location_info.update(
            f"CURRENT LOCATION\n"
            f"{location.name}\n\n"
            f"{location.description}"
        )

    # ============================================================
    # COMMAND INPUT
    # ============================================================

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:

        command = event.value.strip()

        input_box = self.query_one(
            "#cmd-input",
            Input,
        )

        input_box.value = ""
        input_box.focus()

        if not command:
            return

        log = self.query_one(
            "#event-log",
            RichLog,
        )

        # Show user's command
        log.write(
            f"[bold]> {command}[/bold]"
        )

        command_lower = command.lower()

        # --------------------------------------------------------
        # EXIT
        # --------------------------------------------------------

        if command_lower == "exit":
            if self.engine:
                save_game(self.engine)

            log.write(
                "[dim]Saving world... goodbye.[/dim]"
            )

            self.exit()
            return

        # --------------------------------------------------------
        # RESET
        # --------------------------------------------------------

        if command_lower in ("reset", "clear"):
            self.action_reset_game()
            return

        # --------------------------------------------------------
        # STEP
        # --------------------------------------------------------

        if command_lower == "step":
            if not self.pet_agent:
                log.write(
                    "[bold]ERROR[/bold]  Pet AI is unavailable."
                )
                return

            log.write(
                "[dim]The pet is thinking...[/dim]"
            )

            self.run_worker(
                self.async_step_pet,
                thread=True,
                name="async_step_pet",
            )

            return

        # --------------------------------------------------------
        # CREATE
        # --------------------------------------------------------

        if command_lower.startswith("create "):
            prompt = command[7:].strip()

            if not prompt:
                log.write(
                    "[dim]Usage: create <description>[/dim]"
                )
                return

            if not self.env_agent:
                log.write(
                    "[bold]ERROR[/bold]  Environment AI unavailable."
                )
                return

            log.write(
                f"[dim]World agent: {prompt}[/dim]"
            )

            self.run_worker(
                partial(
                    self.async_modify_world,
                    prompt,
                ),
                thread=True,
                name="modify_world",
            )

            return

        # --------------------------------------------------------
        # STATUS
        # --------------------------------------------------------

        if command_lower == "status":
            self.refresh_ui()

            log.write(
                "[dim]Interface refreshed.[/dim]"
            )

            return

        # --------------------------------------------------------
        # HELP
        # --------------------------------------------------------

        if command_lower in ("help", "?"):
            log.write(
                """
[bold]COMMANDS[/bold]

  step
      Let the pet perceive its surroundings
      and choose an action.

  create <description>
      Ask the environment agent to change
      the world.

  status
      Refresh the interface.

  reset
      Destroy the current save and create
      a new world.

  exit
      Save and exit.
"""
            )

            return

        # --------------------------------------------------------
        # UNKNOWN COMMAND
        # --------------------------------------------------------

        log.write(
            f"[bold]Unknown command:[/bold] {command}"
        )

        log.write(
            "[dim]Type 'help' for available commands.[/dim]"
        )

    # ============================================================
    # PET WORKER
    # ============================================================

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

    # ============================================================
    # ENVIRONMENT WORKER
    # ============================================================

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

    # ============================================================
    # WORKER EVENTS
    # ============================================================

    def on_worker_state_changed(
        self,
        event: Worker.StateChanged,
    ) -> None:

        log = self.query_one(
            "#event-log",
            RichLog,
        )

        # --------------------------------------------------------
        # PET FINISHED
        # --------------------------------------------------------

        if (
            event.state == WorkerState.SUCCESS
            and event.worker.name == "async_step_pet"
        ):
            thought, result, dialogue = (
                event.worker.result
            )

            pet_name = self.engine.pet.name

            log.write(
                f"[bold]THOUGHT[/bold]  {thought}"
            )

            if dialogue:
                log.write(
                    f"[bold]{pet_name}:[/bold] "
                    f"\"{dialogue}\""
                )

            log.write(
                f"[dim]{result}[/dim]"
            )

            self.refresh_ui()

        # --------------------------------------------------------
        # ENVIRONMENT FINISHED
        # --------------------------------------------------------

        elif (
            event.state == WorkerState.SUCCESS
            and event.worker.name == "modify_world"
        ):
            result = event.worker.result

            log.write(
                f"[bold]WORLD[/bold]  {result}"
            )

            self.refresh_ui()

        # --------------------------------------------------------
        # INITIAL PET FINISHED
        # --------------------------------------------------------

        elif (
            event.state == WorkerState.SUCCESS
            and event.worker.name == "initialize_pet"
        ):
            log.write(
                "[bold]SYSTEM[/bold]  Your pet has awakened."
            )
            self.refresh_ui()

        # --------------------------------------------------------
        # WORKER FAILED
        # --------------------------------------------------------

        elif event.state == WorkerState.ERROR:
            log.write(
                f"[bold]WORKER ERROR[/bold]  "
                f"{event.worker.error}"
            )

    # ============================================================
    # RESET
    # ============================================================

    def action_reset_game(self) -> None:
        log = self.query_one(
            "#event-log",
            RichLog,
        )

        self.reset_requested = True
        log.clear()
        log.write(
            "[bold]SYSTEM[/bold]  Choose your new pet."
        )

        self.push_screen(
            PetSetupScreen(),
            self.finish_pet_setup,
        )


if __name__ == "__main__":
    app = DaemonagotchiApp()
    app.run()