# platform
is_macos=0
package_prefix=/usr
PATH="$HOME/.local/bin:$PATH"

if [[ "$OSTYPE" == darwin* ]]; then
    is_macos=1
    package_prefix=/opt/homebrew
    PATH="$package_prefix/opt/rustup/bin:$PATH"
fi

PATH="$HOME/.cargo/bin:$PATH"

# java; Linux version selection will be handled separately
if (( is_macos )); then
    export JAVA_HOME="$package_prefix/opt/openjdk/"
    export JDTLS_JAVA_HOME="$package_prefix/opt/openjdk@21/"
fi
