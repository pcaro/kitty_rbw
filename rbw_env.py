import os
import re
import subprocess
import sys
from typing import Any

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
    for p in [os.path.join(home, ".local/bin"), "/usr/local/bin", "/usr/bin"]:
        if p not in env.get("PATH", ""):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")
    return env


def sanitize_name(name: str) -> str:
    # Equivalent to ${username//[^a-zA-Z0-9_]/_}
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def load_folders(env: dict) -> list[str]:
    proc = subprocess.run(
        ["rbw", "list", "--fields", "folder"],
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        return []

    excluded = set()
    if os.path.exists(EXCLUDED_FOLDERS_FILE):
        with open(EXCLUDED_FOLDERS_FILE, "r") as f:
            excluded = {line.strip().lower() for line in f if line.strip()}

    folders = {
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and line.strip().lower() not in excluded
    }
    return sorted(list(folders))


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

    return results


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

    import tempfile

    exports = []
    for entry in result:
        var = entry["var"]
        val = entry["val"].replace("'", "'\\''")
        exports.append(f"export {var}='{val}'")

    # Write to a secure temporary file to hide secrets from the screen
    fd, path = tempfile.mkstemp(prefix="kitty_rbw_env_")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(exports) + "\n")
        # Ensure the file deletes itself after sourcing
        f.write(f"rm -f {path}\n")

    # Send command with leading space to avoid shell history
    cmd = f"\nsource {path}\n"
    window.write_to_child(cmd)

    # Show exported variable names as a comment (with leading space to avoid history)
    var_list = " ".join(entry["var"] for entry in result)
    window.write_to_child(f" # Exported: {var_list}\n")


if __name__ == "__main__":
    res = main(sys.argv)
    if res:
        for entry in res:
            var = entry["var"]
            val = entry["val"].replace("'", "'\\''")
            print(f"export {var}='{val}'")
