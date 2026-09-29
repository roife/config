#!/usr/bin/env bash
set +xva
set -euo pipefail

fingerprint=A63DE4903F5E1486A4FBB656E09D9EE312C4C223
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
keygrip="$(gpg --with-colons --with-keygrip --with-subkey-fingerprint \
    --list-secret-keys "$fingerprint" | awk -F: -v f="$fingerprint" '
        $1 == "fpr" { selected = ($10 == f) }
        selected && $1 == "grp" { print $10; selected = 0 }
    ')"
if [[ -z "$keygrip" ]]; then
    die 'GPG key missing.'
fi
reply="$(gpg-connect-agent "KEYATTR $keygrip Use-for-ssh: true" /bye)"
if [[ "$reply" == *"ERR "* ]]; then
    die "$reply"
fi
gpgconf --reload gpg-agent
export SSH_AUTH_SOCK
SSH_AUTH_SOCK="$(gpgconf --list-dirs agent-ssh-socket)"
unset SSH_AGENT_PID
if [[ -t 0 ]]; then
    gpg-connect-agent updatestartuptty /bye >/dev/null
fi
## Export public key
ssh_key="$(gpg --export-ssh-key "${fingerprint}!" | awk '{print $1, $2}')"
if ! ssh-add -L | awk '{print $1, $2}' | grep -Fx "$ssh_key" >/dev/null; then
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
printf '%s\n' 'Done. Log out and back in.'
