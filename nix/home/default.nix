# Home Manager configuration shared by macOS and Linux.
{ config, lib, inputs, user, pkgs, ... }:
{
  imports = [
    ./packages.nix
    ./fonts.nix
    ./fish.nix
    ./git.nix
    ./gpg.nix
    ./mail.nix
    ./emacs.nix
    ./vim.nix
    ./rime.nix
    ./agents.nix
    ../lang/java.nix
    ../lang/nix.nix
    ../lang/node.nix
    ../lang/python.nix
    ../lang/rust.nix
  ];

  home.username = user.username;
  home.homeDirectory =
    (if pkgs.stdenv.hostPlatform.isDarwin then "/Users/" else "/home/") + user.username;
  home.stateVersion = "26.05";

  # Export XDG_* so tools stay out of ~/Library/Application Support on macOS.
  xdg.enable = true;
  home.preferXdgDirectories = true;

  nix = {
    package = lib.mkDefault pkgs.nix;
    # Settings live in ../nix.conf, read directly from the working tree.
    # Resolve `nixpkgs#…` and `<nixpkgs>` to the locked input.
    registry.nixpkgs.flake = inputs.nixpkgs;
    nixPath = [ "nixpkgs=${inputs.nixpkgs}" ];
    gc = {
      automatic = true;
      options = "--delete-older-than 30d";
    };
  };

  # HACK: Home Manager passes gc.options as one argument on Darwin.
  # https://github.com/nix-community/home-manager/issues/7211
  launchd.agents.nix-gc.config.ProgramArguments = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin (
    lib.mkForce ([ "${config.nix.package}/bin/nix-collect-garbage" ] ++ lib.splitString " " config.nix.gc.options)
  );

  programs.home-manager.enable = true;
}
