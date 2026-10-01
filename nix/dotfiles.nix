{ config, lib, pkgs, ... }:
let
  name = "roife";
  email = "roifewu@gmail.com";
  codexSettings = {
    approval_policy = "never";
    sandbox_mode = "danger-full-access";
    model_context_window = 1000000;
    model_auto_compact_token_limit = 900000;
    personality = "pragmatic";
    model_verbosity = "low";
    plan_mode_reasoning_effort = "xhigh";
    tui = {
      animations = false;
      show_tooltips = false;
      session_picker_view = "dense";
      status_line = [
        "model-with-reasoning"
        "current-dir"
        "thread-name"
        "context-used"
      ];
    };
    features.prevent_idle_sleep = true;
  };
  codexConfig = (pkgs.formats.toml { }).generate "codex-config.toml" codexSettings;
in
{
  # Link to working files without copying their contents into the Nix store.
  home.file = lib.mapAttrs (_: path: {
    source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.config/${path}";
  }) {
    ".agents" = ".agents";
    ".authinfo.gpg" = "secrets/.authinfo.gpg";
  };

  # Linux uses Fontconfig; Home Manager installs macOS fonts into ~/Library/Fonts.
  fonts.fontconfig = lib.mkIf pkgs.stdenv.hostPlatform.isLinux {
    enable = true;
    configFile.preferences = {
      enable = true;
      source = ./fonts.conf;
    };
  };

  nix = {
    package = lib.mkDefault pkgs.nix;
    gc = {
      automatic = true;
      options = "--delete-older-than 30d";
    };
  };
  # HACK: Home Manager passes gc.options as one argument on Darwin.
  # https://github.com/nix-community/home-manager/issues/7211
  launchd.agents.nix-gc.config.ProgramArguments = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin (
    lib.mkForce ([ "${config.nix.package}/bin/nix-collect-garbage" ] ++ lib.splitString " " config.nix.gc.options)
  );

  programs.pnpm.enable = true;

  programs.tealdeer = {
    enable = true;
    settings.updates.auto_update = true;
  };

  programs.emacs.enable = true;
  services.emacs = {
    enable = true;
    defaultEditor = true;
    extraOptions = [ "--init-directory=${config.home.homeDirectory}/.config/emacs" ];
  };

  programs.direnv.enable = true;

  programs.rime.userConfigDirectory = ../rime;

  programs.git = {
    enable = true;
    lfs.enable = true;
    settings = {
      user = {
        inherit name email;
      };
      core = {
        quotepath = false;
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
      prefer_editor_prompt = "enabled";
      aliases.co = "pr checkout";
      color_labels = "enabled";
      spinner = "disabled";
    };
  };

  # HACK: https://github.com/nix-community/home-manager/pull/10000
  # Keep the user config writable so Codex can save GUI preferences.
  # Each activation restores the configuration declared above.
  home.activation.writeCodexConfig = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
  run mkdir -p "$HOME/.codex"
  if [[ -L "$HOME/.codex/config.toml" ]]; then
    run rm -f "$HOME/.codex/config.toml"
  fi
  run install -m 600 ${codexConfig} "$HOME/.codex/config.toml"
  '';

  programs.gpg.enable = true;
  services.gpg-agent = {
    enable = true;
    pinentry.package = if pkgs.stdenv.hostPlatform.isDarwin
                       then pkgs.pinentry_mac
                       else pkgs.pinentry-curses;
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
  launchd.agents.gpg-agent.enable =
    lib.mkIf pkgs.stdenv.hostPlatform.isDarwin (lib.mkForce false);

  programs.mbsync.enable = true;
  accounts.email = {
    certificatesFile = null;
    maildirBasePath = "${config.home.homeDirectory}/.local/share/mail";
    accounts.gmail = {
      primary = true;
      address = email;
      realName = name;
      userName = email;
      passwordCommand = [
        (toString (pkgs.writeShellScript "gmail-imap-password" ''
          set -euo pipefail
          "${pkgs.gnupg}/bin/gpg" --batch -d "$HOME/.authinfo.gpg" 2>/dev/null |
            "${pkgs.gawk}/bin/awk" '$2 == "imap.gmail.com" { for (i = 3; i < NF; i += 2) if ($i == "password") { print $(i + 1); exit } }'
        ''))
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
