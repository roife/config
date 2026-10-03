# Home Manager configuration shared by macOS and Linux.
{ config, lib, user, pkgs, ... }:
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
  ];

  home.username = user.fullName;
  home.homeDirectory =
    (if pkgs.stdenv.hostPlatform.isDarwin then "/Users/" else "/home/") + user.fullName;
  home.stateVersion = "26.05";

  nix = {
    package = lib.mkDefault pkgs.nix;
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
