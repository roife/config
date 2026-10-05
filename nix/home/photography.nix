# These files are replaced with the declared preferences on activation.
{ lib, pkgs, ... }:
{
  xdg.configFile."darktable/darktablerc-common" = {
    force = true;
    # Compared with the defaults shipped by darktable 5.6.1.
    text = ''
      themes/usercss=TRUE
      ui/show_welcome_screen=FALSE
      ui_last/gui_language=zh_CN
      ui_last/theme=darktable
    '';
  };

  # Non-default digiKam 9.1.0 preferences; Linux is managed by kde.nix.
  home.file."Library/Preferences/digikamrc" = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin {
    force = true;
    text = ''
      [Album Settings]
      Preview Raw Use Loading Data=1
      Show Thumbbar=false
      Theme=FusionGray

      [Autotags Settings]
      Autotags Object Detection Model=efficientnetb7

      [General Settings]
      DateTime Format=yyyy/M/d HH:mm
      Show Splash=false

      [ImageViewer Settings]
      PreviewMode=128
    '';
  };
}
