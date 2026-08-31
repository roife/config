# Platform and environment
if command -q mise
    mise activate fish | source
end

fish_add_path --global --move "$HOME/.cargo/bin" "$HOME/.local/bin"

status is-interactive; or return

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
    command emacsclient -t $argv
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

# Interactive shell
set -g fish_greeting

abbr --add l 'll -a'
abbr --add la 'll -a'
abbr --add rm 'rm -i'
abbr --add codex 'codex --disable apps --disable plugins'

set -l hooks \
    'direnv hook fish'
for hook in $hooks
    set -l parts (string split ' ' -- $hook)
    command -q $parts[1]; or continue
    $parts 2>/dev/null | source
end

source "$HOME/.emacs.d/straight/repos/ezf/scripts/ezf.fish"

bind \ct ezf-file-widget
bind -M insert \ct ezf-file-widget
bind \cr ezf-history-widget
bind -M insert \cr ezf-history-widget
bind \ec ezf-cd-widget
bind -M insert \ec ezf-cd-widget
bind \ex ezf-dispatch-widget
bind -M insert \ex ezf-dispatch-widget
