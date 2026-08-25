```                                                                                                                                              
    ,---,                                  ____                                                            ___                ,---,              
  .'  .' `\                              ,'  , `.                                                        ,--.'|_            ,--.' |      ,--,    
,---.'     \                          ,-+-,.' _ |   ,---.        ,---,                          ,---.    |  | :,'           |  |  :    ,--.'|    
|   |  .`\  |                      ,-+-. ;   , ||  '   ,'\   ,-+-. /  |             ,----._,.  '   ,'\   :  : ' :           :  :  :    |  |,     
:   : |  '  |  ,--.--.     ,---.  ,--.'|'   |  || /   /   | ,--.'|'   |  ,--.--.   /   /  ' / /   /   |.;__,'  /     ,---.  :  |  |,--.`--'_     
|   ' '  ;  : /       \   /     \|   |  ,', |  |,.   ; ,. :|   |  ,"' | /       \ |   :     |.   ; ,. :|  |   |     /     \ |  :  '   |,' ,'|    
'   | ;  .  |.--.  .-. | /    /  |   | /  | |--' '   | |: :|   | /  | |.--.  .-. ||   | .\  .'   | |: ::__,'| :    /    / ' |  |   /' :'  | |    
|   | :  |  ' \__\/: . ..    ' / |   : |  | ,    '   | .; :|   | |  | | \__\/: . ..   ; ';  |'   | .; :  '  : |__ .    ' /  '  :  | | ||  | :    
'   : | /  ;  ," .--.; |'   ;   /|   : |  |/     |   :    ||   | |  |/  ," .--.; |'   .   . ||   :    |  |  | '.'|'   ; :__ |  |  ' | :'  : |__  
|   | '` ,/  /  /  ,.  |'   |  / |   | |`-'       \   \  / |   | |--'  /  /  ,.  | `---`-'| | \   \  /   ;  :    ;'   | '.'||  :  :_:,'|  | '.'| 
;   :  .'   ;  :   .'   \   :    |   ;/            `----'  |   |/     ;  :   .'   \.'__/\_: |  `----'    |  ,   / |   :    :|  | ,'    ;  :    ; 
|   ,.'     |  ,     .-./\   \  /'---'                     '---'      |  ,     .-./|   :    :             ---`-'   \   \  / `--''      |  ,   /  
'---'        `--`---'     `----'                                       `--`---'     \   \  /                        `----'              ---`-'   
                                                                                     `--`-'                                                      
```

Daemonagotchi is a terminal-based virtual pet (Tamagotchi-style) whose brain is
a large language model. Your pet lives in a persistent simulated world: it
thinks, wanders, eats, sleeps and remembers what happens to it.

Powered by [Groq](https://groq.com) structured outputs via
[instructor](https://github.com/567-labs/instructor), with the interface built
on [Textual](https://github.com/Textualize/textual).

## Features

- LLM-driven pet that perceives its surroundings and autonomously chooses actions
- Persistent memory: your pet remembers its name, recent actions and the places it has visited
- World agent: describe something and a new location is generated into the world on the fly
- Full TUI with live vitals bars, world map, event log and memory log
- Save/load: world state persists between sessions in `pet_save.json`

## Requirements

- Python 3.9+ (developed on 3.14)
- A [Groq API key](https://console.groq.com/keys), Sign in, generate your key and then use it during the setup process.

## Setup

```bash
git clone https://github.com/Maxye4655/Daemonagotchi.git
cd Daemonagotchi

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

export GROQ_API_KEY="your-key-here"   # <---- put your groq api key here, for Windows use: set GROQ_API_KEY=your-key-here

python tui.py
```

On first launch you choose your pet's name and species.

## Usage

| Command | Description |
| --- | --- |
| `step` | The pet thinks and performs one action |
| `create <description>` | Environment agent adds a new location to the world |
| `status` | Refresh the interface |
| `reset` | Delete the save and start over |
| `exit` | Save and quit |

Keyboard: `Ctrl+R` reset, `Ctrl+C` quit.

## Building a standalone binary

PyInstaller is configured via `daemonagotchi.spec`:

```bash
pip install pyinstaller
pyinstaller daemonagotchi.spec --noconfirm
```

The single-file binary ends up at `dist/daemonagotchi`.

## Releases

Tagged releases are built automatically by GitHub Actions for Linux, macOS and
Windows; binaries are attached to the GitHub release. To ship one:

```bash
git tag v1.0
git push origin v1.0
```

## Roadmap

- Talk command and richer pet interactions
- Scheduled ticks so the pet acts on its own over time
- Guided first-run setup for the Groq API key
