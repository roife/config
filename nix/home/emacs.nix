{ config, lib, pkgs, ... }:
{
  programs.emacs = {
    enable = true;
    # Native Wayland build for Plasma; macOS keeps the default Cocoa build.
    package = lib.mkIf pkgs.stdenv.hostPlatform.isLinux pkgs.emacs-pgtk;
  };

  services.emacs = {
    enable = true;
    defaultEditor = true;
    extraOptions = [ "--init-directory=${config.xdg.configHome}/emacs" ];
  };

  home.packages = [
    pkgs.mupdf.dev # Headers and pkg-config metadata for emacs-reader.
  ];
}
