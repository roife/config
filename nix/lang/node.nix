{ pkgs, ... }:
{
  home.packages = [ pkgs.nodejs ];
  programs.pnpm.enable = true;
}
