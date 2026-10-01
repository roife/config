{ config, lib, pkgs, fenixPackages, ... }:
{
  imports = [ ./dotfiles.nix ./fish.nix ];

  home.username = "roifewu";
  home.homeDirectory =
    (if pkgs.stdenv.hostPlatform.isDarwin then "/Users/" else "/home/")
    + config.home.username;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;

  home.packages = with pkgs; [
    # Fonts shared by macOS and Linux.
    sarasa-gothic
    noto-fonts
    noto-fonts-cjk-sans
    noto-fonts-cjk-serif
    noto-fonts-color-emoji

    # Default language toolchains. Project-specific versions belong in devShells.
    nodejs_24
    temurin-bin-26
    fenixPackages.stable.toolchain
    # Prefer LLVM, then GNU binutils, then GCC's bundled binutils (lower wins).
    (lib.setPrio 30 gcc)
    (lib.setPrio 20 binutils)
    gdb
    # Keep all LLVM tools on Nixpkgs' default LLVM version.
    llvmPackages.llvm
    llvmPackages.llvm.dev
    llvmPackages.clang
    llvmPackages.clang-tools
    llvmPackages.lld
    llvmPackages.lldb

    # Build and code intelligence
    gnumake
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
    gnupatch
    rsync
    ripgrep
    fd
    wget
    unzip
    zip
    # HACK: Frost's Lua filters use native bitwise operators (Lua >= 5.3).
    (librime.override {
      plugins = [
        (librime-lua.override { lua = lua5_4; })
        librime-octagram
      ];
    })

    # Writing, documents, and diagrams
    (aspellWithDicts (dicts: [ dicts.en ]))
    mupdf.dev # Headers and pkg-config metadata for emacs-reader.
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
    codex-acp
    bitwarden-cli
  ];
}
