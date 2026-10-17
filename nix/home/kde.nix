{ inputs, lib, pkgs, ... }:
let
  gwenviewWithHeif = pkgs.kdePackages.gwenview.overrideAttrs (old: {
    qtWrapperArgs = (old.qtWrapperArgs or [ ]) ++ [
      "--prefix QT_PLUGIN_PATH : ${pkgs.kdePackages.kimageformats}/lib/qt-6/plugins"
    ];
  });

  # Current panel order; widget settings omit Plasma 6.7.5 defaults and UI state.
  panelWidgets = [
    {
      name = "org.kde.plasma.kickoff";
      settings.General.icon = "start-here";
    }
    { name = "org.kde.plasma.pager"; }
    {
      name = "org.kde.plasma.taskmanager";
      settings.General = {
        groupingStrategy = 0;
        iconSpacing = 0;
        launchers = [
          "preferred://filemanager"
          "preferred://browser"
          "applications:org.kde.konsole.desktop"
        ];
      };
    }
    { name = "org.kde.plasma.marginsseparator"; }
    {
      name = "org.kde.plasma.systemtray";
      settings.General.iconSpacing = 1;
    }
    {
      name = "org.kde.plasma.digitalclock";
      settings.Appearance = {
        dateDisplayFormat = "BesideTime";
        enabledCalendarPlugins = [
          "holidaysevents"
          "pimevents"
        ];
        showDate = false;
        use24hFormat = 2;
      };
    }
    { name = "org.kde.plasma.showdesktop"; }
  ];
in
{
  # KDE desktop settings; imported by x86_64-linux.nix.
  imports = [
    inputs.plasma-manager.homeModules.plasma-manager
  ];

  home.packages = [
    # Use Nix's media libraries for HEIF images and H.264/HEVC videos.
    gwenviewWithHeif
    pkgs.kdePackages.dragon
    # Install both theme variants together; KDE manages GTK appearance settings.
    pkgs.kdePackages.breeze-gtk
  ];

  # Provide KDE's integration modules built against Nix's GTK libraries.
  programs.firefox.package = pkgs.firefox.overrideAttrs (old: {
    gtk_modules = old.gtk_modules ++ [
      "${pkgs.kdePackages.kde-gtk-config}/lib/gtk-3.0"
    ];
  });

  # Prefer the Nix viewer even when Plasma's session still has Fedora's PATH.
  xdg.dataFile."applications/org.kde.gwenview.desktop".text = builtins.replaceStrings
    [ "Exec=gwenview" ] [ "Exec=${gwenviewWithHeif}/bin/gwenview" ]
    (builtins.readFile "${pkgs.kdePackages.gwenview}/share/applications/org.kde.gwenview.desktop");

  xdg.dataFile."applications/org.kde.dragonplayer.desktop".text = builtins.replaceStrings
    [ "Exec=dragon" ] [ "Exec=${pkgs.kdePackages.dragon}/bin/dragon" ]
    (builtins.readFile "${pkgs.kdePackages.dragon}/share/applications/org.kde.dragonplayer.desktop");

  # Keep undeclared settings writable in KDE's GUI. Activities, monitor layouts
  # and session state remain local; their original files were backed up.
  # Omit verified defaults. Removing a declaration leaves existing local values intact.
  programs.plasma = {
    enable = true;

    input.keyboard = {
      options = [
        "altwin:meta_alt"
        "ctrl:nocaps"
      ];
      repeatDelay = 250;
    };

    kwin = {
      nightLight = {
        enable = true;
        temperature.night = 3600;
      };
    };

    # The panels option deletes/recreates every panel in this plasma-manager version.
    # Update the bottom panel on screen 0 in place, preserving widget IDs and other panels.
    # Runs once per script change at login, leaving subsequent GUI edits writable.
    startup.desktopScript.panel-layout = {
      priority = 2;
      # floatingApplets is stored in plasmashellrc and has no scripting property yet.
      restartServices = [ "plasma-plasmashell" ];
      text = ''
        const layout = ${builtins.toJSON panelWidgets};
        let panel = panels().find(p => p.screen === 0 && p.location === "bottom");
        if (!panel) {
          panel = new Panel();
          panel.screen = 0;
          panel.location = "bottom";
        }
        panel.height = 34;
        panel.floating = false;

        const views = ConfigFile("plasmashellrc", "PlasmaViews");
        const view = ConfigFile(views, "Panel " + panel.id);
        view.writeEntry("floatingApplets", 1);

        // Replace a stock icons-only task manager only when the text version is absent.
        if (panel.widgets("org.kde.plasma.taskmanager").length === 0) {
          panel.widgets("org.kde.plasma.icontasks").forEach(w => w.remove());
        }
        layout.forEach((spec, index) => {
          const widget = panel.widgets(spec.name)[0] || panel.addWidget(spec.name);
          widget.index = index;
          const settings = spec.settings || {};
          Object.keys(settings).forEach(group => {
            widget.currentConfigGroup = group.split("/");
            Object.keys(settings[group]).forEach(key => {
              widget.writeConfig(key, settings[group][key]);
            });
          });
        });
      '';
    };

    configFile = {
      # Upstream writes web-search defaults unconditionally; preserve the local settings.
      kuriikwsfilterrc = lib.mkForce { };
      kdeglobals = {
        KDE = {
          AnimationDurationFactor = 0.5;
          contrast = 4;
        };
        # The places sidebar width otherwise depends on the widget's size hint.
        "KFileDialog Settings"."Speedbar Width" = 140;
      };
      kcminputrc = {
        Mouse.cursorTheme = "breeze_cursors";
      };
      kwinrc = {
        # Preserve existing desktop IDs, which KWin's saved tiling layouts reference.
        Desktops = {
          Rows = 1;
        };
        ElectricBorders = {
          BottomLeft = "ApplicationLauncher";
          BottomRight = "ShowDesktop";
        };
        MouseBindings.CommandTitlebarWheel = "Change Opacity";
      };
      "plasma-localerc".Formats = {
        LANG = "en_US.UTF-8";
        LC_TIME = "en_GB.UTF-8";
      };
      plasmakeyboardrc.General.diacriticsPopupEnabled = false;

      konsolerc = {
        TabBar.CloseTabOnMiddleMouseButton = true;
        MainWindow.MenuBar = "Disabled";
        "MainWindow/Toolbar sessionToolbar".ToolButtonStyle = "TextOnly";
        "Toolbar sessionToolbar".ToolButtonStyle = "TextOnly";
      };

      # Non-default digiKam preferences (checked against 9.1.0).
      # Fonts, application style and date format otherwise depend on the environment.
      digikamrc = {
        "General Settings" = {
          "DateTime Format" = "M/d/yy h:mm Ap";
        };
        "ImageViewer Settings" = {
          "PreviewMode" = 128;
        };
        "Autotags Settings" = {
          "Autotags Object Detection Model" = "none";
        };
      };
    };
  };

  programs.konsole = {
    enable = true;
    defaultProfile = "NixGruvboxLight";
    profiles = lib.genAttrs [ "NixGruvboxLight" "NixGruvboxDark" ] (_: {
      font = {
        name = "Sarasa Mono SC";
        size = 11;
      };
      extraConfig = {
        Scrolling.ScrollBarPosition = 2;
        "Terminal Features" = {
          AnimatingCursorEnabled = true;
          BidiRenderingEnabled = false;
        };
      };
    });
  };
}
