#!/usr/bin/env bash

set -euo pipefail

config="$HOME/.config"

link_config() {
    [[ ! -e "$2" || -L "$2" ]] || {
        printf '%s already exists\n' "$2" >&2
        return 1
    }
    mkdir -p "$(dirname "$2")"
    ln -sfn "$1" "$2"
}

main() {
    local rime="$HOME/.local/share/fcitx5/rime"
    local fish_path rime_file

    link_config "$config/.gitconfig" "$HOME/.gitconfig"
    link_config "$config/.gitignore_global" "$HOME/.gitignore_global"
    link_config "$config/.mbsyncrc" "$HOME/.mbsyncrc"
    link_config "$config/.agents" "$HOME/.agents"

    export PATH="$HOME/.local/bin:$PATH"

    command -v mise >/dev/null || curl -fsSL https://mise.run | sh
    mise install
    eval "$(mise activate bash)"

    if [[ "$(uname)" == Darwin ]]; then
        rime="$HOME/Library/Rime"
        if ! command -v brew >/dev/null; then
            /bin/bash -c "$(curl -fsSL \
                https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
            eval "$(brew shellenv)"
        fi
        link_config "$config/Brewfile" "$HOME/Brewfile"
        brew bundle --file="$config/Brewfile"
    fi

    fish_path="$(command -v fish)"
    grep -Fqx "$fish_path" /etc/shells || \
        printf '%s\n' "$fish_path" | sudo tee -a /etc/shells >/dev/null
    [[ "${SHELL:-}" == "$fish_path" ]] || chsh -s "$fish_path"
    fish -c '
        functions -q fisher
        or curl -fsSL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source
        or exit $status
        fisher update
    '

    tldr -u

    [[ -d "$rime/.git" ]] || \
        git clone --depth 1 https://github.com/gaboolic/rime-frost "$rime"
    for rime_file in "$config"/rime/*; do
        [[ -e "$rime_file" ]] && ln -sfn "$rime_file" "$rime/"
    done
    curl -fL -o "$rime/wanxiang-lts-zh-hans.gram" \
        https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram

    [[ -d "$HOME/.emacs.d/.git" ]] || \
        git clone git@github.com:roife/.emacs.d.git "$HOME/.emacs.d"
    emacs --batch \
        --load "$HOME/.emacs.d/early-init.el" \
        --load "$HOME/.emacs.d/init.el"
}

main "$@"
