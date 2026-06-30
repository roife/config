# auto-completion
zstyle ':completion:*' sort         false # don't sort completion candidates
zstyle ':completion:*' menu select
[[ -n "$LS_COLORS" ]] && zstyle ':completion:*' list-colors "${(@s.:.)LS_COLORS}" # colors for ls
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}' 'l:|=* r:|=*' # case-insensitive when completion with tab & fuzzy
autoload -Uz compinit
compinit -C -d ~/.cache/zsh/zcompdump

# cd folder without "cd"
setopt auto_cd
setopt auto_pushd
setopt pushd_ignore_dups
setopt pushd_silent

# correct
setopt correct_all

# auto-suggestion
source /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh
# z
source /opt/homebrew/etc/profile.d/z.sh
# PS
PS1='%(?.%F{green}.%F{red})%~%f '

# history
HISTFILE=$HOME/.zsh_history
HISTSIZE=50000
SAVEHIST=50000

setopt append_history
setopt inc_append_history
unsetopt share_history
setopt hist_ignore_dups
setopt hist_reduce_blanks
setopt hist_expire_dups_first
setopt hist_ignore_space
setopt hist_verify
setopt extended_history
setopt hist_find_no_dups

# Treat - and / as word separators for Option+Left/Right
WORDCHARS=${WORDCHARS//[\/.-]/}

# alias
alias l='ls -laGh'     #size,show type,human readable
alias la='ls -lAFh'   #long list,show almost all,show type,human readable
alias lr='ls -tRFh'   #sorted by date,recursive,show type,human readable
alias lt='ls -ltFh'   #long list,sorted by date,show type,human readable
alias rm='rm -i'
alias grep='grep --color=auto'

#alias-git
# Oh My Zsh Git aliases — 常用 alias 列表
git_current_branch() {
    git symbolic-ref --short HEAD 2>/dev/null
}

alias g='git'
alias gst='git status'
alias gss='git status -s'
alias ga='git add'
alias gaa='git add --all'
alias gapa='git add --patch'
alias gb='git branch'
alias gba='git branch -a'
alias gbd='git branch -d'
alias gbD='git branch -D'
alias gbda='git branch --no-color --merged | command grep -vE "^(\*|\s*(main|master|develop)\s*$)" | command xargs -n 1 git branch -d'
alias gbl='git blame -b -w'
alias gbnm='git branch --no-merged'
alias gbr='git branch --remote'
alias gbs='git bisect'
alias gbsb='git bisect bad'
alias gbsg='git bisect good'
alias gbsr='git bisect reset'
alias gbss='git bisect start'

alias gc='git commit -v'
alias gc!='git commit -v --amend'
alias gca='git commit -v -a'
alias gca!='git commit -v -a --amend'
alias gcam='git commit -a -m'
alias gcmsg='git commit -m'
alias gcsm='git commit -s -m'
alias gcs='git commit -S'

alias gco='git checkout'
alias gcb='git checkout -b'
alias gcm='git checkout master'
alias gcd='git checkout develop'

alias gr='git reset'
alias grh='git reset --hard'
alias grhh='git reset HEAD --hard'

alias gcl='git clone --recurse-submodules'
alias gcf='git config --list'
alias gclean='git clean -id'

alias gd='git diff'
alias gdt='GIT_EXTERNAL_DIFF=difft git diff'
alias gdca='git diff --cached'
alias gds='git diff --staged'
alias gdw='git diff --word-diff'
alias gdct='git describe --tags $(git rev-list --tags --max-count=1)'

alias gf='git fetch'
alias gfa='git fetch --all --prune'
alias gfo='git fetch origin'

alias gl='git pull'
alias gp='git push'
alias ggpull='git pull origin "$(git_current_branch)"'
alias ggpush='git push origin "$(git_current_branch)"'
alias ggsup='git branch --set-upstream-to=origin/"$(git_current_branch)"'

alias gcount='git shortlog -sn'
alias gcp='git cherry-pick'
alias gcpa='git cherry-pick --abort'
alias gcpc='git cherry-pick --continue'

alias glog='git log --all --pretty="format:%d %h  %s" --graph'

alias codex='codex --disable apps --disable plugins'

e() {
  if (( $# == 0 )); then
    emacsclient .
  else
    emacsclient "$@"
  fi
}
ec() {
  if (( $# == 0 )); then
    emacsclient -c .
  else
    emacsclient -c "$@"
  fi
}

# brew
alias brewdump='brew bundle dump --file="$HOME/.config/Brewfile"'
alias brewrestore='brew bundle --file="$HOME/.config/Brewfile"'

# Integration with fzf
source <(fzf --zsh)

# direnv
eval "$(direnv hook zsh)"

# Backup
recover() {
    ln -sfn "$HOME/.config/.gitconfig" "$HOME/.gitconfig"
    ln -sfn "$HOME/.config/.gitignore_global" "$HOME/.gitignore_global"
    brew bundle --file="$HOME/.config/Brewfile"

    rustup install nightly
    fnm i --lts
    tldr -u
}

# IME switching
autoload -Uz add-zsh-hook

focus-in()  { im-select com.apple.keylayout.ABC }
focus-out() { : }
zle -N focus-in
zle -N focus-out
bindkey '\e[I' focus-in
bindkey '\e[O' focus-out

_focus_on()  { print -n '\e[?1004h' }
_focus_off() { print -n '\e[?1004l' }
add-zsh-hook precmd  _focus_on
add-zsh-hook preexec _focus_off
add-zsh-hook zshexit _focus_off

# highlighting
source /opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

