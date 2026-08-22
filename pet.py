from dataclasses import dataclass


@dataclass
class Pet:
    name: str
    hunger: int = 50
    happiness: int = 50
    energy: int = 50
    mood: str = "Neutral"

    def clamp_stats(self):
        self.hunger = max(0, min(100, self.hunger))
        self.happiness = max(0, min(100, self.happiness))
        self.energy = max(0, min(100, self.energy))

    def update_mood(self):
        if self.hunger < 20:
            self.mood = "Hungry"
        elif self.energy < 20:
            self.mood = "Tired"
        elif self.happiness > 75:
            self.mood = "Happy"
        else:
            self.mood = "Neutral"

    def feed(self):
        self.hunger -= 20
        self.happiness += 5
        self.clamp_stats()
        self.update_mood()

    def play(self):
        self.happiness += 20
        self.energy -= 15
        self.hunger -= 10
        self.clamp_stats()
        self.update_mood()

    def sleep(self):
        self.energy += 30
        self.hunger -= 5
        self.clamp_stats()
        self.update_mood()

    def tick(self):
        self.hunger += 1
        self.happiness -= 1
        self.energy -= 1
        self.clamp_stats()
        self.update_mood()


def display_status(pet):
    print()
    print(f"{pet.name}")
    print("-" * 20)
    print(f"Hunger:     {pet.hunger}/100")
    print(f"Happiness:  {pet.happiness}/100")
    print(f"Energy:     {pet.energy}/100")
    print(f"Mood:       {pet.mood}")
    print()


def main():
    pet = Pet("Blob")

    print("Welcome to Daemonagotchi. ฅ^>⩊<^ ฅ")
    print(f"Your pet's name is {pet.name}.")
    print("Type 'help' to see available commands.")

    while True:
        command = input("> ").strip().lower()

        if command == "feed":
            pet.feed()
            print(f"{pet.name} eats the food.")

        elif command == "play":
            pet.play()
            print(f"{pet.name} plays with you.")

        elif command == "sleep":
            pet.sleep()
            print(f"{pet.name} goes to sleep.")

        elif command == "tick":
            pet.tick()
            print("Time passes...")

        elif command == "status":
            display_status(pet)

        elif command == "help":
            print()
            print("──── ୨୧ ────Commands──── ୨୧ ────")
            print("              feed      ")
            print("              play      ")
            print("              sleep     ")
            print("              tick      ")
            print("              status    ")
            print("              quit      ")
            print()

        elif command in ("quit", "exit"):
            print(f"Goodbye. {pet.name} will miss you. ૮◞ ‸ ◟ ა")
            break

        elif command == "":
            continue

        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for a list of commands.")


if __name__ == "__main__":
    main()