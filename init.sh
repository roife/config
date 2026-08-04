#!/usr/bin/env bash

# Install or update Fish plugins from a Bash shell.
install_fish_plugins() {
    command -v fish >/dev/null 2>&1 || return 127

    fish -c '
        if not functions -q fisher
            curl -fsSL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source
            or exit $status

            fisher install jorgebucaran/fisher
            or exit $status
        end

        fisher update
    '
}

# Restore this user environment.
recover() {
    local is_macos=0
    local rime_user_dir="$HOME/.local/share/fcitx5/rime"

    if [[ "$(uname -s)" == "Darwin" ]]; then
        is_macos=1
        rime_user_dir="$HOME/Library/Rime"
    fi

    if (( is_macos )); then
        ln -sfn "$HOME/.config/Brewfile" "$HOME/Brewfile"
        brew bundle --file="$HOME/.config/Brewfile"
    fi

    mise install || return $?

    install_fish_plugins || return $?

    ln -sfn "$HOME/.config/.gitconfig" "$HOME/.gitconfig"
    ln -sfn "$HOME/.config/.gitignore_global" "$HOME/.gitignore_global"
    ln -sfn "$HOME/.config/.mbsyncrc" "$HOME/.mbsyncrc"

    mkdir -p "$HOME/.codex/skills"
    ln -sfn "$HOME/.config/codex/AGENTS.md" "$HOME/.codex/AGENTS.md"
    for skill_dir in "$HOME/.config/codex/skills"/*/; do
        ln -sfn "$skill_dir" "$HOME/.codex/skills/$(basename "$skill_dir")"
    done

    tldr -u

    mkdir -p "$(dirname "$rime_user_dir")"
    git clone --depth 1 https://github.com/gaboolic/rime-frost "$rime_user_dir"
    for rime_file in "$HOME/.config/rime/"*; do
        ln -sfn "$rime_file" "$rime_user_dir/"
    done
    curl -fL \
        -o "$rime_user_dir/wanxiang-lts-zh-hans.gram" \
        https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram

    git clone git@github.com:roife/.emacs.d.git "$HOME/.emacs.d"
    emacs --batch \
      --load ~/.emacs.d/early-init.el \
      --load ~/.emacs.d/init.el
}

recover
