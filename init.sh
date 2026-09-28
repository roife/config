#!/usr/bin/env bash

# Stop on errors, unset variables, and failed pipelines.
set -euo pipefail

# Use the configuration checkout in the home directory.
config_dir="$HOME/.config"

# Let GPG authenticate SSH when the configured secret key is available.
configure_gpg_ssh() {
    local fingerprint="A63DE4903F5E1486A4FBB656E09D9EE312C4C223"
    local keygrip

    mkdir -p "$HOME/.gnupg"
    chmod 700 "$HOME/.gnupg"

    command -v gpg >/dev/null || return 0
    # Select the keygrip for this fingerprint from all secret keys.
    keygrip="$(
        gpg --with-colons --with-keygrip --with-subkey-fingerprint \
            --list-secret-keys |
            awk -F: -v fingerprint="$fingerprint" '
                $1 == "fpr" { selected = ($10 == fingerprint); next }
                selected && $1 == "grp" { print $10; exit }
            '
    )"
    if [[ -z "$keygrip" ]]; then
        printf '%s\n' 'Import the GPG secret key and run init.sh --configure-gpg-ssh.' >&2
        return 0
    fi

    gpg-connect-agent "KEYATTR $keygrip Use-for-ssh: true" /bye >/dev/null
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    gpg --export-ssh-key "${fingerprint}!" >"$HOME/.ssh/gpg-auth.pub"
    chmod 644 "$HOME/.ssh/gpg-auth.pub"

    # Restart the agent so its SSH socket uses the updated key attribute.
    gpgconf --kill gpg-agent
    gpg-connect-agent /bye >/dev/null
    export SSH_AUTH_SOCK="$(gpgconf --list-dirs agent-ssh-socket)"
}

# Run only GPG SSH setup after importing the secret key.
if [[ "${1:-}" == --configure-gpg-ssh ]]; then
    configure_gpg_ssh
    exit
fi

# Select the Home Manager target and Rime data directory for this platform.
case "$(uname -s):$(uname -m)" in
    Darwin:arm64)
        nix_system=aarch64-darwin
        rime_dir="$HOME/Library/Rime"
        ;;
    Linux:x86_64)
        nix_system=x86_64-linux
        rime_dir="$HOME/.local/share/fcitx5/rime"
        ;;
    *) printf '%s\n' 'Unsupported platform.' >&2; exit 1 ;;
esac

# Install Nix when absent and make it available to this running shell.
if ! command -v nix >/dev/null; then
    nix_daemon_profile=/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    nix_user_profile="$HOME/.nix-profile/etc/profile.d/nix.sh"
    if [[ ! -f "$nix_daemon_profile" && ! -f "$nix_user_profile" ]]; then
        curl -fsSL https://nixos.org/nix/install | sh
    fi
    # The installer configures future shells; load the profile here as well.
    if [[ -f "$nix_daemon_profile" ]]; then
        . "$nix_daemon_profile"
    else
        . "$nix_user_profile"
    fi
fi

ln -sfn "$config_dir/.agents" "$HOME/.agents"
ln -sfn "$config_dir/secrets/.authinfo.gpg" "$HOME/.authinfo.gpg"

# Clone Emacs configuration before Home Manager starts its service.
if [[ ! -d "$config_dir/emacs/.git" ]]; then
    git clone https://github.com/roife/.emacs.d.git "$config_dir/emacs"
    git -C "$config_dir/emacs" remote set-url --push origin \
        git@github.com:roife/.emacs.d.git
fi

# Apply Home Manager and use the binaries it installs in this process.
nix --extra-experimental-features 'nix-command flakes' \
    run github:nix-community/home-manager/master -- \
    switch --flake "${config_dir}#roifewu@${nix_system}"
export PATH="$HOME/.nix-profile/bin:$PATH"

# Install macOS packages. Home Manager installs Fish on both platforms.
if [[ "$nix_system" == aarch64-darwin ]]; then
    if ! command -v brew >/dev/null; then
        /bin/bash -c "$(curl -fsSL \
            https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    brew bundle --file="$config_dir/Brewfile"
fi

# Register Fish as a login shell and select it for the account.
fish_path="$HOME/.nix-profile/bin/fish"
if [[ ! -x "$fish_path" ]]; then
    printf 'Home Manager did not install Fish at %s\n' "$fish_path" >&2
    exit 1
fi
if ! grep -Fqx "$fish_path" /etc/shells; then
    printf '%s\n' "$fish_path" | sudo tee -a /etc/shells >/dev/null
fi
if [[ "${SHELL:-}" != "$fish_path" ]]; then
    chsh -s "$fish_path"
fi

# Install Rime Frost, overlay local settings, and refresh its language model.
if [[ ! -d "$rime_dir/.git" ]]; then
    mkdir -p "${rime_dir%/*}"
    git clone --depth 1 https://github.com/gaboolic/rime-frost "$rime_dir"
fi
for rime_file in "$config_dir"/rime/*; do
    ln -sfn "$rime_file" "$rime_dir/"
done
curl -fL -o "$rime_dir/wanxiang-lts-zh-hans.gram" \
    https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram

# Refresh tealdeer's local documentation cache.
tldr -u
