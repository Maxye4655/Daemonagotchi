# TUI interface, uses pet.py for backend logic. Run this instead of pet.py from now onwards.

import os
import sys
import instructor
from openai import OpenAI

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, RichLog, Input, Button
from textual.worker import Worker, WorkerState


from pet import (
    load_game,
    create_default_world,
    save_game,
    PetAgent,
    EnvironmentAgent,
    SAVE_FILE
)

class DaemonagotchiApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #main-container {
        height: 1fr;
    }

    #left-panel {
        width: 38%;
        border: solid green;
        padding: 1;
    }

    #ascii-view {
        height: 7;
        content-align: center middle;
        border: double green;
        color: $accent;
        margin-bottom: 1;
    }

    #right-panel {
        width: 62%;
        border: solid blue;
        padding: 0;
    }

    #input-container {
        height: auto;
        border: solid yellow;
        padding: 0 1;
    }

    .stat-label {
        margin-top: 1;
        text-style: bold;
    }

    ProgressBar {
        height: 1;
    }

    #log-view {
        height: 1fr;
    }

    #memory-log {
        height: 8;
        border: ascii grey;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+r", "reset_game", "Reset Game"),
    ]

    def __init__(self):
        super().__init__()
        self.engine = None
        self.pet_agent = None
        self.env_agent = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                # ASCII Art Display Panel
                yield Static("", id="ascii-view")
                
                yield Static("PET STATUS", id="pet-title", classes="stat-label")
                yield Static("Name: -- | Species: --", id="pet-info")
                yield Static("Location: --", id="pet-location")
                yield Static("Mood: --", id="pet-mood")
                
                yield Static("Hunger", classes="stat-label")
                yield ProgressBar(id="hunger-bar", total=100, show_percentage=True)
                
                yield Static("Energy", classes="stat-label")
                yield ProgressBar(id="energy-bar", total=100, show_percentage=True)
                
                yield Static("Happiness", classes="stat-label")
                yield ProgressBar(id="happiness-bar", total=100, show_percentage=True)
                
                yield Static("Memories", classes="stat-label")
                yield RichLog(id="memory-log")

            with Vertical(id="right-panel"):
                yield RichLog(id="log-view", highlight=True, markup=True)

        with Horizontal(id="input-container"):
            yield Input(placeholder="Commands: 'step', 'create <area>', 'reset', 'status', 'exit'", id="cmd-input")

        yield Footer()

    def on_mount(self) -> None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            self.query_one("#log-view", RichLog).write("[bold red]Error: GROQ_API_KEY is missing![/bold red]")
            return

        client = instructor.from_openai(
            OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key),
            mode=instructor.Mode.JSON,
        )

        self.pet_agent = PetAgent(client)
        self.env_agent = EnvironmentAgent(client)

        self.engine = load_game()
        if not self.engine:
            self.engine = create_default_world("Blob", "Digital Slime")
            self.query_one("#log-view", RichLog).write("[cyan]Created new default pet world.[/cyan]")

        self.refresh_ui()
        self.query_one("#cmd-input", Input).focus()

    def refresh_ui(self) -> None:
        if not self.engine:
            return

        pet = self.engine.pet
        loc_name = self.engine.world.locations[pet.current_location_id].name

        # 1. Render dynamic ASCII Art from the Pet instance
        self.query_one("#ascii-view", Static).update(pet.ascii_art)

        # 2. Render Text Stats
        self.query_one("#pet-title", Static).update(f"[bold]{pet.name.upper()}'S DASHBOARD[/bold]")
        self.query_one("#pet-info", Static).update(f"Species: {pet.species}")
        self.query_one("#pet-location", Static).update(f"Location: {loc_name}")
        self.query_one("#pet-mood", Static).update(f"Mood: {pet.mood}")

        # 3. Update Progress Bars
        self.query_one("#hunger-bar", ProgressBar).progress = pet.hunger
        self.query_one("#energy-bar", ProgressBar).progress = pet.energy
        self.query_one("#happiness-bar", ProgressBar).progress = pet.happiness

        # 4. Update Memory Log
        mem_log = self.query_one("#memory-log", RichLog)
        mem_log.clear()
        for mem in pet.memories:
            mem_log.write(f"- {mem}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        cmd_input = self.query_one("#cmd-input", Input)
        cmd_input.value = ""
        cmd_input.focus() 
        
        if not command:
            return

        log = self.query_one("#log-view", RichLog)

        if command.lower() == "exit":
            save_game(self.engine)
            self.exit()

        elif command.lower() in ("reset", "clear"):
            self.action_reset_game()

        elif command.lower() == "step":
            log.write("[yellow]Thinking... Calling LLM Agent...[/yellow]")
            self.run_worker(self.async_step_pet, thread=True)

        elif command.lower().startswith("create "):
            prompt = command[7:]
            log.write(f"[yellow]Modifying world: {prompt}...[/yellow]")
            self.run_worker(lambda: self.env_agent.modify_world(prompt, self.engine), thread=True)

        elif command.lower() == "status":
            self.refresh_ui()
            log.write("[green]UI refreshed.[/green]")

        else:
            log.write(f"[red]Unknown command:[/red] {command}")

    def async_step_pet(self) -> tuple[str, str, str]:
        self.engine.tick()
        thought, result, dialogue = self.pet_agent.perceive_and_act(self.engine)
        save_game(self.engine)
        return thought, result, dialogue

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS and event.worker.name == "async_step_pet":
            thought, result, dialogue = event.worker.result
            log = self.query_one("#log-view", RichLog)
            pet_name = self.engine.pet.name

            log.write(f"[bold blue][{pet_name}'s Thought]:[/bold blue] {thought}")
            if dialogue:
                log.write(f"[bold green]{pet_name}:[/bold green] \"{dialogue}\"")
            log.write(f"[dim]{result}[/dim]\n")

            # Update the screen (including ASCII frame) upon turn completion
            self.refresh_ui()

    def action_reset_game(self) -> None:
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
        self.engine = create_default_world("NewBlob", "Digital Slime")
        self.refresh_ui()
        log = self.query_one("#log-view", RichLog)
        log.clear()
        log.write("[bold red]Save wiped. Started new game with default pet.[/bold red]")

if __name__ == "__main__":
    app = DaemonagotchiApp()
    app.run()