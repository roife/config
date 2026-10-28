# Linux-only layer on top of ./default.nix; imported by flake.nix.
{ lib, pkgs, graphical, ... }:
{
  imports = lib.optionals graphical [ ./kde.nix ];

  targets.genericLinux.enable = true;

  home.packages = [
    pkgs.clashtui
    pkgs.mihomo
  ] ++ lib.optionals graphical [ pkgs.google-chrome ];
}
