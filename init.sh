#!/usr/bin/env bash
set +xva
set -euo pipefail

keygrip=295FEF9E1BEA886C9AAE2C92D49F4A90C4D60477
key_file="$HOME/private-key.asc"

die() { printf '%s\n' "$*" >&2; exit 1; }
if [[ "$EUID" == 0 ]]; then
    die 'Run without sudo.'
fi

config_dir="$HOME/.config"

platform="$(uname -s)"
case "$platform" in
    Darwin) target=darwinConfigurations.roifewu.system ;;
    Linux) target='homeConfigurations."roifewu@x86_64-linux".activationPackage' ;;
    *) die 'Unsupported platform.' ;;
esac

# Nix
if ! command -v nix >/dev/null; then
    daemon_profile=/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    user_profile="$HOME/.nix-profile/etc/profile.d/nix.sh"
    if [[ ! -f "$daemon_profile" && ! -f "$user_profile" ]]; then
        installer="$(curl -fsSL https://nixos.org/nix/install)"
        sh -c "$installer"
    fi
    if [[ -f "$daemon_profile" ]]; then
        . "$daemon_profile"
    else
        . "$user_profile"
    fi
fi

# Activate
activation="$(
    if [[ -n "${GITHUB_TOKEN-}" ]]; then
        export NIX_CONFIG="${NIX_CONFIG-}"$'\n'"extra-access-tokens = github.com=$GITHUB_TOKEN"
    fi
    nix build --no-update-lock-file --no-link --print-out-paths "git+file://${config_dir}#$target"
)"
if [[ "$platform" == Darwin ]]; then
    sudo -H "$(command -v nix-env)" --profile /nix/var/nix/profiles/system --set "$activation"
    sudo -H "$activation/activate"
else
    "$activation/activate"
fi
export PATH="$HOME/.nix-profile/bin:/run/current-system/sw/bin:$PATH"

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
if [[ "${SHELL:-}" != */fish ]]; then
    if [[ "$platform" == Darwin ]]; then
        fish_path="/run/current-system/sw/bin/fish"
    else
        fish_path="$HOME/.nix-profile/bin/fish"
        if ! grep -Fqx "$fish_path" /etc/shells; then
            printf '%s\n' "$fish_path" | sudo tee -a /etc/shells >/dev/null
        fi
        sudo /usr/sbin/usermod --shell "$fish_path" "$(id -un)"
    fi
    chsh -s "$fish_path"
fi
printf '%s\n' 'Done. Log out and back in.'
