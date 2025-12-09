# auto-completion
zstyle ':completion:*' list-colors "${(@s.:.)LS_COLORS}" # colors for ls
zstyle ':completion:*' matcher-list '' 'm:{a-zA-Z}={A-Za-z}' # case-insensitive when completion with tab
autoload -U compinit
compinit

# cd folder without "cd"
setopt autocd

# highlighting
source /opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
# auto-suggestion
source /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh
# z
source /opt/homebrew/etc/profile.d/z.sh

# PS
PS1="%F{green}%~%f "

# history
HISTFILE=~/.histfile
HISTSIZE=5000
SAVEHIST=5000
setopt appendhistory

# alias
alias l='ls -lFh'     #size,show type,human readable
alias la='ls -lAFh'   #long list,show almost all,show type,human readable
alias lr='ls -tRFh'   #sorted by date,recursive,show type,human readable
alias lt='ls -ltFh'   #long list,sorted by date,show type,human readable
alias ll='ls -laGh'      #long list
alias rm='rm -i'
alias grep='grep --color'
alias ec='emacsclient -n'

#alias-git
# Oh My Zsh Git aliases — 常用 alias 列表
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

alias gcl='git clone --recurse-submodules'
alias gcf='git config --list'
alias gclean='git clean -id'

alias gd='git diff'
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

alias vim='nvim'

# nodejs
eval "$(fnm env)"

# brew
alias brewdump='brew bundle dump --file="~/.config/Brewfile"'
alias brewrestore='brew bundle --file="~/.config/Brewfile"'

# Backup
recover() {
    ln .gitconfig ~
    ln .gitignore_global ~
    brew bundle --file="~/.config/Brewfile"
}
