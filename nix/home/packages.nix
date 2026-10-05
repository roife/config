{ lib, pkgs, ... }:
{
  nixpkgs.config.allowUnfreePredicate = pkg:
    builtins.elem (lib.getName pkg) [ "qq" "wechat" ];

  home.packages = with pkgs; [
    # Desktop messaging
    qq
    wechat

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
    ast-grep
    hyperfine

    # Version control and shell utilities
    git-filter-repo
    gnupatch
    rsync
    wget
    unzip
    zip
    tokei

    # Writing, documents, and diagrams
    (aspellWithDicts (dicts: [ dicts.en ]))
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

    # Accounts
    bitwarden-cli
  ];

  programs.ripgrep = {
    enable = true;
    arguments = [ "--smart-case" ];
  };
  programs.fd = {
    enable = true;
    hidden = true;
    ignores = [ ".git/" ];
  };
  programs.yt-dlp = {
    enable = true;
    settings = {
      embed-metadata = true;
      embed-thumbnail = true;
      no-playlist = true;
    };
  };

  programs.direnv = {
    enable = true;
    nix-direnv.enable = true;
  };
  programs.tealdeer = {
    enable = true;
    settings.updates.auto_update = true;
  };
}
