# Linux-only layer on top of ./default.nix; imported by flake.nix.
{ pkgs, ... }:
{
  imports = [ ./kde.nix ];

  targets.genericLinux.enable = true;

  home.packages = [ pkgs.chromium ];
}
