{ lib, pkgs, ... }:
{
  imports = [
    ../lang/java.nix
    ../lang/node.nix
    ../lang/rust.nix
    ../lang/python.nix
  ];

  home.packages = with pkgs; [
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
    yt-dlp

    # Accounts
    bitwarden-cli
  ];

  programs.direnv.enable = true;
  programs.tealdeer = {
    enable = true;
    settings.updates.auto_update = true;
  };
}
