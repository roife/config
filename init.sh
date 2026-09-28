#!/usr/bin/env bash

set -euo pipefail

readonly config_dir="$HOME/.config"

link_config() {
    local src="$1" dst="$2"
    if [[ -e "$dst" && ! -L "$dst" ]]; then
        printf '%s already exists\n' "$dst" >&2
        return 1
    fi
    mkdir -p "$(dirname "$dst")"
    ln -sfn "$src" "$dst"
}

configure_gpg_ssh() {
    local fingerprint="A63DE4903F5E1486A4FBB656E09D9EE312C4C223"
    local keygrip

    command -v gpg >/dev/null || return 0
    keygrip="$(
        gpg --with-colons --with-keygrip --with-subkey-fingerprint \
            --list-secret-keys "$fingerprint" 2>/dev/null |
            awk -F: -v fingerprint="$fingerprint" '
                $1 == "fpr" { selected = ($10 == fingerprint); next }
                selected && $1 == "grp" { print $10; exit }
            ' || true
    )"
    if [[ -z "$keygrip" ]]; then
        printf '%s\n' 'Import the GPG secret key and rerun init.sh.' >&2
        return 0
    fi

    gpg-connect-agent "KEYATTR $keygrip Use-for-ssh: true" /bye >/dev/null
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    gpg --export-ssh-key "${fingerprint}!" >"$HOME/.ssh/gpg-auth.pub"
    chmod 644 "$HOME/.ssh/gpg-auth.pub"
    gpgconf --kill gpg-agent
    gpg-connect-agent /bye >/dev/null
    export SSH_AUTH_SOCK="$(gpgconf --list-dirs agent-ssh-socket)"
}

main() {
    local nix_system rime_dir fish_path brew_installer rime_file
    local emacs_cloned=false

    if ! command -v nix >/dev/null; then
        printf '%s\n' 'Install Nix first: https://nix.dev/install-nix' >&2
        return 1
    fi
    case "$(uname -s):$(uname -m)" in
        Darwin:arm64)
            nix_system=aarch64-darwin
            rime_dir="$HOME/Library/Rime"
            ;;
        Linux:x86_64)
            nix_system=x86_64-linux
            rime_dir="$HOME/.local/share/fcitx5/rime"
            ;;
        *) printf '%s\n' 'Unsupported Nix platform.' >&2; return 1 ;;
    esac

    link_config "$config_dir/.agents" "$HOME/.agents"
    link_config "$config_dir/secrets/authinfo.gpg" "$HOME/.authinfo.gpg"
    mkdir -p "$HOME/.gnupg"
    chmod 700 "$HOME/.gnupg"

    export PATH="$HOME/.local/bin:$PATH"
    nix --extra-experimental-features 'nix-command flakes' \
        run github:nix-community/home-manager/master -- \
        switch --flake "${config_dir}#roifewu@${nix_system}"
    export PATH="$HOME/.nix-profile/bin:$PATH"

    if [[ "$nix_system" == aarch64-darwin ]]; then
        if ! command -v brew >/dev/null; then
            brew_installer="$(curl -fsSL \
                https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            /bin/bash -c "$brew_installer"
            export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
            eval "$(brew shellenv)"
        fi
        brew bundle --file="$config_dir/Brewfile"
        fish_path="$(brew --prefix)/bin/fish"
    else
        fish_path="$(command -v fish)"
    fi
    if ! grep -Fqx "$fish_path" /etc/shells; then
        printf '%s\n' "$fish_path" | sudo tee -a /etc/shells >/dev/null
    fi
    if [[ "${SHELL:-}" != "$fish_path" ]]; then
        chsh -s "$fish_path"
    fi
    configure_gpg_ssh

    if [[ ! -d "$rime_dir/.git" ]]; then
        git clone --depth 1 https://github.com/gaboolic/rime-frost "$rime_dir"
    fi
    for rime_file in "$config_dir"/rime/*; do
        [[ -e "$rime_file" ]] || continue
        ln -sfn "$rime_file" "$rime_dir/"
    done
    curl -fL -o "$rime_dir/wanxiang-lts-zh-hans.gram" \
        https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram

    if [[ ! -d "$HOME/.emacs.d/.git" ]]; then
        git clone https://github.com/roife/.emacs.d.git "$HOME/.emacs.d"
        git -C "$HOME/.emacs.d" remote set-url --push origin \
            git@github.com:roife/.emacs.d.git
        emacs_cloned=true
    fi
    emacs --batch \
        --load "$HOME/.emacs.d/early-init.el" \
        --load "$HOME/.emacs.d/init.el"
    if [[ "$emacs_cloned" == true ]]; then
        if [[ "$nix_system" == aarch64-darwin ]]; then
            if launchctl print "gui/$(id -u)/org.nix-community.home.emacs" >/dev/null 2>&1; then
                launchctl kickstart -k "gui/$(id -u)/org.nix-community.home.emacs"
            fi
        elif command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
            systemctl --user restart emacs.service
        fi
    fi
    tldr -u
}

main "$@"
