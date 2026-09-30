{ config, pkgs, fenixPackages, ... }:
{
  imports = [ ./dotfiles.nix ./fish.nix ];

  home.username = "roifewu";
  home.homeDirectory =
    (if pkgs.stdenv.hostPlatform.isDarwin then "/Users/" else "/home/")
    + config.home.username;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;

  # Linux uses Fontconfig; Home Manager installs macOS fonts into ~/Library/Fonts.
  fonts.fontconfig = lib.mkIf pkgs.stdenv.hostPlatform.isLinux {
    enable = true;
    configFile.preferences = {
      enable = true;
      priority = 60;
      source = ./fonts.conf;
    };
  };

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
    # GNU tools coexist with LLVM; prefer LLVM for shared command names.
    (lib.setPrio 20 gcc)
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
    openssh
    rsync
    ripgrep
    fd
    wget
    gnutar
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
    codex
    codex-acp
    bitwarden-cli
  ];
}
