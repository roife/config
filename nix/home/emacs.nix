{ config, inputs, lib, pkgs, graphical, ... }:
{
  nixpkgs.overlays = [ inputs.emacs-overlay.overlays.emacs ];

  programs.emacs = {
    enable = true;
    # Track upstream master: Wayland/terminal on Linux, Cocoa on macOS.
    package = if pkgs.stdenv.hostPlatform.isDarwin then pkgs.emacs-git
      else if graphical then pkgs.emacs-git-pgtk else pkgs.emacs-git-nox;

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

  # Resolve MuPDF independently of the user's profile location.
  home.sessionSearchVariables.PKG_CONFIG_PATH = [
    "${lib.getDev pkgs.mupdf}/lib/pkgconfig"
  ];
}
