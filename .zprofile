# nodejs
eval "$(fnm env)"

# rust 
PATH=$(brew --prefix rustup)/bin:$PATH

# java
export SDKMAN_DIR=$(brew --prefix sdkman-cli)/libexec
export JDTLS_JAVA_HOME=$(brew --prefix openjdk)/libexec/openjdk.jdk/Contents/Home

# mactex
eval "$(/usr/libexec/path_helper)"
