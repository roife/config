{ pkgs, ... }:
{
  programs.direnv.enable = true;

  programs.fish = {
    enable = true;
    plugins = [
      { name = "plugin-git"; src = pkgs.fishPlugins.plugin-git.src; }
      { name = "z"; src = pkgs.fishPlugins.z.src; }
      { name = "autopair"; src = pkgs.fishPlugins.autopair.src; }
      { name = "bass"; src = pkgs.fishPlugins.bass.src; }
    ];

    shellAbbrs = {
      l = "ll -a";
      la = "ll -a";
      rm = "rm -i";
      codex = "codex --disable apps --disable plugins";
    };

    binds = {
      "ctrl-t" = {
        name = "\\ct";
        command = "ezf-file-widget";
      };
      "ctrl-t-insert" = {
        name = "\\ct";
        command = "ezf-file-widget";
        mode = "insert";
      };
      "ctrl-r" = {
        name = "\\cr";
        command = "ezf-history-widget";
      };
      "ctrl-r-insert" = {
        name = "\\cr";
        command = "ezf-history-widget";
        mode = "insert";
      };
      "alt-c" = {
        name = "\\ec";
        command = "ezf-cd-widget";
      };
      "alt-x" = {
        name = "\\ex";
        command = "ezf-dispatch-widget";
      };
    };

    shellInit = ''
      # Nix's system and Home Manager profiles.
      for nix_bin in /nix/var/nix/profiles/default/bin $HOME/.nix-profile/bin
          if test -d $nix_bin
              fish_add_path --path --move $nix_bin
          end
      end

      set -gx JAVA21_HOME "${pkgs.temurin-bin-21.home}"
      set -gx JAVA26_HOME "${pkgs.temurin-bin-26.home}"
      if not set -q JAVA_HOME
          set -gx JAVA_HOME "$JAVA26_HOME"
      end
      set -gx JDTLS_JAVA_HOME "$JAVA21_HOME"
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
      __gcg_generate = {
        argumentNames = [ "insertp" ];
        body = ''
          set -l wait_dir (mktemp -d); or return
          set -l wait_fifo "$wait_dir/result"
          command mkfifo "$wait_fifo"; or begin
              command rmdir "$wait_dir"
              return 1
          end

          command emacsclient -a "" -u -e "(progn (require 'gptel-magit) (+gptel-magit-fish \"$wait_fifo\" $insertp))"
          set -l command_status $status
          set -l result
          if test $command_status -eq 0
              read -z result <"$wait_fifo"
              set command_status $status
          end

          command rm "$wait_fifo"
          command rmdir "$wait_dir"
          test $command_status -eq 0; or return $command_status

          if test (string sub -s 1 -l 1 -- "$result") = 0
              string sub -s 2 -- "$result"
          else
              printf 'gcg: ' >&2
              string sub -s 2 -- "$result" >&2
              return 1
          end
        '';
      };
      gcg = {
        description = "Generate into the current commit buffer";
        body = ''
          echo 'Generating commit message...'
          __gcg_generate t >/dev/null; or return
          echo 'Commit message generated.'
        '';
      };
      gcgf = {
        description = "Generate and commit immediately";
        body = ''
          echo 'Generating commit message...'
          set -l message (__gcg_generate nil | string collect); or return
          printf '%s\n' "$message" | command git commit -F -
        '';
      };
    };

    interactiveShellInit = ''
      source "$HOME/.emacs.d/straight/repos/ezf/scripts/ezf.fish"
    '';
  };
}
