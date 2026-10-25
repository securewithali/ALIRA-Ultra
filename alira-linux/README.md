# ALIRA for Linux

The full ALIRA desktop assistant (same UI as Windows) for Linux: Gemini Live voice conversation, 148+ languages,
camera vision, screen sharing, floating orb, system monitor, website studio and Linux system control.

## Install (Ubuntu / Debian)

```
sudo apt install -y pipx libportaudio2 libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libgl1 libpulse0 libasound2-plugins pulseaudio-utils tesseract-ocr scrot python3-tk xclip libnotify-bin playerctl brightnessctl wmctrl xdotool network-manager
pipx ensurepath
pipx install ALIRA-linux
ALIRA-linux
```

## Commands

| Command | What it does |
|---|---|
| `ALIRA-linux` | Run ALIRA (window + voice) |
| `ALIRA-linux --background` | Run with only the floating orb |
| `ALIRA-linux install` | Autostart at login (orb) and start now |
| `ALIRA-linux uninstall` | Turn autostart off |
| `ALIRA-linux status` | Version, autostart, display and audio status |
| `ALIRA-linux deps` | Install the required system libraries (`sudo apt`) |
| `ALIRA-linux update` | Update to the newest version |
| `ALIRA-linux remove [--purge]` | Uninstall ALIRA (`--purge` also deletes settings/data) |

Update: `pipx upgrade ALIRA-linux` (or `ALIRA-linux update`) - Remove: `ALIRA-linux remove` (or `pipx uninstall ALIRA-linux`)

First run asks for a free Gemini API key: https://aistudio.google.com/apikey

## What works on Linux

Voice chat, language selection, name, camera vision, screen share, orb, chat UI, open any installed app (from `.desktop` files),
Spotify search, media keys (`playerctl`), volume, brightness, lock/sleep/shutdown, clipboard, notifications, folders,
window management (`wmctrl`), web/YouTube/Google, notes, PDFs, QR codes, timers and more.

## Not available on Linux (yet)

Security mode and reading/replying to WhatsApp chats need Windows. ALIRA answers honestly that they are not available.
Spotify opens the search; Linux does not allow auto-playing a track. WhatsApp send opens WhatsApp Web with your message filled in (you press Send).

Needs a desktop session (X11 or Wayland). On a server/SSH use the text version: `pipx install ALIRA-termux`.
