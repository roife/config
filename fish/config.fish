# Platform and environment
if test (uname -s) = Darwin
    set -g is_macos 1
    set -g rime_user_dir "$HOME/Library/Rime"
else
    set -g is_macos 0
    set -g rime_user_dir "$HOME/.local/share/fcitx5/rime"
end
fish_add_path --global "$HOME/.cargo/bin" "$HOME/.local/bin"

if command -q mise
    mise activate fish | source

    if mise where java@latest >/dev/null 2>&1
        set -gx JAVA_HOME (mise where java@latest)
    end
    if mise where java@21 >/dev/null 2>&1
        set -gx JDTLS_JAVA_HOME (mise where java@21)
    end
end

status is-interactive; or return

if functions -q theme_gruvbox
    theme_gruvbox dark medium
end

set -gx EDITOR 'emacsclient --alternate-editor=""'
set -gx GIT_EDITOR "$EDITOR"

# Prompt
function fish_prompt --description 'Show login context and working directory'
    set -l last_status $status

    if set -q SSH_CONNECTION; or set -q SUDO_USER; or fish_is_root_user
        set_color cyan
        printf '%s@%s ' "$USER" (prompt_hostname)
    end

    set_color (test $last_status -eq 0; and echo green; or echo red)
    printf '%s ' (prompt_pwd --dir-length=0)
    set_color normal
end

# Commands
function e --wraps emacsclient --description 'Open files in Emacs'
    set -q argv[1]; or set argv .
    command emacsclient $argv
end

function ec --wraps emacsclient --description 'Open files in a new Emacs frame'
    set -q argv[1]; or set argv .
    command emacsclient -c $argv
end

function install_fish_plugins --description 'Install or update Fish plugins'
    if not functions -q fisher
        curl -fsSL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source
        or return $status

        fisher install jorgebucaran/fisher
        or return $status
    end

    fisher update
end

function recover --description 'Restore this user environment'
    install_fish_plugins

    if test "$is_macos" -eq 1
        ln -sfn "$HOME/.config/Brewfile" "$HOME/Brewfile"
        brew bundle --file="$HOME/.config/Brewfile"
    end

    mise install
    or return $status

    ln -sfn "$HOME/.config/.gitconfig" "$HOME/.gitconfig"
    ln -sfn "$HOME/.config/.gitignore_global" "$HOME/.gitignore_global"

    ln -sfn "$HOME/.config/.mbsyncrc" "$HOME/.mbsyncrc"

    tldr -u

    mkdir -p (path dirname "$rime_user_dir")
    git clone --depth 1 https://github.com/gaboolic/rime-frost "$rime_user_dir"
    for rime_file in "$HOME/.config/rime/"*
        ln -sfn "$rime_file" "$rime_user_dir/"
    end
    curl -fL \
        -o "$rime_user_dir/wanxiang-lts-zh-hans.gram" \
        https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram

    git clone git@github.com:roife/.emacs.d.git "$HOME/.emacs.d"
    emacs --batch -Q --load "$HOME/.emacs.d/init.el"
end

# Interactive shell
set -g fish_greeting

abbr --add l 'll'
abbr --add rm 'rm -i'
abbr --add codex 'codex --disable apps --disable plugins'

abbr --add brewdump 'brew bundle dump --file="$HOME/.config/Brewfile"'
abbr --add brewrestore 'brew bundle --file="$HOME/.config/Brewfile"'

set -l hooks \
    'fzf --fish' \
    'direnv hook fish'
for hook in $hooks
    set -l parts (string split ' ' -- $hook)
    command -q $parts[1]; or continue
    $parts 2>/dev/null | source
end
