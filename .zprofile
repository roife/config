# nodejs
eval "$(fnm env)"

HOMEBREW=/opt/homebrew

# rust
PATH="$HOMEBREW/opt/rustup/bin:$PATH"
PATH="$HOME/.cargo/bin:$PATH"

# mactex
eval "$(/usr/libexec/path_helper)"
export PATH="$HOME/.local/slang/bin:$PATH"

# java
export JAVA_HOME="$HOMEBREW/opt/openjdk/libexec/openjdk.jdk/Contents/Home"
export JDTLS_JAVA_HOME="$JAVA_HOME"
