{ config, lib, pkgs, ... }:
let
  authinfo = ".authinfo.gpg";
  inherit (pkgs.stdenv.hostPlatform) isDarwin;
in
{
  # Encrypted credentials, linked from the working tree (also read by Emacs auth-source
  # and mail.nix via home.file.authinfo.target).
  home.file.authinfo = {
    target = authinfo;
    source = config.lib.file.mkOutOfStoreSymlink "${config.xdg.configHome}/secrets/${authinfo}";
  };

  programs.gpg.enable = true;

  services.gpg-agent = {
    enable = true;
    pinentry.package = if isDarwin then pkgs.pinentry_mac else pkgs.pinentry-curses;
    enableSshSupport = true;
    grabKeyboardAndMouse = false;
    noAllowExternalCache = true;
    # Cache GPG passphrases for 2 hours and SSH passphrases for 12 hours.
    defaultCacheTtl = 2 * 60 * 60;
    maxCacheTtl = 2 * 60 * 60;
    defaultCacheTtlSsh = 12 * 60 * 60;
    maxCacheTtlSsh = 12 * 60 * 60;
  };

  # Keep HM's configuration and Fish integration; let GnuPG auto-start on macOS.
  launchd.agents.gpg-agent.enable = lib.mkIf isDarwin (lib.mkForce false);
}
