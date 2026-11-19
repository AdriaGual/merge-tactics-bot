# 🦓 Merge Tactics Bot

<div align="center">
  
<a><img src="https://github.com/user-attachments/assets/490d6d3e-6ddf-4a59-8744-06d36a083e4b" alt="Markdownify" width="200"></a>
  
![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![ADB](https://img.shields.io/badge/ADB-Compatible-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**🤖 An intelligent automation bot for Merge Tactics mobile game**

*Automate your gameplay with advanced computer vision and strategic decision-making*

</div>

---

## 🚀 Overview

Merge Tactics Bot is a sophisticated automation tool that plays Merge Tactics (Clash Royale Merge mode) autonomously using advanced computer vision and strategic gameplay algorithms. The bot analyzes the game screen in real-time, makes intelligent decisions about unit purchases and deployments, and optimizes your gameplay for maximum efficiency.

## ✨ Features

### 🎯 **Core Automation**
- **🔄 Fully Automated Gameplay** - Plays the game from start to finish without human intervention
- **👁️ Advanced Computer Vision** - Uses OpenCV for precise game state recognition
- **🎮 ADB Integration** - Seamless Android device control via Android Debug Bridge
- **⚡ Real-time Decision Making** - Instant responses to game events and opportunities

### 🧠 **Strategic Intelligence**
- **📊 Auto Target Composition** - Builds a strong composition itself, no setup
- **💎 Smart Elixir Management** - Optimal resource allocation and spending
- **🔄 Merge-First Purchasing** - Buys duplicates to upgrade troops to higher stars
- **🎪 Multi-Phase Handling** - Adapts to different game phases (deploy, battle, rewards)

### 🛠️ **Technical Excellence**
- **🖥️ Headless CLI** - Runs with `python bot.py`, no GUI to babysit
- **📝 Comprehensive Logging** - Detailed logs for debugging and performance tracking
- **⚡ Performance Optimization** - Caching system for improved speed
- **🔧 Modular Architecture** - Clean, maintainable codebase

## 🎮 Supported Units

The bot recognizes and strategically manages all major units:

| **Melee Units** | **Ranged Units** | **Special Units** |
|----------------|------------------|-------------------|
| 🗡️ Knight | 🏹 Archer | 👑 Archer Queen |
| ⚔️ Barbarian | 🎯 Dart Goblin | 🏴‍☠️ Bandit |
| 🛡️ Valkyrie | 💣 Bomber | 👻 Royal Ghost |
| 🤖 PEKKA | 🪓 Executioner | 💀 Skeleton King |
| 👑 Mega Knight | 🏹 Princess | ⭐ Golden Knight |

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- Android device with USB debugging enabled
- ADB (Android Debug Bridge) installed
- Merge Tactics game installed on your device

### Quick Setup

# Clone the repository
```
git clone git@github.com:AdriaGual/merge-tactics-bot.git
```
```
cd merge-tactics-bot
```
# Install dependencies
```
pip install -r requirements.txt
```
# Connect your Android device via USB
```
adb devices
```
(If you can't use the adb command remember to set the environment variables PATH with the route to your adb platform-tools)

# Run the bot
```
python bot.py
```


## 🎯 Usage

### Basic Operation

1. **Connect Device**: Ensure your Android device is connected via USB with debugging enabled
2. **Launch Game**: Open Clash Royale and go to the Merge Tactics lobby
3. **Start Bot**: Run `python bot.py` — it presses "Batalla" to search a match and plays non-stop
4. **No setup**: The bot builds the season's strong composition on its own

```bash
python bot.py                 # search for a match and play forever
python bot.py --no-search     # already in a match: just play it
python bot.py --duration 1800 # stop after 30 minutes
```

## ⚙️ Configuration

### Target Composition (per season)

There is no manual composition to set. The bot reads the current season's troop
tier list (S/A/B/C/D) from CrownStats and builds its target comp from the S/A/B
troops in `config/season_tier.json`: it merges duplicates first, then buys the
strongest target troop it can afford, and never spends elixir on C/D troops, so
it commits to a good comp instead of diluting the roster.

Refresh the season data whenever the roster changes:

```bash
python utils/fetch_tier_list.py
```

If the JSON is missing it falls back to the last known list in
`config/target_comp.py`.

## 📸 Screenshots

<div align="center">

### 🎮 Bot in Action
![Animation](https://github.com/user-attachments/assets/d871cc43-376e-48a8-8f94-c62a927c5303)

</div>

## 🏗️ Architecture

```
merge-tactics-bot/
├── 🤖 bot.py                 # Main bot entry point
├── 🎮 core/
│   ├── strategy.py           # Deploy planner (target comp + merges)
│   ├── board_state.py        # Screenshot -> board state (vision)
│   ├── card_identifier.py    # Shop card recognition (SIFT)
│   ├── image_processing.py   # Computer vision engine
│   └── adb_controller.py     # Android device control
├── ⚙️ config/
│   ├── target_comp.py        # Season target comp (from the tier list)
│   ├── season_tier.json      # Current season S/A/B/C/D troop tiers
│   ├── constants.py          # Game constants and settings
│   └── logging_config.py     # Logging configuration
├── 🛠️ utils/
│   ├── fetch_tier_list.py    # Refresh season_tier.json from CrownStats
│   └── cache_manager.py      # Performance optimization
└── 📁 templates/             # Unit recognition templates
```

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **🍴 Fork** the repository
2. **🌿 Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **💾 Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **📤 Push** to the branch (`git push origin feature/amazing-feature`)
5. **🔄 Open** a Pull Request

## 📋 Roadmap

- [ ] 🎯 Advanced AI strategy optimization
- [ ] 📱 Multi-device support
- [ ] 🌐 Web-based remote control interface
- [ ] 📊 Advanced analytics and statistics
- [ ] 🔄 Auto-update mechanism
- [ ] 🎮 Support for additional game modes

## ⚠️ Disclaimer

This bot is created for educational purposes and personal use. Please ensure you comply with the game's Terms of Service and use responsibly. The developers are not responsible for any consequences resulting from the use of this software.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**⭐ If you found this project helpful, please give it a star! ⭐**

Made with ❤️
</div>
