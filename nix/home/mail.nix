{ config, lib, user, pkgs, ... }:
{
  programs.mbsync.enable = true;

  accounts.email = {
    certificatesFile = null;
    maildirBasePath = "${config.home.homeDirectory}/.local/share/mail";
    accounts.gmail = {
      primary = true;
      flavor = "gmail.com";
      address = user.email;
      realName = user.fullName;
      passwordCommand = lib.concatStringsSep " " [
        ''printf 'host=%s\nusername=%s\n\n' imap.gmail.com:993 ${lib.escapeShellArg user.email} |''
        ''${pkgs.git}/bin/git-credential-netrc -f "$HOME/${config.home.file.authinfo.target}" -g ${pkgs.gnupg}/bin/gpg get |''
        ''${pkgs.gnused}/bin/sed -n 's/^password=//p' ''
      ];
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
