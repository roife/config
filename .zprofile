# nodejs
eval "$(fnm env)"

HOMEBREW=/opt/homebrew

# rust
PATH="$HOMEBREW/opt/rustup/bin:$PATH"
PATH="$HOME/.cargo/bin:$PATH"

# java
export JDTLS_JAVA_HOME="$HOMEBREW/opt/openjdk/libexec/openjdk.jdk/Contents/Home"
export SDKMAN_DIR="$HOMEBREW/opt/sdkman-cli/libexec"
export JAVA_HOME="$SDKMAN_DIR/candidates/java/current"
[[ -s "${SDKMAN_DIR}/bin/sdkman-init.sh" ]] && source "${SDKMAN_DIR}/bin/sdkman-init.sh"

# mactex
eval "$(/usr/libexec/path_helper)"
export PATH="$HOME/.local/slang/bin:$PATH"
