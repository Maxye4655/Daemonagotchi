from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ==========================================
# 1. WORLD & OBJECT MODELS
# ==========================================

@dataclass
class WorldObject:
    id: str
    name: str
    description: str
    location_id: str
    available_actions: List[str]  # e.g. ["eat", "inspect"]


@dataclass
class Location:
    id: str
    name: str
    description: str
    exits: Dict[str, str] = field(default_factory=dict)  # direction -> target_location_id
    objects: List[str] = field(default_factory=list)     # list of object_ids


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
        """Connects two rooms bi-directionally or uni-directionally."""
        if loc1_id in self.locations and loc2_id in self.locations:
            self.locations[loc1_id].exits[direction] = loc2_id
            if opposite_direction:
                self.locations[loc2_id].exits[opposite_direction] = loc1_id


# ==========================================
# 2. PET MODEL & SIMULATION ENGINE
# ==========================================

@dataclass
class Pet:
    name: str
    current_location_id: str
    hunger: int = 50
    happiness: int = 50
    energy: int = 50
    mood: str = "Neutral"

    def clamp_stats(self):
        self.hunger = max(0, min(100, self.hunger))
        self.happiness = max(0, min(100, self.happiness))
        self.energy = max(0, min(100, self.energy))

    def update_mood(self):
        if self.hunger > 80:
            self.mood = "Starving"
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
        """Advance world state by 1 unit of time."""
        self.pet.hunger += 2
        self.pet.happiness -= 1
        self.pet.energy -= 1
        self.pet.clamp_stats()
        self.pet.update_mood()
        return "Time passed. Vitals decreased."

    # --- Tool Actions (The Pet AI will call these later) ---

    def move(self, direction: str) -> str:
        current_loc = self.world.locations[self.pet.current_location_id]
        if direction in current_loc.exits:
            new_loc_id = current_loc.exits[direction]
            self.pet.current_location_id = new_loc_id
            self.pet.energy -= 3
            self.pet.clamp_stats()
            self.pet.update_mood()
            new_loc = self.world.locations[new_loc_id]
            return f"{self.pet.name} moved {direction} to {new_loc.name}."
        return f"Cannot go {direction} from here. Exits available: {list(current_loc.exits.keys())}"

    def interact_with_object(self, object_id: str, action: str) -> str:
        current_loc = self.world.locations[self.pet.current_location_id]
        if object_id not in current_loc.objects:
            return f"Object '{object_id}' is not in this room."

        obj = self.world.objects[object_id]
        if action not in obj.available_actions:
            return f"Action '{action}' is invalid for {obj.name}."

        # Action handlers
        if action == "eat" and object_id == "food_bowl":
            self.pet.hunger -= 25
            self.pet.happiness += 5
            self.pet.clamp_stats()
            self.pet.update_mood()
            return f"{self.pet.name} ate food from the bowl. Hunger satisfied!"
            
        elif action == "sleep" and object_id == "bed":
            self.pet.energy += 40
            self.pet.clamp_stats()
            self.pet.update_mood()
            return f"{self.pet.name} slept in the bed and restored energy."

        return f"{self.pet.name} interacted with {obj.name} ({action}). Nothing noticeable happened."

    # --- God Actions (The Environment AI will call these later) ---

    def spawn_location(self, loc_id: str, name: str, description: str, connect_to_id: str, direction: str) -> str:
        """Spawns a new location and connects it to an existing one."""
        if connect_to_id not in self.world.locations:
            return f"Target location '{connect_to_id}' does not exist."
        
        new_loc = Location(id=loc_id, name=name, description=description)
        self.world.add_location(new_loc)
        
        # Simple opposite mapping for clean navigation
        opposites = {"north": "south", "south": "north", "east": "west", "west": "east"}
        opp_dir = opposites.get(direction)
        
        self.world.connect_locations(connect_to_id, direction, loc_id, opp_dir)
        return f"Created location '{name}' ({direction} of {connect_to_id})."

    # --- Perception Payload ---

    def get_perception(self) -> dict:
        """Returns the structured payload that will eventually be sent to the Pet LLM."""
        current_loc = self.world.locations[self.pet.current_location_id]
        objects_in_room = [
            {
                "id": self.world.objects[obj_id].id,
                "name": self.world.objects[obj_id].name,
                "actions": self.world.objects[obj_id].available_actions
            }
            for obj_id in current_loc.objects
        ]
        
        return {
            "vitals": {
                "hunger": self.pet.hunger,
                "happiness": self.pet.happiness,
                "energy": self.pet.energy,
                "mood": self.pet.mood,
            },
            "location": {
                "name": current_loc.name,
                "description": current_loc.description,
                "exits": list(current_loc.exits.keys()),
            },
            "objects": objects_in_room
        }


# ==========================================
# 3. CLI & BOOTSTRAP
# ==========================================

def setup_default_world() -> SimulationEngine:
    world = WorldMap()
    
    # Locations
    house = Location("house", "Inside House", "A cozy living space.")
    garden = Location("garden", "Garden", "A peaceful outdoors area with grass.")
    world.add_location(house)
    world.add_location(garden)
    world.connect_locations("house", "east", "garden", "west")

    # Objects
    bowl = WorldObject("food_bowl", "Food Bowl", "A bowl full of pet kibble.", "house", ["eat"])
    bed = WorldObject("bed", "Comfy Bed", "A soft pet bed.", "house", ["sleep"])
    world.add_object(bowl)
    world.add_object(bed)

    pet = Pet(name="Blob", current_location_id="house")
    return SimulationEngine(pet, world)


def main():
    engine = setup_default_world()
    print("Engine Initialized. Manual control mode active.")
    print("Commands: move <dir>, interact <obj_id> <action>, spawn <loc_id> <dir>, tick, inspect, exit\n")

    while True:
        cmd_input = input("> ").strip().lower().split()
        if not cmd_input:
            continue

        verb = cmd_input[0]

        if verb in ("exit", "quit"):
            break

        elif verb == "inspect":
            perception = engine.get_perception()
            print("\n--- PERCEPTION PAYLOAD ---")
            print(perception)
            print("--------------------------\n")

        elif verb == "tick":
            res = engine.tick()
            print(res)

        elif verb == "move" and len(cmd_input) > 1:
            res = engine.move(cmd_input[1])
            print(res)

        elif verb == "interact" and len(cmd_input) > 2:
            res = engine.interact_with_object(cmd_input[1], cmd_input[2])
            print(res)

        elif verb == "spawn" and len(cmd_input) > 2:
            # God command: spawn lake east
            res = engine.spawn_location(
                loc_id=cmd_input[1],
                name=cmd_input[1].capitalize(),
                description=f"A freshly created {cmd_input[1]}.",
                connect_to_id=engine.pet.current_location_id,
                direction=cmd_input[2]
            )
            print(res)

        else:
            print("Unknown or incomplete command.")


if __name__ == "__main__":
    main()