{ config, pkgs, ... }:
{
  home.packages = with pkgs; [
    codex-acp
  ];

  # Shared agent skills, linked from the working tree.
  home.file.".agents".source = config.lib.file.mkOutOfStoreSymlink "${config.xdg.configHome}/.agents";

  programs.codex = {
    enable = true;
    mutableSettings = true;
    settings = {
      approval_policy = "on-request";
      sandbox_mode = "workspace-write";
      approvals_reviewer = "auto_review";

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
        appearanceLightCodeThemeId = "solarized";
        appearanceTheme = "system";
      };

      features.prevent_idle_sleep = true;
    };
  };
}
