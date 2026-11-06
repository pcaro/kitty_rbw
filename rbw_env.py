import datetime
import os
import re
import subprocess
import sys
import tempfile

# Reuse some logic/style from rbw.py
DIM = "\033[2m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

CONFIG_DIR = os.path.expanduser("~/.config/kitty_rbw")
EXCLUDED_FOLDERS_FILE = os.path.join(CONFIG_DIR, "excluded_folders.txt")


def get_env() -> dict:
    env = os.environ.copy()
    home = os.path.expanduser("~")
    for p in [os.path.join(home, ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
        if p not in env.get("PATH", ""):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")
    return env


def sanitize_name(name: str) -> str:
    # Equivalent to ${username//[^a-zA-Z0-9_]/_}
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def load_excluded_folders() -> set[str]:
    """Lowercased folder names hidden from the picker. A missing file means no exclusions."""
    try:
        with open(EXCLUDED_FOLDERS_FILE) as f:
            return {line.strip().lower() for line in f if line.strip()}
    except OSError:
        return set()


def load_folders(env: dict) -> list[str]:
    proc = subprocess.run(
        ["rbw", "list", "--fields", "folder"],
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        return []

    excluded = load_excluded_folders()

    folders = {
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and line.strip().lower() not in excluded
    }
    return sorted(folders)


def run_fzf(options: list[str], env: dict) -> str | None:
    fzf_cmd = [
        "fzf",
        "--ansi",
        "--layout=reverse",
        "--height=40%",
        "--header",
        "\n  Select folder to export as environment variables\n",
    ]
    try:
        proc = subprocess.Popen(
            fzf_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        stdout, _ = proc.communicate(input="\n".join(options))
        return stdout.strip()
    except FileNotFoundError:
        print("Error: 'fzf' not found in PATH.", file=sys.stderr)
        return None


def main(args: list[str]) -> list[dict[str, str]] | None:
    env = get_env()

    # If folder is passed as argument, use it. Otherwise, use fzf.
    if len(args) > 1:
        folder = args[1]
    else:
        folders = load_folders(env)
        if not folders:
            print("No folders found or vault locked.", file=sys.stderr)
            if sys.stdin.isatty():
                input("Press Enter to close...")
            return None
        folder = run_fzf(folders, env)
        if not folder:
            return None

    if sys.stdin.isatty():
        print(f"Exporting secrets from folder: {folder}...", file=sys.stderr)

    # Load entries in folder
    proc = subprocess.run(
        ["rbw", "list", "--fields", "id,name,user,folder"],
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        print(f"Error: {proc.stderr.strip()}", file=sys.stderr)
        if sys.stdin.isatty():
            input("Press Enter to close...")
        return None

    results = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue

        eid, name, user, f = parts[0], parts[1], parts[2], parts[3]

        if f.lower() == folder.lower():
            if name == "NOEXPORT" or user == "NOEXPORT":
                continue
            if not user:
                continue

            try:
                # Get the secret (password)
                password = subprocess.check_output(
                    ["rbw", "get", eid], text=True, env=env
                ).strip()

                results.append(
                    {"var": sanitize_name(user), "val": password, "name": name}
                )
                if sys.stdin.isatty():
                    print(f"✅ Prepared {name} ({user})", file=sys.stderr)
            except subprocess.CalledProcessError:
                if sys.stdin.isatty():
                    print(f"❌ Failed to get {name}", file=sys.stderr)

    if not results:
        if sys.stdin.isatty():
            print("No exportable entries found in this folder.", file=sys.stderr)
            input("Press Enter to close...")
        return None

    # When run as `kitten rbw_env.py` from the shell, kitty runs main() but
    # never calls handle_result(), so inject the `source` command ourselves.
    if _is_kitten_cli(env):
        _inject_into_shell(results, env)

    return results


def build_export_script(result: list[dict[str, str]]) -> str:
    timestamp = datetime.datetime.now().astimezone().isoformat()

    exports = [f"export RBW_ENV_LOADED='{timestamp}'"]
    for entry in result:
        var = entry["var"]
        val = entry["val"].replace("'", "'\\''")
        exports.append(f"export {var}='{val}'")

    # Write to a temporary file to hide secrets from the screen
    fd, path = tempfile.mkstemp(prefix="kitty_rbw_env_")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(exports) + "\n")
        # Report what was loaded from inside the script: a `#` comment typed
        # into an interactive zsh is not a comment unless INTERACTIVE_COMMENTS
        # is set, and fails with "command not found: #".
        var_list = " ".join(entry["var"] for entry in result)
        f.write(f'echo "Exported: {var_list}"\n')
        # Ensure the file deletes itself after sourcing
        f.write(f"rm -f {path}\n")

    return path


def _is_kitten_cli(env: dict) -> bool:
    # True when run as `kitten rbw_env.py` from a shell inside kitty. Overlay
    # kittens have KITTY_CHILD_PID set, and plain `eval $(python ...)` pipes
    # stdout, so both are excluded.
    return (
        "KITTY_WINDOW_ID" in env
        and "KITTY_CHILD_PID" not in env
        and sys.stdout.isatty()
    )


def _inject_into_shell(result: list[dict[str, str]], env: dict) -> None:
    listen = env.get("KITTY_LISTEN_ON")
    window_id = env.get("KITTY_WINDOW_ID")
    if not listen or not window_id:
        print("Error: not running inside kitty.", file=sys.stderr)
        return

    path = build_export_script(result)

    proc = subprocess.run(
        [
            "kitten", "@", "--to", listen, "send-text",
            "--stdin", "--match", f"id:{window_id}",
        ],
        input=f"\nsource {path}\n",
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        print(
            f"Error: could not inject into shell: {proc.stderr.strip()}",
            file=sys.stderr,
        )


def handle_result(
    args: list[str],
    result: list[dict[str, str]] | None,
    target_window_id: int,
    boss,
) -> None:
    if not result:
        return

    window = boss.window_id_map.get(target_window_id) or boss.active_window
    if window is None:
        return

    path = build_export_script(result)

    # Send command with leading space to avoid shell history
    cmd = f"\nsource {path}\n"
    window.write_to_child(cmd)


if __name__ == "__main__":
    res = main(sys.argv)
    if res:
        timestamp = datetime.datetime.now().astimezone().isoformat()
        print(f"export RBW_ENV_LOADED='{timestamp}'")
        for entry in res:
            var = entry["var"]
            val = entry["val"].replace("'", "'\\''")
            print(f"export {var}='{val}'")
