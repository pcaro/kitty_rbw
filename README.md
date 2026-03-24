# kitty_rbw

A [kitty](https://sw.kovidgoyal.net/kitty/) kitten to quickly search and use [rbw](https://github.com/doy/rbw) (unofficial Bitwarden CLI) credentials directly from the terminal.

![kitty_rbw screenshot](screenshot.png)

## Features

- **Fuzzy search** through your vault using `fzf` — searches by name, username and folder simultaneously.
- **Direct injection**: types password or username directly into the active terminal window.
- **Clipboard support**: copy password, username or TOTP code to clipboard.
- **TOTP support**: copy the 2FA code for entries that have it configured.
- **Most-used first**: the 10 most frequently used entries appear at the top in bold, separated from the rest.
- **Folder shortcuts**: launch the kitten pre-filtered to a specific folder via `kitty.conf` arguments.
- **Duplicate-safe**: internally uses UUIDs, so entries with the same name are always resolved correctly.
- **Sync**: refresh your local vault without leaving the kitten.
- **Environment export**: select a folder and export all its secrets as environment variables into your active shell (`rbw_env.py`).

## Requirements

- [kitty](https://sw.kovidgoyal.net/kitty/) terminal
- [rbw](https://github.com/doy/rbw) installed and configured (`rbw login` / `rbw unlock` done at least once)
- [fzf](https://github.com/junegunn/fzf) installed

## Installation

1. Clone into your kitty config directory:
   ```bash
   cd ~/.config/kitty
   git clone https://github.com/pcaro/kitty_rbw
   ```

2. Add a shortcut to `kitty.conf`:
   ```
   map kitty_mod+b kitten kitty_rbw/rbw.py
   ```

## Usage

Press the configured shortcut to open an overlay with your vault entries. The list shows name, username (dimmed) and folder (in cyan) for each entry.

### Key bindings

| Key | Action |
|-----|--------|
| `Enter` | Type the **password** into the terminal |
| `Ctrl+u` | Type the **username** into the terminal |
| `Ctrl+b` | Type **username**, `Tab`, then **password** (useful for login forms) |
| `Ctrl+t` | Copy the **TOTP** code to clipboard |
| `Alt+p` | Copy the **password** to clipboard |
| `Alt+u` | Copy the **username** to clipboard |
| `Alt+s` | Sync the vault and refresh the list |
| `Esc` | Cancel |

### Folder shortcuts

You can pass a folder name as an argument to pre-filter the list:

```
map kitty_mod+b       kitten kitty_rbw/rbw.py
map kitty_mod+shift+y kitten kitty_rbw/rbw.py yith
map kitty_mod+shift+t kitten kitty_rbw/rbw.py terminal
```

The folder name is case-insensitive.

### Environment Export (`rbw_env.py`)

This tool allows you to select a Bitwarden folder and export all its entries as environment variables into your current shell. The variable name is derived from the entry's username (sanitized to be a valid bash variable).

**As a Kitty Kitten:**
Map it in your `kitty.conf` to type the `export` commands directly into your active window:
```
map kitty_mod+e kitten kitty_rbw/rbw_env.py
```

**As a Standalone Script:**
You can run it in any terminal to evaluate the exports:
```bash
eval $(python ~/.config/kitty/kitty_rbw/rbw_env.py)
```
Or pass a folder name directly to skip the interactive selection:
```bash
eval $(python ~/.config/kitty/kitty_rbw/rbw_env.py my_folder)
```

**Folder Exclusions:**
You can hide specific folders from the interactive `fzf` picker by creating a file at `~/.config/kitty_rbw/excluded_folders.txt` and listing the folder names to exclude (one per line, case-insensitive). Entries with the name or username `NOEXPORT` are always ignored.

## Usage history

The kitten tracks how often each entry is used and stores a counter in `~/.local/share/kitty_rbw/usage.json` (permissions `0700`/`0600`). The top 10 most-used entries are shown first. The file contains only UUIDs, counts and timestamps — no passwords or usernames.

## License

MIT
