{ config, pkgs, ... }:
{
  nix.package = pkgs.nix;
  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  programs.pnpm.enable = true;

  programs.emacs.enable = true;
  services.emacs = {
    enable = true;
    defaultEditor = true;
  };

  programs.git = {
    enable = true;
    lfs.enable = true;
    settings = {
      user = {
        name = "roife";
        email = "roifewu@gmail.com";
      };
      core = {
        quotepath = false;
        preloadindex = true;
        untrackedCache = true;
      };
      fetch.prune = true;
      github.user = "roife";
    };
    ignores = [
      # macOS and Windows
      ".DS_Store"
      ".AppleDouble"
      ".LSOverride"
      "Icon?"
      "._*"
      "Thumbs.db"
      "Thumbs.db:encryptable"
      "ehthumbs.db"
      "Desktop.ini"
      "$RECYCLE.BIN/"

      # Editors and operating systems
      "*~"
      ".nfs*"
      ".vscode/*"
      "!.vscode/settings.json"
      "!.vscode/tasks.json"
      "!.vscode/launch.json"
      "!.vscode/extensions.json"
      ".idea/"
      "*.iml"
      "out/"
      "*.sublime-workspace"
      "*.sublime-project"
      "*.swp"
      "*.swo"
      "*.swn"
      "Session.vim"
      "\\#*\\#"
      ".\\#*"

      # Languages and build output
      "__pycache__/"
      "*.py[cod]"
      "*.pyo"
      "*.pyd"
      "*.pdb"
      "*.pytest_cache/"
      ".python-version"
      ".venv/"
      "env/"
      "venv/"
      "node_modules/"
      "npm-debug.log*"
      "yarn-debug.log*"
      "yarn-error.log*"
      ".pnpm-store/"
      ".pnp/"
      ".pnp.js"
      "*.class"
      "*.jar"
      "*.war"
      "*.ear"
      "hs_err_pid*"
      "vendor/"
      "*.test"
      "target/"
      "Cargo.lock"
      ".bundle/"
      "vendor/bundle/"
      "Gemfile.lock"
      "*.orig"
      "*.rej"
      ".svn/"
      ".hg/"
      "**/.claude/settings.local.json"
    ];
  };

  programs.gh = {
    enable = true;
    gitCredentialHelper.enable = false;
    settings = {
      git_protocol = "https";
      prompt = "enabled";
      prefer_editor_prompt = "enabled";
      aliases.co = "pr checkout";
      color_labels = "enabled";
      spinner = "disabled";
    };
  };

  services.gpg-agent = {
    enable = true;
    enableSshSupport = true;
    grabKeyboardAndMouse = false;
    noAllowExternalCache = true;
    defaultCacheTtl = 600;
    maxCacheTtl = 7200;
    defaultCacheTtlSsh = 1800;
    maxCacheTtlSsh = 7200;
  };

  programs.mbsync.enable = true;
  accounts.email = {
    certificatesFile = null;
    maildirBasePath = "${config.home.homeDirectory}/.local/share/mail";
    accounts.gmail = {
      address = "roifewu@gmail.com";
      realName = "roife";
      userName = "roifewu@gmail.com";
      passwordCommand = [
        (toString (pkgs.writeShellScript "gmail-imap-password" ''
          set -euo pipefail
          "${pkgs.gnupg}/bin/gpg" --batch -d "$HOME/.authinfo.gpg" 2>/dev/null |
            "${pkgs.gawk}/bin/awk" '$2 == "imap.gmail.com" { for (i = 3; i < NF; i += 2) if ($i == "password") { print $(i + 1); exit } }'
        ''))
      ];
      imap = {
        host = "imap.googlemail.com";
        tls.useStartTls = false;
      };
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
