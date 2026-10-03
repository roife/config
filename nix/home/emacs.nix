{ config, pkgs, ... }:
{
  programs.emacs.enable = true;

  services.emacs = {
    enable = true;
    defaultEditor = true;
    extraOptions = [ "--init-directory=${config.xdg.configHome}/emacs" ];
  };

  home.packages = [
    pkgs.mupdf.dev # Headers and pkg-config metadata for emacs-reader.
  ];
}
