#!/usr/bin/env bash
set +xva
set -euo pipefail

config_dir="$HOME/.config"
keygrip=295FEF9E1BEA886C9AAE2C92D49F4A90C4D60477
key_file="$HOME/secret-keys.asc"

die() { printf '%s\n' "$*" >&2; exit 1; }
if [[ "$EUID" == 0 ]]; then
    die 'Run without sudo.'
fi

# Ask for the administrator password once and keep the sudo timestamp fresh
# until this script exits (the Nix installer, Homebrew setup, casks and the
# login shell change all need it).
sudo -v
while sleep 60; do sudo -n -v || exit; done 2>/dev/null &
sudo_keepalive=$!
trap 'kill "$sudo_keepalive" 2>/dev/null' EXIT

platform="$(uname -s)"
case "$platform" in
    Darwin) system=aarch64-darwin ;;
    Linux) system=x86_64-linux ;;
    *) die 'Unsupported platform.' ;;
esac
target="homeConfigurations.\"$(id -un)@$system\".activationPackage"

# Nix
daemon_profile=/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
if ! command -v nix >/dev/null; then
    if [[ ! -f "$daemon_profile" ]]; then
        installer="$(curl -fsSL https://nixos.org/nix/install)"
        sh -c "$installer" -- --daemon
    fi
    . "$daemon_profile"
fi

# Activate
activation="$(
    if [[ -n "${GITHUB_TOKEN-}" ]]; then
        export NIX_CONFIG="${NIX_CONFIG-}"$'\n'"extra-access-tokens = github.com=$GITHUB_TOKEN"
    fi
    nix build --no-update-lock-file --no-link --print-out-paths "git+file://${config_dir}#$target"
)"
"$activation/activate"
export PATH="$HOME/.nix-profile/bin:$PATH"

# GPG / SSH
## Import key
install -d -m 700 "$HOME/.gnupg" "$HOME/.ssh"
export GPG_TTY
if [[ -t 0 ]]; then
    GPG_TTY="$(tty)"
fi
if [[ -f "$key_file" ]]; then
    gpg --import "$key_file"
fi
## Add to SSH
if ! gpg-connect-agent "KEYATTR $keygrip Use-for-ssh:" /bye | grep -Fxq 'D true'; then
    reply="$(gpg-connect-agent "KEYATTR $keygrip Use-for-ssh: true" /bye)"
    if [[ "$reply" == *"ERR "* ]]; then
        die "$reply"
    fi
fi
gpgconf --reload gpg-agent
export SSH_AUTH_SOCK
SSH_AUTH_SOCK="$(gpgconf --list-dirs agent-ssh-socket)"
unset SSH_AGENT_PID
if [[ -t 0 ]]; then
    gpg-connect-agent updatestartuptty /bye >/dev/null
fi
## Export public key
ssh_reply="$(gpg-connect-agent "READKEY --format=ssh $keygrip" /bye)"
read -r tag key_type key_data _ <<< "$ssh_reply"
if [[ "$tag" != D || "$key_type" != ssh-* || -z "$key_data" ]]; then
    die 'SSH public key unavailable.'
fi
ssh_key="$key_type $key_data"
if ! ssh-add -L | cut -d ' ' -f1,2 | grep -Fxq "$ssh_key"; then
    die 'SSH key unavailable.'
fi
printf '%s\n' "$ssh_key" >"$HOME/.ssh/gpg-auth.pub"
chmod 644 "$HOME/.ssh/gpg-auth.pub"
rm -f -- "$key_file"

# Emacs configuration
if [[ ! -e "$config_dir/emacs/.git" ]]; then
    checkout="$(mktemp -d)"
    git clone https://github.com/roife/.emacs.d.git "$checkout"
    mkdir -p "$config_dir/emacs"
    cp -a "$checkout/." "$config_dir/emacs/"
    rm -rf -- "$checkout"
fi
git -C "$config_dir/emacs" remote set-url origin git@github.com:roife/.emacs.d.git

# Restart
if [[ "$platform" == Darwin ]]; then
    launchctl setenv SSH_AUTH_SOCK "$SSH_AUTH_SOCK"
    launchctl setenv PATH "$PATH"
    launchctl kickstart -k "gui/$(id -u)/org.nix-community.home.emacs"
else
    systemctl --user import-environment SSH_AUTH_SOCK PATH
    systemctl --user --no-block restart emacs.service
fi

# Login shell
fish_path="$HOME/.nix-profile/bin/fish"
if [[ ! -f /etc/shells ]] || ! grep -Fqx "$fish_path" /etc/shells; then
    printf '%s\n' "$fish_path" | sudo tee -a /etc/shells >/dev/null
fi
if [[ "${SHELL:-}" != "$fish_path" ]]; then
    if [[ "$platform" == Linux ]]; then
        sudo usermod --shell "$fish_path" "$(id -un)" || true
    fi
    sudo chsh -s "$fish_path" "$(id -un)"
fi

printf '%s\n' 'Done. Log out and back in.'
