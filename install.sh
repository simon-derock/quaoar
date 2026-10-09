#!/bin/sh
# installs the quaoar command line tool:
#   curl -fsSL quaoar.philipsimonderock.com/install | sh
#   curl -fsSL https://raw.githubusercontent.com/simon-derock/quaoar/main/install.sh | sh
# it needs uv (Astral's Python tool manager); if uv is missing it runs Astral's own installer first
set -eu

SOURCE="git+https://github.com/simon-derock/quaoar"

say() { printf '%s\n' "$*"; }

fetch() {
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "$1"
  else
    say "quaoar: this installer needs curl or wget" >&2
    exit 1
  fi
}

if ! command -v uv >/dev/null 2>&1; then
  say "quaoar: installing uv first (https://docs.astral.sh/uv/)"
  fetch https://astral.sh/uv/install.sh | sh
  # uv lands in one of these; make it usable for the rest of this script
  PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$HOME/.cargo/bin:$PATH"
  export PATH
fi

say "quaoar: installing the command line tool (Python 3.13 is fetched if needed)"
uv tool install --force --python 3.13 "$SOURCE"

say ""
say "Quaoar is installed. Start it with:  quaoar"
say "  /replay trafiksol    watch a recorded check, no API keys needed"
say "  /help                every command"
if ! command -v quaoar >/dev/null 2>&1; then
  say "If 'quaoar' isn't found, open a new terminal or run: uv tool update-shell"
fi
