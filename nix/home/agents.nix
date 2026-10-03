{ config, lib, pkgs, ... }:
let
  codexConfig = (pkgs.formats.toml { }).generate "codex-config.toml" {
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

    desktop = {
      followUpQueueMode = "queue";
      composerPlainTextMode = true;
      show-context-window-usage = true;
      composerEnterBehavior = "cmdIfMultiline";
      codeFontSize = 14;
      pagesFontSize = 16;
      sansFontSize = 16;
    };

    features.prevent_idle_sleep = true;
  };
in
{
  home.packages = [ pkgs.codex-acp ];

  # Shared agent skills, linked from the working tree.
  home.file.".agents".source =
    config.lib.file.mkOutOfStoreSymlink "${config.xdg.configHome}/.agents";

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
}
