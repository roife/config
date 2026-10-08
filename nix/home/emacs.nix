{ config, lib, pkgs, graphical, ... }:
{
  programs.emacs = {
    enable = true;
    # Wayland for desktops, terminal-only for headless Linux; Cocoa on macOS.
    package = lib.mkIf pkgs.stdenv.hostPlatform.isLinux (
      if graphical then pkgs.emacs-pgtk else pkgs.emacs-nox
    );
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
