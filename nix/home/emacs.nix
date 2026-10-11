{ config, lib, pkgs, graphical, ... }:
{
  programs.emacs = {
    enable = true;
    # Wayland for desktops, terminal-only for headless Linux; Cocoa on macOS.
    package = lib.mkIf pkgs.stdenv.hostPlatform.isLinux (
      if graphical then pkgs.emacs-pgtk else pkgs.emacs-nox
    );

    # Launch through the app bundle so Rime can identify Emacs on macOS.
    overrides = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin (_self: super: {
      emacsWithPackages = packages:
        (super.emacsWithPackages packages).overrideAttrs (old: {
          buildCommand = old.buildCommand + ''
            ln -sf ../Applications/Emacs.app/Contents/MacOS/Emacs "$out/bin/emacs"
            ln -sf emacs "$out/bin/emacs-${config.programs.emacs.package.version}"
          '';
        });
    });
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
