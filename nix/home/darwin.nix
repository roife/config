# macOS-only layer on top of ./default.nix; imported by flake.nix.
# Only non-default preferences are declared; undeclared ones stay writable in
# System Settings. Removing a declaration leaves the current value in place.
# Some settings take effect after logging out and back in.
{ lib, ... }:
{
  imports = [ ../modules/homebrew.nix ];

  homebrew = {
    brews = [ "mas" "coreutils" ];
    casks = [
      "bettertouchtool"
      "chatgpt" # Includes the Codex desktop workspace.
      "ghostty"
      "squirrel-app"
    ];
    masApps = {
      "AdGuard for Safari" = 1440147259;
      "Bob" = 1630034110;
      "QQ" = 451108668;
      "Quantumult X" = 1443988620;
      "Telegram" = 747648890;
      "TencentMeeting" = 1484048379;
      "WeChat" = 836500024;
      "Xcode" = 497799835;
    };
  };

  targets.darwin.defaults = {
    NSGlobalDomain = {
      AppleLanguages = [ "en-CN" "zh-Hans-CN" ];
      AppleLocale = "en_CN";
      AppleInterfaceStyleSwitchesAutomatically = true;
      NSGlassTintAmount = 1.0; # Liquid Glass tint, set in Appearance.
      AppleKeyboardUIMode = 2; # Keyboard navigation with Tab.
      InitialKeyRepeat = 15;
      KeyRepeat = 2;
      "com.apple.keyboard.fnState" = true; # F1-F12 as standard function keys.
      NSAutomaticPeriodSubstitutionEnabled = false;
    };

    "com.apple.dock" = {
      autohide = true;
      tilesize = 45;
      enterMissionControlByTopWindowDrag = false;
      persistent-apps = [
        "/Applications/Safari.app"
        "/Applications/WeChat.app"
        "/Applications/企业微信.app"
        "/System/Applications/Reminders.app"
        "/Applications/ChatGPT.app"
      ];
    };

    "com.apple.finder".FXPreferredViewStyle = "clmv"; # Column view.
    "com.apple.WindowManager".EnableTiledWindowMargins = false;
    "com.apple.AppleMultitouchTrackpad" = {
      Clicking = true;
      TrackpadThreeFingerHorizSwipeGesture = 0;
      TrackpadThreeFingerVertSwipeGesture = 0;
      # Light click on the built-in Force Touch trackpad.
      FirstClickThreshold = 0;
      SecondClickThreshold = 0;
    };
    "com.apple.driver.AppleBluetoothMultitouch.trackpad" = {
      Clicking = true;
      TrackpadThreeFingerHorizSwipeGesture = 0;
      TrackpadThreeFingerVertSwipeGesture = 0;
    };
    "com.apple.HIToolbox".AppleFnUsageType = 3; # Press fn to start dictation.
    "com.apple.loginwindow".TALLogoutSavesState = false; # Do not reopen windows.
    "com.apple.AdLib".allowApplePersonalizedAdvertising = false;
  };

  targets.darwin.currentHostDefaults.NSGlobalDomain = {
    "com.apple.mouse.tapBehavior" = 1;
    # Caps Lock → Control on the built-in keyboard (ctrl:nocaps in kde.nix).
    "com.apple.keyboard.modifiermapping.0-0-0" = [
      {
        HIDKeyboardModifierMappingSrc = lib.fromHexString "0x700000039"; # Caps Lock
        HIDKeyboardModifierMappingDst = lib.fromHexString "0x7000000E4"; # Right Control
      }
    ];
  };
}
