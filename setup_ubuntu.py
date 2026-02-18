#!/usr/bin/env python3
"""
Setup script for new Ubuntu install.
Steps are defined in STEPS; add or edit entries there to change behavior.
Shows progress, per-step success/failure, and a final summary.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable

HOME = os.path.expanduser("~")

# ---------------------------------------------------------------------------
# Step definitions — add or edit steps here
# ---------------------------------------------------------------------------

# Optional: set to True to not abort the script when this step fails
# Skip: use "skip_if" with a callable that returns True to skip the step
# Custom: use "run" with a callable instead of "commands"


def _all_steps() -> list[dict]:
    return [
        {
            "name": "Install apt packages",
            "commands": [
                "sudo apt update",
                "sudo apt install -y chrome-gnome-shell curl git vim zsh fish "
                "fonts-powerline xfce4-terminal nodejs npm locate gnome-tweaks "
                "gnome-shell-extensions libfuse2t64 build-essential ffmpeg cmake ranger",
            ],
        },
        {"name": "Update locate DB", "commands": ["sudo updatedb"]},
        {
            "name": "Create SSH key (ed25519)",
            "skip_if": lambda: os.path.exists(f"{HOME}/.ssh/id_ed25519"),
            "commands": [
                f'ssh-keygen -t ed25519 -C "aniket.dhere@gmail.com" -f {HOME}/.ssh/id_ed25519 -N ""',
            ],
        },
        {
            "name": "Start ssh-agent and add key",
            "commands": [
                'eval "$(ssh-agent -s)" && ssh-add ~/.ssh/id_ed25519',
            ],
        },
        {
            "name": "Show SSH public key",
            "show_output": True,
            "commands": ["cat ~/.ssh/id_ed25519.pub"],
        },
        {
            "name": "Git config (name, email, editor)",
            "commands": [
                'git config --global user.name "Aniket Dhere"',
                'git config --global user.email "aniket.dhere@gmail.com"',
                'git config --global core.editor "vim"',
                'git config --global init.defaultBranch main',
            ],
        },
        {
            "name": "Install Nerd Font (DroidSansMono)",
            "commands": [
                "mkdir -p ~/.local/share/fonts",
                "cd ~/.local/share/fonts && curl -fLO "
                "https://github.com/ryanoasis/nerd-fonts/raw/HEAD/patched-fonts/DroidSansMono/DroidSansMNerdFont-Regular.otf",
            ],
        },
        {
            "name": "Install Oh My Zsh",
            "commands": [
                'RUNZSH=no sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"',
            ],
        },
        {
            "name": "Install Oh My Fish",
            "optional": True,
            "commands": [
                "curl -sS https://raw.githubusercontent.com/oh-my-fish/oh-my-fish/master/bin/install | fish",
            ],
        },
        {
            "name": "Install Fish theme (bobthefish)",
            "optional": True,
            "commands": [
                "fish -c 'omf install bobthefish'",
            ],
        },
        {
            "name": "Configure Fish theme (nerd fonts)",
            "run": _append_fish_theme,
        },
        {
            "name": "Clone update-cursor and move to /opt",
            "commands": [
                "cd ~ && git clone git@github.com:s0m3OnE47/update-cursor.git",
                "sudo mv ~/update-cursor /opt",
            ],
        },
        {
            "name": "Append PATH and autocomplete to ~/.zshrc",
            "run": _append_zshrc,
        },
        {
            "name": "Run update-cursor",
            "optional": True,
            "commands": ["/opt/update-cursor/bin/update-cursor"],
        },
        {
            "name": "Clone zsh-autocomplete and move to /opt",
            "commands": [
                "cd ~ && git clone --depth 1 https://github.com/marlonrichert/zsh-autocomplete.git",
                "sudo mv ~/zsh-autocomplete /opt",
            ],
        },
    ]


def _append_fish_theme() -> bool:
    """Append bobthefish theme settings to Fish config."""
    fish_config = f"{HOME}/.config/fish/config.fish"
    theme_lines = "\nset -g theme_powerline_fonts no\nset -g theme_nerd_fonts yes\n"
    os.makedirs(os.path.dirname(fish_config), exist_ok=True)
    try:
        with open(fish_config) as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    if "theme_powerline_fonts" in content:
        return True
    with open(fish_config, "a") as f:
        f.write(theme_lines)
    return True


def _append_zshrc() -> bool:
    """Append PATH and zsh-autocomplete source to ~/.zshrc."""
    zshrc_path = f"{HOME}/.zshrc"
    block = """
# Added by setup_ubuntu.py
export PATH="$HOME/.local/bin:$PATH"
export PATH="/opt/update-cursor/bin:$PATH"
source /opt/zsh-autocomplete/zsh-autocomplete.plugin.zsh
"""
    with open(zshrc_path, "a") as f:
        f.write(block)
    return True


# Build flat list of steps (so we can index and count)
def _build_steps() -> list[dict]:
    return _all_steps()


STEPS = _build_steps()

# ---------------------------------------------------------------------------
# Runner: progress, run, report
# ---------------------------------------------------------------------------


@dataclass
class Result:
    step_name: str
    step_index: int
    total: int
    status: str  # "ok" | "skipped" | "failed"
    message: str = ""
    optional: bool = False


def _run_cmd(cmd: str, env: dict, capture: bool = True) -> tuple[bool, str]:
    """Run a single command. Return (success, stderr_or_empty). If not capture, stdout is shown."""
    r = subprocess.run(
        cmd,
        shell=True,
        cwd=HOME,
        env=env,
        capture_output=capture,
        text=True,
    )
    if capture:
        return (r.returncode == 0, (r.stderr or "").strip() or (r.stdout or "").strip())
    return (r.returncode == 0, "")


def _run_step(step: dict, index: int, total: int, env: dict) -> Result:
    name = step["name"]
    optional = step.get("optional", False)

    if step.get("skip_if"):
        if step["skip_if"]():
            return Result(
                step_name=name,
                step_index=index,
                total=total,
                status="skipped",
                message="condition matched",
            )

    if "run" in step:
        fn: Callable[[], bool] = step["run"]
        try:
            ok = fn()
            return Result(
                step_name=name,
                step_index=index,
                total=total,
                status="ok" if ok else "failed",
                message="" if ok else "run() returned False",
                optional=optional,
            )
        except Exception as e:
            return Result(
                step_name=name,
                step_index=index,
                total=total,
                status="failed",
                message=str(e),
                optional=optional,
            )

    commands = step.get("commands", [])
    # Show command output for steps that print something useful (e.g. SSH pub key)
    show_output = step.get("show_output", False)
    for cmd in commands:
        print(f"    $ {cmd}")
        ok, err = _run_cmd(cmd, env, capture=not show_output)
        if not ok:
            return Result(
                step_name=name,
                step_index=index,
                total=total,
                status="failed",
                message=err or f"exit code non-zero",
                optional=optional,
            )
    return Result(
        step_name=name,
        step_index=index,
        total=total,
        status="ok",
        optional=optional,
    )


def _print_result(r: Result) -> None:
    total = r.total
    n = r.step_index
    name = r.step_name
    if r.status == "ok":
        print(f"  [{n}/{total}] {name} — OK")
    elif r.status == "skipped":
        print(f"  [{n}/{total}] {name} — SKIPPED ({r.message})")
    elif r.status == "failed":
        opt = " (optional)" if r.optional else ""
        print(f"  [{n}/{total}] {name} — FAILED{opt}")
        if r.message:
            for line in r.message.strip().split("\n")[:5]:
                print(f"      {line}")


def main() -> None:
    env = {**os.environ, "HOME": HOME}
    total = len(STEPS)
    results: list[Result] = []

    print("=" * 60)
    print(" Ubuntu setup script")
    print("=" * 60)

    for i, step in enumerate(STEPS, start=1):
        name = step["name"]
        print(f"\n[{i}/{total}] {name} …")
        r = _run_step(step, i, total, env)
        results.append(r)
        _print_result(r)

        if r.status == "failed" and not r.optional:
            print("\n>>> Aborting due to failed required step.")
            _print_summary(results, total)
            sys.exit(1)

    _print_summary(results, total)
    print("\n>>> Done. Restart your shell or run: source ~/.zshrc")
    print(">>> Add your SSH public key to GitHub if needed (it was printed above).")


def _print_summary(results: list[Result], total: int) -> None:
    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    failed_optional = sum(1 for r in results if r.status == "failed" and r.optional)
    failed_required = failed - failed_optional

    print("\n" + "=" * 60)
    print(" Summary")
    print("=" * 60)
    print(f"  Steps performed (OK):  {ok}/{total}")
    print(f"  Skipped:               {skipped}")
    print(f"  Failed (optional):     {failed_optional}")
    if failed_required:
        print(f"  Failed (required):     {failed_required}")
    print("=" * 60)


if __name__ == "__main__":
    main()
