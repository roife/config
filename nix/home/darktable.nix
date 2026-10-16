{ lib, pkgs, graphical, ... }:
{
  xdg.configFile = lib.mkIf (graphical && pkgs.stdenv.hostPlatform.isLinux) {
    "darktable/darktablerc-common" = {
      force = true;
      text = ''
        font_size=10.0
        ui/show_welcome_screen=FALSE
        ui_last/gui_language=zh_CN
      '';
    };
  };
}
