# Linux-only layer on top of ./default.nix; imported by flake.nix.
{ lib, pkgs, graphical, ... }:
{
  imports = lib.optionals graphical [ ./kde.nix ];

  targets.genericLinux.enable = true;

  home.packages = lib.optionals graphical [ pkgs.chromium ];
}
