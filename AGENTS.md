# AI Agents in kitty-rbw

This project follows a structured approach for AI agents to ensure consistency, security, and high-quality code.

## Agent Guidelines

- **Security First:** Never store or log Bitwarden credentials or session keys.
- **Tooling:** Always verify that `rbw` and `fzf` are available in the environment before executing commands that depend on them.
- **Python Style:** Follow PEP 8 standards. Use type hints where possible.
- **Language:** Documentation and commits should be in English, but blog-related notes (if applicable) follow the bilingual (ES/EN) rule defined in `.gemini/GEMINI.md`.

## Scripts

### rbw.py
Main kitten for interactive credential selection. Provides a fuzzy-searchable list of all vault entries with keyboard shortcuts for copying passwords, usernames, TOTP codes, or auto-typing credentials into the terminal.

### rbw_env.py
Kitten for bulk-exporting credentials as environment variables. Select a folder and it exports all entries (using username as variable name, password as value) directly into the shell environment via a temporary file that self-destructs after sourcing. Displays the list of exported variable names after loading. Additionally, it exports `RBW_ENV_LOADED` with the current local timestamp in ISO 8601 format, allowing detection of active credential sessions.
