# nodejs
eval "$(fnm env)"

# rust 
PATH="$(brew --prefix rustup)/bin:$PATH"
PATH="$HOME/.cargo/bin:$PATH"

# java
export JDTLS_JAVA_HOME="$(brew --prefix openjdk)/libexec/openjdk.jdk/Contents/Home"
export JAVA_HOME="$(brew --prefix sdkman-cli)/libexec/candidates/java/current"
export SDKMAN_DIR="$(brew --prefix sdkman-cli)/libexec"
[[ -s "${SDKMAN_DIR}/bin/sdkman-init.sh" ]] && source "${SDKMAN_DIR}/bin/sdkman-init.sh"

# mactex
eval "$(/usr/libexec/path_helper)"
export PATH="$HOME/.local/slang/bin:$PATH"

export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_AUTH_TOKEN="sk-8e39457cdf374859a8f4f39c231ccdde"
export ANTHROPIC_MODEL="deepseek-v4-pro[1m]"
export ANTHROPIC_DEFAULT_OPUS_MODEL="deepseek-v4-pro[1m]"
export ANTHROPIC_DEFAULT_SONNET_MODEL="deepseek-v4-pro[1m]"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="deepseek-v4-flash"
export CLAUDE_CODE_SUBAGENT_MODEL="deepseek-v4-flash"
export CLAUDE_CODE_EFFORT_LEVEL="max"
