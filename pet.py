# This File containst the logic with all of the terminal functionality stripped away so that it can act as an import module for tui.py


from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Union
import json
import os
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

MODEL_NAME = "openai/gpt-oss-20b"
SAVE_FILE = "pet_save.json"

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
    ascii_art: str = r"""
 /\_/\  
( o.o ) 
/>  < \
"""
    memories: List[str] = field(default_factory=list)

    def add_memory(self, event_description: str):
        self.memories.append(event_description)
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
        return "Time passed. Vitals naturally decayed."

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
            "identity": {"name": self.pet.name, "species": self.pet.species},
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

class MoveAction(BaseModel):
    direction: str = Field(..., description="Direction to move")

class InteractAction(BaseModel):
    object_id: str = Field(..., description="The ID of the object")
    action: str = Field(..., description="The specific action to perform")

class WaitAction(BaseModel):
    reason: str = Field(..., description="Why the pet decides to do nothing")

class PetDecision(BaseModel):
    internal_thought: str = Field(..., description="Inner monologue evaluating needs, memories, and environment.")
    dialogue: Optional[str] = Field(None, description="Optional verbal remark or sound made out loud by the pet.")
    ascii_art: str = Field(
        ..., 
        description="A 3-5 line ASCII drawing of the pet. Use standard text characters. Do NOT use unescaped single backslashes."
    )
    action: Union[MoveAction, InteractAction, WaitAction] = Field(..., description="The concrete physical action chosen.")
    
class SpawnLocationAction(BaseModel):
    loc_id: str = Field(...)
    name: str = Field(...)
    description: str = Field(...)
    direction: Literal["north", "south", "east", "west"] = Field(...)

class PetAgent:
    def __init__(self, client: instructor.Instructor):
        self.client = client

    def perceive_and_act(self, engine: SimulationEngine) -> tuple[str, str, Optional[str]]:
        perception = engine.get_perception()

        system_prompt = f"""
You are the brain of {engine.pet.name}, a living autonomous digital {engine.pet.species} in a simulated world.
You make decisions based on your physical vitals, recent memories, current room, visible objects, and available exits.

Rules:
1. Act according to your species ({engine.pet.species}) characteristics and current mood.
2. Prioritize critical needs: high hunger requires finding food, low energy requires sleep.
3. Express your current state in `ascii_art` using a semi-compact 3-5 line ASCII drawing. Keep width under 20 characters. 
   IMPORTANT: Ensure all newline breaks inside `ascii_art` are standard '\\n' strings.
"""
        decision: PetDecision = self.client.chat.completions.create(
            model=MODEL_NAME,
            response_model=PetDecision,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Current Perception State:\n{json.dumps(perception, indent=2)}"},
            ],
            temperature=0.7,
        )

        if isinstance(decision.action, MoveAction):
            res = engine.move(decision.action.direction)
        elif isinstance(decision.action, InteractAction):
            res = engine.interact_with_object(decision.action.object_id, decision.action.action)
        elif isinstance(decision.action, WaitAction):
            res = f"{engine.pet.name} waited: {decision.action.reason}"
            engine.pet.add_memory(f"Waited in {engine.world.locations[engine.pet.current_location_id].name}.")
        else:
            res = "No action executed."

        engine.pet.ascii_art = decision.ascii_art

        return decision.internal_thought, res, decision.dialogue

class EnvironmentAgent:
    def __init__(self, client: instructor.Instructor):
        self.client = client

    def modify_world(self, user_command: str, engine: SimulationEngine) -> str:
        system_prompt = "Translate user creation request to world modification API."
        user_prompt = f"Pet location: {engine.pet.current_location_id}\nCommand: {user_command}"

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
            ascii_art=pet_data.get("ascii_art", r"""
 /\_/\  
( o.o ) 
/>  < \
"""),
            memories=pet_data.get("memories", []),
        )

        return SimulationEngine(pet, world)
    except Exception:
        return None

def create_default_world(name: str = "Blob", species: str = "Digital Slime") -> SimulationEngine:
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