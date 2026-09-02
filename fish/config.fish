# Platform and environment
if command -q mise
    mise activate fish | source
end

fish_add_path --global --move "$HOME/.cargo/bin" "$HOME/.local/bin"

# Use gpg-agent as the SSH agent.
if command -q gpgconf
    gpg-connect-agent /bye >/dev/null 2>&1
    set -gx SSH_AUTH_SOCK (gpgconf --list-dirs agent-ssh-socket)

    if status is-interactive
        set -gx GPG_TTY (tty)
        gpg-connect-agent UPDATESTARTUPTTY /bye >/dev/null 2>&1
    end
end

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

function __gcg_generate --argument-names insertp
    set -l wait_dir (mktemp -d); or return
    set -l wait_fifo "$wait_dir/result"
    command mkfifo "$wait_fifo"; or begin
        command rmdir "$wait_dir"
        return 1
    end

    command emacsclient -a "" -u -e "(progn (require 'gptel-magit) (+gptel-magit-fish \"$wait_fifo\" $insertp))"
    set -l command_status $status
    set -l result
    if test $command_status -eq 0
        read -z result <"$wait_fifo"
        set command_status $status
    end

    command rm "$wait_fifo"
    command rmdir "$wait_dir"
    test $command_status -eq 0; or return $command_status

    if test (string sub -s 1 -l 1 -- "$result") = 0
        string sub -s 2 -- "$result"
    else
        printf 'gcg: ' >&2
        string sub -s 2 -- "$result" >&2
        return 1
    end
end

function gcg --description 'Generate into the current commit buffer'
    echo 'Generating commit message...'
    __gcg_generate t >/dev/null; or return
    echo 'Commit message generated.'
end

function gcgf --description 'Generate and commit immediately'
    echo 'Generating commit message...'
    set -l message (__gcg_generate nil | string collect); or return
    printf '%s\n' "$message" | command git commit -F -
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
