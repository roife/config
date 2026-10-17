{ inputs, pkgs, graphical, ... }:
let
  inherit (pkgs.stdenv.hostPlatform) isDarwin isLinux;
  linuxDesktop = graphical && isLinux;
in
{
  imports = [ inputs.colorscheme.homeModules.default ];

  # Firefox profile names are set next to programs.firefox in packages.nix.
  colorscheme = {
    darktable.enable = graphical;
    firefox.enable = graphical;
    chromium.enable = linuxDesktop;
    plasma.enable = linuxDesktop;
    konsole.enable = linuxDesktop;
    digikam.enable = linuxDesktop;
    squirrel.enable = graphical && isDarwin;
  };
}
