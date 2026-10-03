{ pkgs, ... }:
{
  home.sessionPath = [ "$HOME/.local/bin" ];
  programs.fish = {
    enable = true;
    plugins = map (name: {
      inherit name;
      src = pkgs.fishPlugins.${name}.src;
    }) [ "plugin-git" "z" "autopair" "bass" ];

    shellAbbrs = {
      l = "ll -a";
      la = "ll -a";
      rm = "rm -i";
      codex = "codex --disable apps --disable plugins";
    };

    binds = {
      ctrl-t = {
        name = "\\ct";
        command = "ezf-file-widget";
      };
      ctrl-r = {
        name = "\\cr";
        command = "ezf-history-widget";
      };
      alt-c = {
        name = "\\ec";
        command = "ezf-cd-widget";
      };
      alt-x = {
        name = "\\ex";
        command = "ezf-dispatch-widget";
      };
    };

    shellInit = ''
      # Nix profile PATH, certificate bundle and other environment.
      if test -f /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.fish
        source /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.fish
      else
        source_if_exists "$HOME/.nix-profile/etc/profile.d/nix.fish"
      end
    '';

    interactiveShellInit = ''
      source_if_exists "$HOME/.config/emacs/straight/repos/ezf/scripts/ezf.fish"
    '';

    functions = {
      fish_greeting = "";
      fish_prompt = {
        description = "Show login context and working directory";
        body = ''
          set -l last_status $status

          if set -q SSH_CONNECTION; or set -q SUDO_USER; or fish_is_root_user
              set_color cyan
              printf '%s@%s ' "$USER" (prompt_hostname)
          end

          set_color (test $last_status -eq 0; and echo green; or echo red)
          printf '%s ' (prompt_pwd --dir-length=0)
          set_color normal
        '';
      };
      source_if_exists = {
        description = "Source a file if it exists";
        body = ''
          if test -f "$argv[1]"
            source "$argv[1]"
          end
        '';
      };
      e = {
        wraps = "emacsclient";
        description = "Open files in Emacs";
        body = ''
          set -q argv[1]; or set argv .
          command emacsclient -t $argv
        '';
      };
      ec = {
        wraps = "emacsclient";
        description = "Open files in a new Emacs frame";
        body = ''
          set -q argv[1]; or set argv .
          command emacsclient -c $argv
        '';
      };
    };
  };
}
