#!/usr/bin/env bash
# Make the `cm` command available in every terminal, or take it away again.
#
# A thin wrapper around uv's own tool installer:
#
#   uv tool install --editable <this repo>   puts `cm` in uv's tool folder, with its own
#                                            environment, separate from the repo's .venv
#   uv tool update-shell                     adds that folder to your PATH
#
# The install is editable, so `cm` runs the code in this folder: a `git pull` takes effect
# without reinstalling, and the default workspace stays <this repo>/workspace. Set
# CM_WORKSPACE to keep it somewhere else.
#
# Usage:
#   ./install.sh                 install, and add uv's tool folder to PATH
#   ./install.sh --uninstall     remove the cm command (repo, .venv and workspace are left alone)
#   ./install.sh --no-path       install without touching PATH
#   ./install.sh --native-tls    use the system's certificates, for networks that inspect HTTPS
#
# Works on Linux, macOS, and Git Bash on Windows.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE="content-machine"            # the project name in pyproject.toml

uninstall=false
touch_path=true
tls_args=()

fail() {
    echo "error: $1" >&2
    exit 1
}

for arg in "$@"; do
    case "$arg" in
        --uninstall)  uninstall=true ;;
        --no-path)    touch_path=false ;;
        --native-tls) tls_args=(--native-tls) ;;
        -h|--help)    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)            fail "unknown option $arg (try --help)" ;;
    esac
done

command -v uv >/dev/null 2>&1 || fail "uv is not installed. Install it from https://docs.astral.sh/uv/getting-started/installation/ and run this again."

if $uninstall; then
    uv tool uninstall "$PACKAGE" || fail "uv could not remove $PACKAGE (is it installed? try: uv tool list)"
    echo "Removed the cm command. The repo, its .venv and your workspace are untouched."
    exit 0
fi

echo "Installing cm from $REPO"
# ${a[@]+"${a[@]}"} expands an empty array to nothing; plain "${a[@]}" fails under set -u
# on the bash 3.2 macOS still ships.
uv tool install --editable "$REPO" --force ${tls_args[@]+"${tls_args[@]}"} \
    || fail "uv could not install $PACKAGE. If downloads failed on a work network, run again with --native-tls."

if $touch_path; then
    uv tool update-shell \
        || fail "cm is installed, but PATH could not be updated. Add the folder from 'uv tool dir --bin' to PATH yourself."
fi

bin="$(uv tool dir --bin)"
cm="$bin/cm"
[ -e "$cm" ] || [ -e "$cm.exe" ] || fail "uv reported success, but $cm is missing. Run 'uv tool list' to see what was installed."
[ -e "$cm" ] || cm="$cm.exe"          # Git Bash on Windows
"$cm" --help >/dev/null || fail "$cm is installed but does not run. Try '$cm --help' to see why."

echo
echo "cm is installed in $bin"
if $touch_path; then
    echo "Open a new terminal, then run: cm where    (shows the workspace)"
    echo "                               cm serve    (starts the app)"
else
    echo "PATH was left alone: add $bin to it to use 'cm' anywhere."
fi
