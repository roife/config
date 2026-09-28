#!/usr/bin/env bash

# Keep credentials out of tracing and exported variables.
set +xva
set -euo pipefail
ulimit -c 0

config_dir="$HOME/.config"

# Retain an optional token only in this shell, not in child environments.
unset github_token
github_token="${GITHUB_TOKEN-}"
unset GITHUB_TOKEN

configure_gpg_ssh() {
    local key_file="$HOME/private-key.asc"
    local gpg_fingerprint="A63DE4903F5E1486A4FBB656E09D9EE312C4C223"
    local keygrip

    # Import GPG keys
    mkdir -p "$HOME/.gnupg" && chmod 700 "$HOME/.gnupg"
    if [[ -f "$key_file" ]]; then
        gpg --import "$key_file"
    fi

    # Find the target keygrip only for local private material or a card reference.
    keygrip="$(
        gpg --with-colons --with-keygrip --with-subkey-fingerprint \
            --list-secret-keys |
            awk -F: -v fingerprint="$gpg_fingerprint" '
                $1 == "sec" || $1 == "ssb" {
                    available = ($15 == "+" || $15 ~ /^[0-9A-Fa-f]+$/)
                    selected = 0
                    next
                }
                $1 == "fpr" { selected = ($10 == fingerprint); next }
                selected && available && $1 == "grp" { print $10; selected = 0 }
            '
    )"
    if [[ -z "$keygrip" ]]; then
        printf 'Target GPG private material or smart-card reference missing. Place a backup at %s or run gpg --card-status, then rerun init.sh.\n' "$key_file" >&2
        return 1
    fi
    # Only delete the supplied backup after import and secret-key verification.
    if [[ -f "$key_file" ]]; then
        rm -- "$key_file"
    fi

    gpg-connect-agent "KEYATTR $keygrip Use-for-ssh: true" /bye >/dev/null
    mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
    gpg --export-ssh-key "${gpg_fingerprint}!" >"$HOME/.ssh/gpg-auth.pub"
    chmod 644 "$HOME/.ssh/gpg-auth.pub"

    # Reload the agent after enabling SSH access.
    gpgconf --reload gpg-agent
    if [[ -t 0 ]]; then
        GPG_TTY="$(tty)"
        export GPG_TTY
        gpg-connect-agent updatestartuptty /bye >/dev/null
    fi
}

platform="$(uname -s)"
case "$platform:$(uname -m)" in
    Darwin:arm64)
        nix_target=darwinConfigurations.roifewu.system
        ;;
    Linux:x86_64)
        nix_target='homeConfigurations."roifewu@x86_64-linux".activationPackage'
        ;;
    *) printf '%s\n' 'Unsupported platform.' >&2; exit 1 ;;
esac

# Install Nix when absent and make it available to this running shell.
if ! command -v nix >/dev/null; then
    nix_daemon_profile=/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    nix_user_profile="$HOME/.nix-profile/etc/profile.d/nix.sh"
    if [[ ! -f "$nix_daemon_profile" && ! -f "$nix_user_profile" ]]; then
        nix_installer="$(curl -fsSL https://nixos.org/nix/install)"
        sh -c "$nix_installer"
    fi
    # The installer configures future shells; load the profile here as well.
    if [[ -f "$nix_daemon_profile" ]]; then
        . "$nix_daemon_profile"
    else
        . "$nix_user_profile"
    fi
fi

# Clone without SSH credentials, then use SSH for future fetches and pushes.
if [[ ! -e "$config_dir/emacs/.git" ]]; then
    git clone https://github.com/roife/.emacs.d.git "$config_dir/emacs"
fi
git -C "$config_dir/emacs" remote set-url origin git@github.com:roife/.emacs.d.git

activation="$(
    if [[ -n "$github_token" ]]; then
        # Only the descriptor path is exported, not the token.
        export NIX_CONFIG="${NIX_CONFIG-}"$'\ninclude /dev/fd/3'
        exec 3< <(printf 'extra-access-tokens = github.com=%s\n' "$github_token")
    fi
    nix build --no-update-lock-file --no-link --print-out-paths \
        "git+file://${config_dir}#$nix_target"
)"
unset github_token

# On macOS, nix-darwin activates Homebrew and Home Manager together.
if [[ "$platform" == Darwin ]]; then
    # Match darwin-rebuild switch: record a system generation, then activate it.
    sudo "$(command -v nix-env)" --profile /nix/var/nix/profiles/system --set "$activation"
    sudo "$activation/activate"
else
    "$activation/activate"
fi
export PATH="$HOME/.nix-profile/bin:$PATH"

# Load GPG keys and configure SSH independently of GitHub API authentication.
configure_gpg_ssh

# nix-darwin registers Fish on macOS; standalone Home Manager cannot do so.
if [[ "$platform" == Darwin ]]; then
    fish_path=/run/current-system/sw/bin/fish
else
    fish_path="$HOME/.nix-profile/bin/fish"
    if ! grep -Fqx "$fish_path" /etc/shells; then
        printf '%s\n' "$fish_path" | sudo tee -a /etc/shells >/dev/null
    fi
fi
chsh -s "$fish_path"
