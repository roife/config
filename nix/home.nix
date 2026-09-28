{ config, pkgs, fenixPackages, ... }:
{
  imports = [ ./dotfiles.nix ./fish.nix ];

  home.username = "roifewu";
  home.homeDirectory =
    (if pkgs.stdenv.hostPlatform.isDarwin then "/Users/" else "/home/")
    + config.home.username;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;

  home.packages = with pkgs; [
    # Default language toolchains. Project-specific versions belong in devShells.
    nodejs_24
    temurin-bin-26
    fenixPackages.stable.toolchain
    # Keep all LLVM tools on Nixpkgs' default LLVM version.
    llvmPackages.llvm
    llvmPackages.llvm.dev
    llvmPackages.clang
    llvmPackages.clang-tools
    llvmPackages.lld
    llvmPackages.lldb

    # Build and code intelligence
    cmake
    ninja
    pkg-config
    tree-sitter
    universal-ctags
    tokei
    jdt-language-server
    pest-ide-tools

    # Python tooling
    uv
    ruff
    pyrefly

    # Version control and shell utilities
    git-filter-repo
    difftastic
    ripgrep
    fd
    wget
    tealdeer
    librime

    # Writing, documents, and diagrams
    aspell
    mupdf
    gnuplot
    plantuml
    pandoc
    tectonic
    graphviz
    d2
    mermaid-cli
    typst
    tinymist

    # Media
    exiftool
    ffmpeg
    imagemagick
    yt-dlp

    # AI and account tools
    codex
    codex-acp
    bitwarden-cli
  ];
}
