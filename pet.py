from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Literal, Optional, Union
import json
import os
import sys
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

# Updated to use openai/gpt-oss-20b
MODEL_NAME = "openai/gpt-oss-20b"
SAVE_FILE = "pet_save.json"


# ==========================================
# 1. CORE SIMULATION ENGINE & MEMORY
# ==========================================

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
    exits: Dict[str, str] = field(default_factory=dict)  # direction -> target_location_id
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
            self.locations[obj.location_id].objects.append(obj.id)

    def connect_locations(self, loc1_id: str, direction: str, loc2_id: str, opposite_direction: Optional[str] = None):
        if loc1_id in self.locations and loc2_id in self.locations:
            self.locations[loc1_id].exits[direction] = loc2_id
            if opposite_direction:
                self.locations[loc2_id].exits[opposite_direction] = loc1_id


@dataclass
class Pet:
    name: str
    species: str
    current_location_id: str
    hunger: int = 75
    happiness: int = 50
    energy: int = 50
    mood: str = "Hungry"
    memories: List[str] = field(default_factory=list)

    def add_memory(self, event_description: str):
        """Append an event to the pet's episodic memory log."""
        self.memories.append(event_description)
        # Retain top 15 most recent memories to prevent context bloat
        if len(self.memories) > 15:
            self.memories.pop(0)

    def clamp_stats(self):
        self.hunger = max(0, min(100, self.hunger))
        self.happiness = max(0, min(100, self.happiness))
        self.energy = max(0, min(100, self.energy))

    def update_mood(self):
        if self.hunger > 70:
            self.mood = "Hungry"
        elif self.energy < 20:
            self.mood = "Exhausted"
        elif self.happiness > 75:
            self.mood = "Joyful"
        else:
            self.mood = "Neutral"


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
        msg = "Time passed. Vitals naturally decayed."
        return msg

    def move(self, direction: str) -> str:
        current_loc = self.world.locations[self.pet.current_location_id]
        if direction in current_loc.exits:
            new_loc_id = current_loc.exits[direction]
            self.pet.current_location_id = new_loc_id
            self.pet.energy -= 5
            self.pet.clamp_stats()
            self.pet.update_mood()
            new_loc = self.world.locations[new_loc_id]
            res = f"{self.pet.name} walked {direction} to {new_loc.name}."
            self.pet.add_memory(f"Moved {direction} into {new_loc.name}.")
            return res
        return f"Cannot go {direction}. Available exits: {list(current_loc.exits.keys())}"

    def interact_with_object(self, object_id: str, action: str) -> str:
        current_loc = self.world.locations[self.pet.current_location_id]
        if object_id not in current_loc.objects:
            return f"Object '{object_id}' is not in this room."

        obj = self.world.objects[object_id]
        if action not in obj.available_actions:
            return f"Action '{action}' is invalid for {obj.name}."

        if action == "eat" and object_id == "food_bowl":
            self.pet.hunger -= 35
            self.pet.happiness += 10
            self.pet.clamp_stats()
            self.pet.update_mood()
            res = f"{self.pet.name} ate food from the bowl. Hunger satisfied!"
            self.pet.add_memory(f"Ate food from the bowl in {current_loc.name}.")
            return res

        elif action == "sleep" and object_id == "bed":
            self.pet.energy += 40
            self.pet.clamp_stats()
            self.pet.update_mood()
            res = f"{self.pet.name} rested in the comfy bed."
            self.pet.add_memory(f"Took a nap in the bed in {current_loc.name}.")
            return res

        res = f"{self.pet.name} used {obj.name} ({action})."
        self.pet.add_memory(f"Interacted with {obj.name} ({action}).")
        return res

    def spawn_location(self, loc_id: str, name: str, description: str, connect_to_id: str, direction: str) -> str:
        if connect_to_id not in self.world.locations:
            return f"Target location '{connect_to_id}' does not exist."

        new_loc = Location(id=loc_id, name=name, description=description)
        self.world.add_location(new_loc)

        opposites = {"north": "south", "south": "north", "east": "west", "west": "east"}
        opp_dir = opposites.get(direction)

        self.world.connect_locations(connect_to_id, direction, loc_id, opp_dir)
        res = f"World updated: Created '{name}' to the {direction} of {connect_to_id}."
        self.pet.add_memory(f"Noticed a new area opened up to the {direction}: {name}.")
        return res

    def get_perception(self) -> dict:
        current_loc = self.world.locations[self.pet.current_location_id]
        objects_in_room = [
            {
                "id": self.world.objects[obj_id].id,
                "name": self.world.objects[obj_id].name,
                "description": self.world.objects[obj_id].description,
                "actions": self.world.objects[obj_id].available_actions,
            }
            for obj_id in current_loc.objects
        ]

        return {
            "identity": {
                "name": self.pet.name,
                "species": self.pet.species,
            },
            "vitals": {
                "hunger": self.pet.hunger,
                "happiness": self.pet.happiness,
                "energy": self.pet.energy,
                "mood": self.pet.mood,
            },
            "recent_memories": self.pet.memories,
            "current_location": {
                "id": current_loc.id,
                "name": current_loc.name,
                "description": current_loc.description,
                "available_exits": current_loc.exits,
            },
            "objects_in_room": objects_in_room,
        }


# ==========================================
# 2. STRUCTURED TOOL DEFINITIONS (PYDANTIC)
# ==========================================

class MoveAction(BaseModel):
    """Move to an adjacent location using an available exit direction."""
    direction: str = Field(..., description="Direction to move (e.g. 'east', 'west', 'north', 'south')")

class InteractAction(BaseModel):
    """Interact with an object present in the current room."""
    object_id: str = Field(..., description="The ID of the object to interact with")
    action: str = Field(..., description="The specific action to perform on the object")

class WaitAction(BaseModel):
    """Do nothing and rest or explore thoughts for a turn."""
    reason: str = Field(..., description="Why the pet decides to do nothing")

class PetDecision(BaseModel):
    """The complete decision-making output from the Pet LLM."""
    internal_thought: str = Field(..., description="Inner monologue evaluating needs, memories, and environment.")
    dialogue: Optional[str] = Field(None, description="Optional verbal remark or sound made out loud by the pet.")
    action: Union[MoveAction, InteractAction, WaitAction] = Field(..., description="The concrete physical action chosen.")


class SpawnLocationAction(BaseModel):
    """Create a new region in the world in response to user requests."""
    loc_id: str = Field(..., description="Unique snake_case identifier for the location (e.g., 'mysterious_lake')")
    name: str = Field(..., description="Display name of the location")
    description: str = Field(..., description="Vivid sensory description of the new area")
    direction: Literal["north", "south", "east", "west"] = Field(..., description="Direction relative to pet's current area")


# ==========================================
# 3. LLM AGENT ROUTINES
# ==========================================

class PetAgent:
    def __init__(self, client: instructor.Instructor):
        self.client = client

    def perceive_and_act(self, engine: SimulationEngine) -> str:
        perception = engine.get_perception()

        system_prompt = f"""
You are the brain of {engine.pet.name}, a living autonomous digital {engine.pet.species} in a simulated world.
You make decisions based on your physical vitals, recent memories, current room, visible objects, and available exits.

Rules:
1. Act according to your species characteristics and current mood.
2. Prioritize critical needs: high hunger requires finding food, low energy requires sleep.
3. Use your 'recent_memories' to avoid repeating failed actions and maintain long-term goal continuity.
4. You can ONLY interact with objects in your current room.
5. You can ONLY move through directions listed under 'available_exits'.
"""

        user_prompt = f"Current Perception State:\n{json.dumps(perception, indent=2)}"

        decision: PetDecision = self.client.chat.completions.create(
            model=MODEL_NAME,
            response_model=PetDecision,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )

        print(f"\n[{engine.pet.name}'s Monologue]: {decision.internal_thought}")
        if decision.dialogue:
            print(f"{engine.pet.name}: \"{decision.dialogue}\"")

        if isinstance(decision.action, MoveAction):
            return engine.move(decision.action.direction)
        elif isinstance(decision.action, InteractAction):
            return engine.interact_with_object(decision.action.object_id, decision.action.action)
        elif isinstance(decision.action, WaitAction):
            msg = f"{engine.pet.name} waited: {decision.action.reason}"
            engine.pet.add_memory(f"Waited in {engine.world.locations[engine.pet.current_location_id].name}.")
            return msg
        return "No valid action executed."


class EnvironmentAgent:
    def __init__(self, client: instructor.Instructor):
        self.client = client

    def modify_world(self, user_command: str, engine: SimulationEngine) -> str:
        system_prompt = """
You are the God/World Engine of a digital simulation.
Translate the user's natural language creation request into a valid world modification API call.
Target location is the pet's current location.
"""
        user_prompt = f"Pet's current location ID: {engine.pet.current_location_id}\nUser Command: {user_command}"

        action: SpawnLocationAction = self.client.chat.completions.create(
            model=MODEL_NAME,
            response_model=SpawnLocationAction,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

        return engine.spawn_location(
            loc_id=action.loc_id,
            name=action.name,
            description=action.description,
            connect_to_id=engine.pet.current_location_id,
            direction=action.direction,
        )


# ==========================================
# 4. SAVE / LOAD PERSISTENCE SYSTEM
# ==========================================

def save_game(engine: SimulationEngine):
    data = {
        "pet": {
            "name": engine.pet.name,
            "species": engine.pet.species,
            "current_location_id": engine.pet.current_location_id,
            "hunger": engine.pet.hunger,
            "happiness": engine.pet.happiness,
            "energy": engine.pet.energy,
            "mood": engine.pet.mood,
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
                for loc_id, loc in engine.world.locations.items()
            },
            "objects": {
                obj_id: {
                    "id": obj.id,
                    "name": obj.name,
                    "description": obj.description,
                    "location_id": obj.location_id,
                    "available_actions": obj.available_actions,
                }
                for obj_id, obj in engine.world.objects.items()
            },
        },
    }
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_game() -> Optional[SimulationEngine]:
    if not os.path.exists(SAVE_FILE):
        return None

    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)

        world = WorldMap()
        for loc_id, loc_data in data["world"]["locations"].items():
            world.add_location(Location(
                id=loc_data["id"],
                name=loc_data["name"],
                description=loc_data["description"],
                exits=loc_data["exits"],
                objects=loc_data["objects"],
            ))

        for obj_id, obj_data in data["world"]["objects"].items():
            world.add_object(WorldObject(
                id=obj_data["id"],
                name=obj_data["name"],
                description=obj_data["description"],
                location_id=obj_data["location_id"],
                available_actions=obj_data["available_actions"],
            ))

        pet_data = data["pet"]
        pet = Pet(
            name=pet_data["name"],
            species=pet_data["species"],
            current_location_id=pet_data["current_location_id"],
            hunger=pet_data["hunger"],
            happiness=pet_data["happiness"],
            energy=pet_data["energy"],
            mood=pet_data["mood"],
            memories=pet_data.get("memories", []),
        )

        return SimulationEngine(pet, world)
    except Exception as e:
        print(f"Warning: Could not load save file ({e}). Starting fresh.")
        return None


def create_new_world() -> SimulationEngine:
    print("\n=== WELCOME TO DAEMONAGOTCHI ===")
    print("Creating a new pet profile...\n")

    name = input("Enter a name for your pet: ").strip()
    if not name:
        name = "Blob"

    species = input("Enter your pet's species (e.g., Cyber Dragon, Fluffy Cat, Slime): ").strip()
    if not species:
        species = "Digital Slime"

    world = WorldMap()

    house = Location("house", "Inside House", "A cozy shelter with wooden floors.")
    garden = Location("garden", "Garden", "A sunny patch of green grass with wild flowers.")
    world.add_location(house)
    world.add_location(garden)
    world.connect_locations("house", "east", "garden", "west")

    bowl = WorldObject("food_bowl", "Food Bowl", "A ceramic bowl filled with pet food.", "house", ["eat"])
    bed = WorldObject("bed", "Comfy Bed", "A plush cushion bed.", "house", ["sleep"])
    world.add_object(bowl)
    world.add_object(bed)

    pet = Pet(name=name, species=species, current_location_id="house")
    pet.add_memory(f"Woke up for the first time as a {species} named {name} in the House.")

    engine = SimulationEngine(pet, world)
    save_game(engine)
    return engine


# ==========================================
# 5. MAIN APPLICATION LOOP
# ==========================================

def main():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is missing.")
        print('Run: export GROQ_API_KEY="your_key_here" before running pet.py')
        sys.exit(1)

    client = instructor.from_openai(
        OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
        ),
        mode=instructor.Mode.JSON,
    )

    # Try loading existing save; if not found, trigger initialization prompt
    engine = load_game()
    if not engine:
        engine = create_new_world()

    pet_agent = PetAgent(client)
    env_agent = EnvironmentAgent(client)

    print(f"\n=== DAEMONAGOTCHI ENGINE ACTIVE ({engine.pet.name} the {engine.pet.species}) ===")
    print("Type 'step' to trigger pet autonomous decision loop.")
    print("Type 'create <description>' to alter the world (e.g. 'create a dark forest to the north').")
    print("Type 'status' to check stats & memories.")
    print("Type 'reset' or 'clear' to wipe save data and start over.")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            cmd = input("\n> ").strip()
            if not cmd:
                continue

            if cmd.lower() in ("exit", "quit"):
                save_game(engine)
                print("Progress saved. Goodbye!")
                break

            elif cmd.lower() in ("reset", "clear"):
                confirm = input("Are you sure you want to delete this pet and world data? (y/N): ").strip().lower()
                if confirm == "y":
                    if os.path.exists(SAVE_FILE):
                        os.remove(SAVE_FILE)
                    print("Save file deleted.")
                    engine = create_new_world()
                    print(f"\n=== DAEMONAGOTCHI ENGINE ACTIVE ({engine.pet.name} the {engine.pet.species}) ===")

            elif cmd.lower() == "step":
                engine.tick()
                result = pet_agent.perceive_and_act(engine)
                print(f"[World Result]: {result}")
                save_game(engine)

            elif cmd.lower().startswith("create "):
                user_req = cmd[7:]
                result = env_agent.modify_world(user_req, engine)
                print(f"[World Engine]: {result}")
                save_game(engine)

            elif cmd.lower() == "status":
                p = engine.pet
                print(f"\n--- {p.name}'s Status ({p.species}) ---")
                print(f"Location:  {engine.world.locations[p.current_location_id].name}")
                print(f"Hunger:    {p.hunger}/100")
                print(f"Energy:    {p.energy}/100")
                print(f"Happiness: {p.happiness}/100")
                print(f"Mood:      {p.mood}")
                print("\nRecent Memories:")
                if p.memories:
                    for i, mem in enumerate(p.memories, 1):
                        print(f"  {i}. {mem}")
                else:
                    print("  (No memories yet)")

            else:
                print("Unknown command. Options: 'step', 'create <prompt>', 'status', 'reset', 'exit'")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()


    