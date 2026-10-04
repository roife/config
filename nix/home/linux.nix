# Linux-only layer on top of ./default.nix; imported by flake.nix.
{ pkgs, ... }:
{
  imports = [ ./kde.nix ];

  home.packages = [ pkgs.chromium ];
}
