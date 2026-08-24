# This file contains the game logic for Daemonagotchi.
# tui.py provides the terminal interface.

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
import json
import os

import instructor
from pydantic import BaseModel, Field


MODEL_NAME = "openai/gpt-oss-20b"
SAVE_FILE = "pet_save.json"


# ============================================================
# WORLD
# ============================================================

@dataclass
class WorldObject:
    id: str
    name: str
    description: str
    location_id: str
    available_actions: List[str]


@dataclass
class Location:
    id: str
    name: str
    description: str
    exits: Dict[str, str] = field(default_factory=dict)
    objects: List[str] = field(default_factory=list)


class WorldMap:
    def __init__(self):
        self.locations: Dict[str, Location] = {}
        self.objects: Dict[str, WorldObject] = {}

    def add_location(self, loc: Location):
        self.locations[loc.id] = loc

    def add_object(self, obj: WorldObject):
        self.objects[obj.id] = obj

        if obj.location_id in self.locations:
            if obj.id not in self.locations[obj.location_id].objects:
                self.locations[obj.location_id].objects.append(obj.id)

    def connect_locations(
        self,
        loc1_id: str,
        direction: str,
        loc2_id: str,
        opposite_direction: Optional[str] = None,
    ):
        if loc1_id not in self.locations:
            return

        if loc2_id not in self.locations:
            return

        self.locations[loc1_id].exits[direction] = loc2_id

        if opposite_direction:
            self.locations[loc2_id].exits[opposite_direction] = loc1_id


# ============================================================
# PET
# ============================================================

@dataclass
class Pet:
    name: str
    species: str
    current_location_id: str

    hunger: int = 75
    happiness: int = 50
    energy: int = 50

    mood: str = "Hungry"

    ascii_art: str = r"""
 /\_/\
( o.o )
/> ^ <
"""

    memories: List[str] = field(default_factory=list)

    def add_memory(self, event_description: str):
        self.memories.append(event_description)

        # Keep the most recent 15 memories.
        if len(self.memories) > 15:
            self.memories.pop(0)

    def clamp_stats(self):
        self.hunger = max(0, min(100, self.hunger))
        self.happiness = max(0, min(100, self.happiness))
        self.energy = max(0, min(100, self.energy))

    def update_mood(self):
        if self.hunger > 80:
            self.mood = "Starving"

        elif self.hunger > 65:
            self.mood = "Hungry"

        elif self.energy < 20:
            self.mood = "Exhausted"

        elif self.happiness > 80:
            self.mood = "Joyful"

        elif self.happiness < 20:
            self.mood = "Lonely"

        else:
            self.mood = "Content"


# ============================================================
# SIMULATION ENGINE
# ============================================================

class SimulationEngine:
    def __init__(self, pet: Pet, world: WorldMap):
        self.pet = pet
        self.world = world

    def tick(self) -> str:
        self.pet.hunger += 3
        self.pet.happiness -= 1
        self.pet.energy -= 1

        self.pet.clamp_stats()
        self.pet.update_mood()

        return "Time passed. Vitals naturally decayed."

    def move(self, direction: str) -> str:
        direction = direction.lower()

        current_loc = self.world.locations[
            self.pet.current_location_id
        ]

        if direction not in current_loc.exits:
            available = ", ".join(current_loc.exits.keys())

            if not available:
                available = "none"

            return (
                f"Cannot go {direction}. "
                f"Available exits: {available}"
            )

        new_loc_id = current_loc.exits[direction]

        if new_loc_id not in self.world.locations:
            return f"Destination '{new_loc_id}' does not exist."

        self.pet.current_location_id = new_loc_id

        self.pet.energy -= 5

        self.pet.clamp_stats()
        self.pet.update_mood()

        new_loc = self.world.locations[new_loc_id]

        result = (
            f"{self.pet.name} walked "
            f"{direction} to {new_loc.name}."
        )

        self.pet.add_memory(
            f"Moved {direction} into {new_loc.name}."
        )

        return result

    def interact_with_object(
        self,
        object_id: str,
        action: str,
    ) -> str:

        current_loc = self.world.locations[
            self.pet.current_location_id
        ]

        if object_id not in current_loc.objects:
            return (
                f"Object '{object_id}' "
                f"is not in this room."
            )

        if object_id not in self.world.objects:
            return f"Object '{object_id}' does not exist."

        obj = self.world.objects[object_id]

        if action not in obj.available_actions:
            return (
                f"Action '{action}' is invalid "
                f"for {obj.name}."
            )

        # --------------------------------------------------------
        # FOOD
        # --------------------------------------------------------

        if action == "eat" and object_id == "food_bowl":
            self.pet.hunger -= 35
            self.pet.happiness += 10

            self.pet.clamp_stats()
            self.pet.update_mood()

            result = (
                f"{self.pet.name} ate food from the bowl. "
                f"Hunger satisfied!"
            )

            self.pet.add_memory(
                f"Ate food from the bowl in "
                f"{current_loc.name}."
            )

            return result

        # --------------------------------------------------------
        # BED
        # --------------------------------------------------------

        if action == "sleep" and object_id == "bed":
            self.pet.energy += 40

            self.pet.clamp_stats()
            self.pet.update_mood()

            result = (
                f"{self.pet.name} rested in the comfy bed."
            )

            self.pet.add_memory(
                f"Took a nap in the bed in "
                f"{current_loc.name}."
            )

            return result

        # --------------------------------------------------------
        # GENERIC OBJECT
        # --------------------------------------------------------

        result = (
            f"{self.pet.name} used "
            f"{obj.name} ({action})."
        )

        self.pet.add_memory(
            f"Interacted with {obj.name} ({action})."
        )

        return result

    def get_pet_context(self) -> str:
        pet = self.pet

        loc = self.world.locations[
            pet.current_location_id
        ]

        # --------------------------------------------------------
        # OBJECTS
        # --------------------------------------------------------

        objects_list = []

        for obj_id in loc.objects:
            if obj_id in self.world.objects:
                obj = self.world.objects[obj_id]

                objects_list.append(
                    f"{obj.id}: "
                    f"{obj.name} "
                    f"(actions: {', '.join(obj.available_actions)})"
                )

        objects_str = (
            "\n".join(objects_list)
            if objects_list
            else "None"
        )

        # --------------------------------------------------------
        # EXITS
        # --------------------------------------------------------

        exits_str = (
            ", ".join(loc.exits.keys())
            if loc.exits
            else "None"
        )

        # --------------------------------------------------------
        # MEMORIES
        # --------------------------------------------------------

        memories_str = (
            "\n".join(
                f"- {memory}"
                for memory in pet.memories[-5:]
            )
            if pet.memories
            else "None"
        )

        return (
            f"PET\n"
            f"Name: {pet.name}\n"
            f"Species: {pet.species}\n\n"

            f"VITALS\n"
            f"Hunger: {pet.hunger}/100\n"
            f"Energy: {pet.energy}/100\n"
            f"Happiness: {pet.happiness}/100\n"
            f"Mood: {pet.mood}\n\n"

            f"LOCATION\n"
            f"{loc.name}\n"
            f"{loc.description}\n\n"

            f"VISIBLE OBJECTS\n"
            f"{objects_str}\n\n"

            f"AVAILABLE EXITS\n"
            f"{exits_str}\n\n"

            f"RECENT MEMORIES\n"
            f"{memories_str}"
        )

    def spawn_location(
        self,
        loc_id: str,
        name: str,
        description: str,
        connect_to_id: str,
        direction: str,
    ) -> str:

        if connect_to_id not in self.world.locations:
            return (
                f"Target location "
                f"'{connect_to_id}' does not exist."
            )

        # Prevent accidental duplicate IDs.
        if loc_id in self.world.locations:
            return (
                f"A location with ID "
                f"'{loc_id}' already exists."
            )

        direction = direction.lower()

        if direction not in {
            "north",
            "south",
            "east",
            "west",
        }:
            return f"Invalid direction: {direction}"

        new_loc = Location(
            id=loc_id,
            name=name,
            description=description,
        )

        self.world.add_location(new_loc)

        opposites = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east",
        }

        opposite = opposites[direction]

        self.world.connect_locations(
            connect_to_id,
            direction,
            loc_id,
            opposite,
        )

        result = (
            f"World updated: Created "
            f"'{name}' to the {direction} "
            f"of {connect_to_id}."
        )

        self.pet.add_memory(
            f"Noticed a new area opened "
            f"to the {direction}: {name}."
        )

        return result


# ============================================================
# AI RESPONSE MODELS
# ============================================================

class PetDecision(BaseModel):
    """
    A deliberately flat schema.

    This is much easier for Groq's structured-output system
    to validate than a nested Union of multiple Pydantic models.
    """

    internal_thought: str = Field(
        description=(
            "Short reasoning about the pet's needs, "
            "environment and decision."
        )
    )

    dialogue: Optional[str] = Field(
        default=None,
        description=(
            "Optional sentence spoken by the pet."
        )
    )

    ascii_art: str = Field(
        description=(
            "A 3 to 7 line ASCII drawing of the pet. "
            "Keep it under 25 characters wide."
        )
    )

    action_type: Literal[
        "move",
        "interact",
        "wait",
    ] = Field(
        description=(
            "The type of action the pet will perform."
        )
    )

    direction: Optional[
        Literal[
            "north",
            "south",
            "east",
            "west",
        ]
    ] = Field(
        default=None,
        description=(
            "Direction for a move action. "
            "Null for other actions."
        )
    )

    object_id: Optional[str] = Field(
        default=None,
        description=(
            "Object ID for an interact action. "
            "Null for other actions."
        )
    )

    object_action: Optional[str] = Field(
        default=None,
        description=(
            "Action to perform on the object. "
            "For example: eat or sleep."
        )
    )

    wait_reason: Optional[str] = Field(
        default=None,
        description=(
            "Reason for waiting. "
            "Null when the pet performs another action."
        )
    )


class SpawnLocationAction(BaseModel):
    """
    Structured command generated by the environment agent.
    """

    loc_id: str = Field(
        description=(
            "Unique lowercase ID for the new location. "
            "Use underscores instead of spaces."
        )
    )

    name: str = Field(
        description="Human-readable location name."
    )

    description: str = Field(
        description="Short description of the location."
    )

    direction: Literal[
        "north",
        "south",
        "east",
        "west",
    ] = Field(
        description=(
            "Direction from the pet's current location."
        )
    )


# ============================================================
# PET AGENT
# ============================================================

class PetAgent:

    def __init__(self, client: instructor.Instructor):
        self.client = client

    def generate_initial_ascii(
        self,
        name: str,
        species: str,
    ) -> str:
        response: PetDecision = (
            self.client.chat.completions.create(
                model=MODEL_NAME,
                response_model=PetDecision,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are initializing a new virtual pet. "
                            "Return a complete valid pet decision. "
                            "The pet must wait because it has not "
                            "entered the world yet. Set action_type "
                            "to wait, direction, object_id and "
                            "object_action to null, and provide a "
                            "simple friendly ASCII portrait. Keep "
                            "the art under 25 characters wide. Do "
                            "not use markdown fences or quotation "
                            "marks inside the art."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Initialize {name}, a {species}. "
                            "Use action_type wait and create the "
                            "first ASCII portrait."
                        ),
                    },
                ],
                max_retries=2,
                temperature=0.7,
            )
        )

        return response.ascii_art.strip()

    def perceive_and_act(
        self,
        engine: SimulationEngine,
    ) -> tuple[str, str, str]:

        state_desc = engine.get_pet_context()

        system_prompt = f"""
You are the brain of {engine.pet.name}.

You are a living autonomous digital {engine.pet.species}
inside a persistent simulated world.

Your personality should emerge from your species, mood,
memories, needs and experiences.

You must choose exactly ONE action.

AVAILABLE ACTIONS:

MOVE
Use this when the pet wants to travel somewhere.

INTERACT
Use this when the pet wants to interact with an object
currently visible in the room.

WAIT
Use this when the pet has no useful action to perform.

IMPORTANT:

- Never invent objects.
- Never invent exits.
- Only move through available exits.
- Only interact with visible objects.
- If hungry, prioritize finding food.
- If exhausted, prioritize resting.
- If happy and safe, exploration is encouraged.
- Keep internal_thought reasonably short.
- Dialogue should sound like the pet.
- ASCII art must be simple terminal ASCII.
- Do not use markdown fences in ascii_art.
- Do not put quotation marks inside ascii_art.

ACTION FIELD RULES:

If action_type is "move":
    direction must be one of:
    north, south, east, west

If action_type is "interact":
    object_id must be a visible object ID
    object_action must be one of that object's available actions

If action_type is "wait":
    wait_reason should explain why the pet waits.
"""

        # Instructor + Groq structured outputs.
        #
        # GPT-OSS 20B supports strict JSON schema output.
        decision: PetDecision = (
            self.client.chat.completions.create(
                model=MODEL_NAME,
                response_model=PetDecision,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Current world state:\n\n"
                            f"{state_desc}"
                        ),
                    },
                ],
                max_retries=2,
                temperature=0.7,
            )
        )

        # --------------------------------------------------------
        # EXECUTE ACTION
        # --------------------------------------------------------

        if decision.action_type == "move":

            if not decision.direction:
                result = (
                    f"{engine.pet.name} wanted to move "
                    f"but did not choose a direction."
                )

            else:
                result = engine.move(
                    decision.direction
                )

        elif decision.action_type == "interact":

            if not decision.object_id:
                result = (
                    f"{engine.pet.name} wanted to interact "
                    f"but did not choose an object."
                )

            elif not decision.object_action:
                result = (
                    f"{engine.pet.name} wanted to interact "
                    f"with {decision.object_id}, "
                    f"but did not choose an action."
                )

            else:
                result = engine.interact_with_object(
                    decision.object_id,
                    decision.object_action,
                )

        elif decision.action_type == "wait":

            reason = (
                decision.wait_reason
                or "The pet decided to wait."
            )

            result = (
                f"{engine.pet.name} waited: {reason}"
            )

            current_location = engine.world.locations[
                engine.pet.current_location_id
            ]

            engine.pet.add_memory(
                f"Waited in {current_location.name}."
            )

        else:
            result = "No action executed."

        # --------------------------------------------------------
        # UPDATE PET
        # --------------------------------------------------------

        engine.pet.update_mood()

        if decision.ascii_art.strip():
            engine.pet.ascii_art = (
                decision.ascii_art.strip()
            )

        engine.pet.add_memory(
            f"Thought: {decision.internal_thought} "
            f"| Action: {result}"
        )

        dialogue = decision.dialogue or ""

        return (
            decision.internal_thought,
            result,
            dialogue,
        )


# ============================================================
# ENVIRONMENT AGENT
# ============================================================

class EnvironmentAgent:

    def __init__(self, client: instructor.Instructor):
        self.client = client

    def modify_world(
        self,
        user_command: str,
        engine: SimulationEngine,
    ) -> str:

        current_location = engine.world.locations[
            engine.pet.current_location_id
        ]

        existing_locations = "\n".join(
            f"- {loc.id}: {loc.name}"
            for loc in engine.world.locations.values()
        )

        system_prompt = """
You are the environment architect for a terminal-based
virtual pet simulation.

The user wants to modify the pet's world.

Convert their request into ONE new location.

Rules:

- Create a creative but sensible location.
- The location must connect to the pet's current location.
- Generate a unique lowercase loc_id.
- Use underscores instead of spaces in loc_id.
- Choose exactly one direction.
- Do not use duplicate IDs.
- Keep the description concise.
"""

        user_prompt = f"""
PET CURRENT LOCATION:
ID: {current_location.id}
Name: {current_location.name}

EXISTING LOCATIONS:
{existing_locations}

USER REQUEST:
{user_command}
"""

        action: SpawnLocationAction = (
            self.client.chat.completions.create(
                model=MODEL_NAME,
                response_model=SpawnLocationAction,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                max_retries=2,
                temperature=0.4,
            )
        )

        return engine.spawn_location(
            loc_id=action.loc_id,
            name=action.name,
            description=action.description,
            connect_to_id=engine.pet.current_location_id,
            direction=action.direction,
        )


# ============================================================
# SAVE
# ============================================================

def save_game(engine: SimulationEngine):

    data = {
        "pet": {
            "name": engine.pet.name,
            "species": engine.pet.species,
            "current_location_id":
                engine.pet.current_location_id,
            "hunger": engine.pet.hunger,
            "happiness": engine.pet.happiness,
            "energy": engine.pet.energy,
            "mood": engine.pet.mood,
            "ascii_art": engine.pet.ascii_art,
            "memories": engine.pet.memories,
        },

        "world": {
            "locations": {
                loc_id: {
                    "id": loc.id,
                    "name": loc.name,
                    "description": loc.description,
                    "exits": loc.exits,
                    "objects": loc.objects,
                }
                for loc_id, loc
                in engine.world.locations.items()
            },

            "objects": {
                obj_id: {
                    "id": obj.id,
                    "name": obj.name,
                    "description": obj.description,
                    "location_id": obj.location_id,
                    "available_actions":
                        obj.available_actions,
                }
                for obj_id, obj
                in engine.world.objects.items()
            },
        },
    }

    # Write atomically so an interrupted save doesn't
    # destroy the previous save.
    temp_file = SAVE_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    os.replace(
        temp_file,
        SAVE_FILE,
    )


# ============================================================
# LOAD
# ============================================================

def load_game() -> Optional[SimulationEngine]:

    if not os.path.exists(SAVE_FILE):
        return None

    try:

        with open(
            SAVE_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        world = WorldMap()

        # --------------------------------------------------------
        # LOCATIONS
        # --------------------------------------------------------

        for loc_id, loc_data in (
            data["world"]["locations"].items()
        ):

            world.add_location(
                Location(
                    id=loc_data["id"],
                    name=loc_data["name"],
                    description=loc_data["description"],
                    exits=loc_data.get("exits", {}),
                    objects=loc_data.get("objects", []),
                )
            )

        # --------------------------------------------------------
        # OBJECTS
        # --------------------------------------------------------

        for obj_id, obj_data in (
            data["world"]["objects"].items()
        ):

            world.add_object(
                WorldObject(
                    id=obj_data["id"],
                    name=obj_data["name"],
                    description=obj_data["description"],
                    location_id=obj_data["location_id"],
                    available_actions=obj_data.get(
                        "available_actions",
                        [],
                    ),
                )
            )

        # --------------------------------------------------------
        # PET
        # --------------------------------------------------------

        pet_data = data["pet"]

        pet = Pet(
            name=pet_data["name"],
            species=pet_data["species"],
            current_location_id=
                pet_data["current_location_id"],
            hunger=pet_data.get("hunger", 75),
            happiness=pet_data.get("happiness", 50),
            energy=pet_data.get("energy", 50),
            mood=pet_data.get("mood", "Content"),
            ascii_art=pet_data.get(
                "ascii_art",
                r"""
 /\_/\
( o.o )
/> ^ <
""",
            ),
            memories=pet_data.get(
                "memories",
                [],
            ),
        )

        pet.clamp_stats()
        pet.update_mood()

        return SimulationEngine(
            pet,
            world,
        )

    except (
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
    ) as error:

        # Do not silently hide broken save files.
        print(
            f"Warning: failed to load save file: {error}"
        )

        return None


# ============================================================
# DEFAULT WORLD
# ============================================================

def create_default_world(
    name: str = "Blob",
    species: str = "Digital Slime",
) -> SimulationEngine:

    world = WorldMap()

    # --------------------------------------------------------
    # LOCATIONS
    # --------------------------------------------------------

    house = Location(
        "house",
        "Inside House",
        "A cozy shelter with wooden floors.",
    )

    garden = Location(
        "garden",
        "Garden",
        "A sunny patch of green grass "
        "with wild flowers.",
    )

    world.add_location(house)
    world.add_location(garden)

    world.connect_locations(
        "house",
        "east",
        "garden",
        "west",
    )

    # --------------------------------------------------------
    # OBJECTS
    # --------------------------------------------------------

    bowl = WorldObject(
        "food_bowl",
        "Food Bowl",
        "A ceramic bowl filled with pet food.",
        "house",
        ["eat"],
    )

    bed = WorldObject(
        "bed",
        "Comfy Bed",
        "A plush cushion bed.",
        "house",
        ["sleep"],
    )

    world.add_object(bowl)
    world.add_object(bed)

    # --------------------------------------------------------
    # PET
    # --------------------------------------------------------

    pet = Pet(
        name=name,
        species=species,
        current_location_id="house",
    )

    pet.add_memory(
        f"Woke up for the first time as a "
        f"{species} named {name} in the House."
    )

    engine = SimulationEngine(
        pet,
        world,
    )

    save_game(engine)

    return engine