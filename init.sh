#!/usr/bin/env bash

# Keep credentials out of tracing and exported variables.
set +xva
set -euo pipefail
ulimit -c 0

config_dir="$HOME/.config"

unset authinfo_passphrase github_token
trap 'unset authinfo_passphrase github_token' EXIT

read_authinfo_passphrase() {
    [[ -r "$config_dir/secrets/.authinfo.gpg" ]] || return 1
    IFS= read -r -s -p '.authinfo.gpg passphrase (hidden): ' authinfo_passphrase </dev/tty
    printf '\n' >/dev/tty
    [[ -n "$authinfo_passphrase" ]]
}

load_github_token() {
    if ! github_token="$(
        gpg --batch --no-tty --pinentry-mode loopback --no-symkey-cache \
            --passphrase-fd 3 --decrypt "$config_dir/secrets/.authinfo.gpg" \
            3< <(printf '%s\n' "$authinfo_passphrase") 2>/dev/null |
            awk '$2 == "api.github.com" { print $NF; exit }'
    )"; then
        printf '%s\n' 'Failed to read GitHub token from authinfo.' >&2
        return 1
    fi
    unset authinfo_passphrase
}

configure_gpg_ssh() {
    local key_file="$HOME/private-key.asc"
    local gpg_fingerprint="A63DE4903F5E1486A4FBB656E09D9EE312C4C223"
    local keygrip

    # Import GPG keys
    mkdir -p "$HOME/.gnupg" && chmod 700 "$HOME/.gnupg"
    if [[ -f "$key_file" ]]; then
        gpg --import "$key_file"
    elif ! gpg --with-colons --list-secret-keys "$gpg_fingerprint" |
        grep -E '^(sec|ssb):' >/dev/null; then
        printf 'GPG secret key not imported; place a backup at %s and rerun init.sh.\n' "$key_file" >&2
        return 1
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
        printf '%s\n' 'Target GPG private material or smart-card reference missing. Restore the target secret key and rerun init.sh.' >&2
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

    # Bootstrap SSH support before Home Manager supplies the agent config.
    gpgconf --kill gpg-agent
    gpg-agent --daemon --enable-ssh-support >/dev/null
    SSH_AUTH_SOCK="$(gpgconf --list-dirs agent-ssh-socket)"
    export SSH_AUTH_SOCK
    if [[ -t 0 ]]; then
        GPG_TTY="$(tty)"
        export GPG_TTY
        gpg-connect-agent updatestartuptty /bye >/dev/null
    fi
}

# Register Fish as a login shell and select it for the account.
configure_fish() {
    local fish_path="$HOME/.nix-profile/bin/fish"
    local login_shell
    if [[ ! -x "$fish_path" ]]; then
        printf 'Home Manager did not install Fish at %s\n' "$fish_path" >&2
        return 1
    fi
    if ! grep -Fqx "$fish_path" /etc/shells; then
        printf '%s\n' "$fish_path" | sudo tee -a /etc/shells >/dev/null
    fi
    # $SHELL is inherited from the old session even after chsh succeeds.
    if [[ "$nix_system" == aarch64-darwin ]]; then
        login_shell="$(dscl . -read "/Users/$(id -un)" UserShell |
            awk '$1 == "UserShell:" { print $2 }')"
    else
        login_shell="$(getent passwd "$(id -u)" | awk -F: '{ print $7 }')"
    fi
    if [[ "$login_shell" != "$fish_path" ]]; then
        chsh -s "$fish_path"
    fi
}

case "$(uname -s):$(uname -m)" in
    Darwin:arm64)
        nix_system=aarch64-darwin
        ;;
    Linux:x86_64)
        nix_system=x86_64-linux
        ;;
    *) printf '%s\n' 'Unsupported platform.' >&2; exit 1 ;;
esac

read_authinfo_passphrase

# Install macOS packages, including GnuPG, before importing the key.
if [[ "$nix_system" == aarch64-darwin ]]; then
    if ! command -v brew >/dev/null; then
        brew_installer="$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        /bin/bash -c "$brew_installer"

        brew_environment="$(/opt/homebrew/bin/brew shellenv)"
        eval "$brew_environment"
    fi
    brew bundle --file="$config_dir/Brewfile"
fi

# Load GPG keys and configure ssh
configure_gpg_ssh

# Clone Emacs configuration before Home Manager starts its service.
if [[ ! -e "$config_dir/emacs/.git" ]]; then
    git clone git@github.com:roife/.emacs.d.git "$config_dir/emacs"
fi

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

# Build and activate the local Home Manager configuration.
load_github_token

home_activation="$(
    # Only the descriptor path is exported, not the token.
    NIX_CONFIG="${NIX_CONFIG-}"$'\ninclude /dev/fd/3' \
    nix --extra-experimental-features 'nix-command flakes' \
        build --no-update-lock-file --no-link --print-out-paths \
        "git+file://${config_dir}#homeConfigurations.\"roifewu@${nix_system}\".activationPackage" \
        3< <(printf 'extra-access-tokens = github.com=%s\n' "$github_token")
)"
unset github_token
"$home_activation/activate"
export PATH="$HOME/.nix-profile/bin:$PATH"

configure_fish
