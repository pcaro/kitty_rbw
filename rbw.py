import json
import os
import subprocess
import time

try:
    from kitty.clipboard import set_clipboard_string
except ImportError:
    from kitty.fast_data_types import set_clipboard_string

# --- Fichero de historial de uso ---
USAGE_FILE = os.path.expanduser("~/.local/share/kitty_rbw/usage.json")
TOP_N = 10  # entradas "más usadas" que se muestran primero

# Header en dos líneas para que quepa en ventanas pequeñas.
HEADER_BASE = "\n  Enter: pass    C-u: usuario    C-b: usuario⇥pass    C-t: copiar totp\n  Alt-p: copiar pass    Alt-u: copiar usuario    Alt-s: sincronizar\n "


def build_header(folder: str | None) -> str:
    if folder:
        return f"\n  Carpeta: {folder}" + HEADER_BASE
    return HEADER_BASE

FZF_EXPECT = "enter,ctrl-u,ctrl-b,ctrl-t,alt-p,alt-u,alt-s"

DIM   = "\033[2m"
CYAN  = "\033[36m"
BOLD  = "\033[1m"
RESET = "\033[0m"
SEP   = f"{DIM}{'─' * 40}{RESET}"  # separador visual entre top y resto


# ---------------------------------------------------------------------------
# Historial de uso
# ---------------------------------------------------------------------------

def load_usage() -> dict:
    try:
        with open(USAGE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_usage(usage: dict) -> None:
    os.makedirs(os.path.dirname(USAGE_FILE), mode=0o700, exist_ok=True)
    # Escribir en fichero temporal y renombrar para evitar escrituras parciales
    tmp = USAGE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(usage, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, USAGE_FILE)


def record_usage(entry_id: str) -> None:
    usage = load_usage()
    rec = usage.get(entry_id, {"count": 0, "last": 0})
    rec["count"] += 1
    rec["last"] = time.time()
    usage[entry_id] = rec
    save_usage(usage)


# ---------------------------------------------------------------------------
# rbw helpers
# ---------------------------------------------------------------------------

def get_env() -> dict:
    env = os.environ.copy()
    home = os.path.expanduser("~")
    for p in [os.path.join(home, ".local/bin"), "/usr/local/bin", "/usr/bin"]:
        if p not in env.get("PATH", ""):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")
    return env


def load_entries(env: dict) -> list[dict] | None:
    proc = subprocess.run(
        ["rbw", "list", "--fields", "id,name,user,folder"],
        text=True, capture_output=True, env=env,
    )
    if proc.returncode != 0:
        print(f"Error rbw list: {proc.stderr.strip()}")
        input("Presiona Enter para cerrar...")
        return None

    entries = []
    for line in proc.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        entries.append({
            "id":     parts[0] if len(parts) > 0 else "",
            "name":   parts[1] if len(parts) > 1 else "",
            "user":   parts[2] if len(parts) > 2 else "",
            "folder": parts[3] if len(parts) > 3 else "",
        })
    return entries


# ---------------------------------------------------------------------------
# Construcción del listado para fzf
# ---------------------------------------------------------------------------

def sort_entries(entries: list[dict], usage: dict) -> tuple[list[dict], list[dict]]:
    """
    Devuelve (top, rest): los TOP_N más usados (orden por count desc, last desc)
    y el resto en orden original (ya viene alfabético de rbw).
    Entradas sin uso van solo al resto.
    """
    used = [(e, usage[e["id"]]) for e in entries if e["id"] in usage]
    used.sort(key=lambda x: (-x[1]["count"], -x[1]["last"]))

    top_ids = {e["id"] for e, _ in used[:TOP_N]}
    top  = [e for e, _ in used[:TOP_N]]
    rest = [e for e in entries if e["id"] not in top_ids]
    return top, rest


def entry_to_display(e: dict) -> str:
    user_str   = f"  {DIM}{e['user']}{RESET}"                if e["user"]   else ""
    folder_str = f"  {CYAN}{DIM}[{e['folder']}]{RESET}"      if e["folder"] else ""
    return f"{e['name']}{user_str}{folder_str}"


def build_fzf_lines(entries: list[dict], usage: dict) -> list[str]:
    """
    Formato de cada línea: <id>TAB<display>
    fzf recibe el id en campo 1 (oculto con --with-nth=2) y muestra el display.
    Las entradas top van primero, separadas del resto por una línea separadora.
    """
    top, rest = sort_entries(entries, usage)

    lines = []

    if top:
        for e in top:
            lines.append(f"{e['id']}\t{BOLD}{entry_to_display(e)}{RESET}")
        # Separador: ID vacío para que no se pueda seleccionar
        lines.append(f"\t{SEP}")

    for e in rest:
        lines.append(f"{e['id']}\t{entry_to_display(e)}")

    return lines


# ---------------------------------------------------------------------------
# fzf
# ---------------------------------------------------------------------------

def run_fzf(fzf_lines: list[str], env: dict, folder: str | None = None) -> tuple[str, str] | None:
    fzf_cmd = [
        "fzf",
        "--ansi",
        "--delimiter=\t",
        "--with-nth=2",        # mostrar solo el campo display (oculta el UUID)
        "--nth=1,2",           # buscar también en UUID y display
        "--header", build_header(folder),
        "--expect", FZF_EXPECT,
        "--layout=reverse",
        "--height=60%",
        "--min-height=20",
        "--tiebreak=index",
    ]

    try:
        proc = subprocess.Popen(
            fzf_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        stdout, _ = proc.communicate(input="\n".join(fzf_lines))
    except FileNotFoundError:
        print("Error: 'fzf' no encontrado en PATH.")
        input("Presiona Enter para cerrar...")
        return None

    lines = stdout.strip().splitlines()
    if len(lines) < 2 or not lines[1].strip():
        return None

    return lines[0], lines[1]  # (key, selected_raw)


def extract_id(selected_raw: str) -> str:
    return selected_raw.split("\t")[0]


# ---------------------------------------------------------------------------
# Kitten entrypoints
# ---------------------------------------------------------------------------

def main(args: list[str]) -> dict | None:
    env    = get_env()
    folder = args[1] if len(args) > 1 else None

    entries = load_entries(env)
    if entries is None:
        return None

    if folder:
        entries = [e for e in entries if e["folder"].lower() == folder.lower()]
        if not entries:
            print(f"No hay entradas en la carpeta '{folder}'.")
            input("Presiona Enter para cerrar...")
            return None
    elif not entries:
        print("La bóveda de rbw está vacía o bloqueada.")
        input("Presiona Enter para cerrar...")
        return None

    usage = load_usage()

    while True:
        fzf_lines = build_fzf_lines(entries, usage)
        result = run_fzf(fzf_lines, env, folder)
        if result is None:
            return None

        key, selected_raw = result
        entry_id = extract_id(selected_raw)

        # Ignorar si el usuario seleccionó el separador
        if not entry_id:
            continue

        # Sync
        if key == "alt-s":
            print("Sincronizando bóveda...")
            sync = subprocess.run(["rbw", "sync"], text=True, capture_output=True, env=env)
            if sync.returncode != 0:
                print(f"Error: {sync.stderr.strip()}")
                input("Presiona Enter para continuar...")
            else:
                print("Sincronizado.")
            entries = load_entries(env)
            if entries is None:
                return None
            continue

        # Obtener credenciales
        payload: dict = {"action": key, "id": entry_id}

        try:
            if key in ("enter", "ctrl-b", "alt-p"):
                payload["password"] = subprocess.check_output(
                    ["rbw", "get", entry_id], text=True, env=env,
                ).strip()

            if key in ("ctrl-u", "ctrl-b", "alt-u"):
                payload["username"] = subprocess.check_output(
                    ["rbw", "get", "--field", "username", entry_id], text=True, env=env,
                ).strip()

            if key == "ctrl-t":
                totp = subprocess.run(
                    ["rbw", "code", entry_id], text=True, capture_output=True, env=env,
                )
                if totp.returncode != 0:
                    print("Esta entrada no tiene TOTP.")
                    input("Presiona Enter para continuar...")
                    continue
                payload["totp"] = totp.stdout.strip()

        except subprocess.CalledProcessError as e:
            print(f"Error obteniendo credenciales: {e}")
            input("Presiona Enter para continuar...")
            continue

        # Registrar uso antes de retornar
        record_usage(entry_id)
        return payload


def handle_result(
    args: list[str],
    result: dict | None,
    target_window_id: int,
    boss,
) -> None:
    if not result:
        return

    window = boss.window_id_map.get(target_window_id) or boss.active_window
    if window is None:
        return

    action   = result.get("action", "")
    password = result.get("password", "")
    username = result.get("username", "")
    totp     = result.get("totp", "")

    if action == "enter":
        window.paste_text(password)
    elif action == "ctrl-u":
        window.paste_text(username)
    elif action == "ctrl-b":
        window.paste_text(f"{username}\t{password}")
    elif action == "ctrl-t":
        set_clipboard_string(totp)
    elif action == "alt-p":
        set_clipboard_string(password)
    elif action == "alt-u":
        set_clipboard_string(username)
