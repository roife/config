{ config, lib, user, pkgs, ... }:
let
  authinfo = ".authinfo.gpg";
in
{
  programs.mbsync.enable = true;

  accounts.email = {
    certificatesFile = null;
    maildirBasePath = "${config.home.homeDirectory}/.local/share/mail";
    accounts.gmail = {
      primary = true;
      address = user.email;
      realName = user.fullName;
      userName = user.email;
      passwordCommand = lib.concatStringsSep " " [
        ''printf 'host=%s\nusername=%s\n\n' imap.gmail.com:993 ${lib.escapeShellArg user.email} |''
        ''${pkgs.git}/bin/git-credential-netrc -f "$HOME/${authinfo}" -g ${pkgs.gnupg}/bin/gpg get |''
        ''${pkgs.gnused}/bin/sed -n 's/^password=//p' ''
      ];
      imap.host = "imap.googlemail.com";
      maildir.path = "gmail";
      folders.inbox = "INBOX";
      mbsync = {
        enable = true;
        flatten = ".";
        patterns = [ "INBOX" "*" ];
        create = "both";
        extraConfig.account = {
          AuthMechs = "LOGIN";
          TLSVersions = "-1.3";
        };
        extraConfig.channel.CopyArrivalDate = true;
      };
    };
  };
}
