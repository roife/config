{ inputs, pkgs, graphical, ... }:
let
  inherit (pkgs.stdenv.hostPlatform) isDarwin isLinux;
  linuxDesktop = graphical && isLinux;
in
{
  imports = [ inputs.colorscheme.homeModules.default ];

  colorscheme = {
    darktable.enable = graphical;
    plasma.enable = linuxDesktop;
    konsole.enable = linuxDesktop;
    digikam.enable = linuxDesktop;
    squirrel.enable = graphical && isDarwin;
  };
}
