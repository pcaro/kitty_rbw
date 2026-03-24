# AI Agents in kitty-rbw

This project follows a structured approach for AI agents to ensure consistency, security, and high-quality code.

## Agent Guidelines

- **Security First:** Never store or log Bitwarden credentials or session keys.
- **Tooling:** Always verify that `rbw` and `fzf` are available in the environment before executing commands that depend on them.
- **Python Style:** Follow PEP 8 standards. Use type hints where possible.
- **Language:** Documentation and commits should be in English, but blog-related notes (if applicable) follow the bilingual (ES/EN) rule defined in `.gemini/GEMINI.md`.

## Workflows

1. **Research:** Understand the current `rbw` integration in `rbw.py`.
2. **Strategy:** Propose changes that maintain the lightweight nature of the tool.
3. **Execution:** Apply surgical changes and verify with manual or automated tests.
4. **Validation:** Ensure the script still integrates correctly with `kitty`'s kitten framework.
