{ lib, pkgs, ... }:
let
  families = [ "Sans" "Serif" ];
  regions = { "zh-HK" = "HK"; "zh-TW" = "TC"; ja = "JP"; ko = "KR"; };

  alias = family: fonts: {
    "@binding" = "strong";
    inherit family;
    prefer.family = fonts;
  };

  # Prefer the locale's regional CJK variant, keeping SC as a fallback.
  localeAlias = family: lang: region:
    alias "Noto ${family} CJK SC" [ "Noto ${family} CJK ${region}" ] // {
      test = {
        "@name" = "lang";
        string = lang;
      };
    };

in
{
  # Home Manager installs these into ~/Library/Fonts on macOS.
  home.packages = with pkgs; [
    sarasa-gothic
    noto-fonts
    noto-fonts-cjk-sans
    noto-fonts-cjk-serif
    noto-fonts-color-emoji
  ];

  # Linux uses Fontconfig; settings are wrapped in <fontconfig> by Home Manager.
  fonts.fontconfig = lib.mkIf pkgs.stdenv.hostPlatform.isLinux {
    enable = true;
    # enable defaults to false before stateVersion 26.11.
    configFile.preferences.enable = true;
    configFile.preferences.settings = {
      alias = [
        (alias "system-ui" [ "sans-serif" ])
        (alias "sans-serif" [ "Noto Sans" "Noto Sans CJK SC" "Noto Color Emoji" ])
        (alias "serif" [ "Noto Serif" "Noto Serif CJK SC" "Noto Color Emoji" ])
        (alias "monospace" [ "Sarasa Mono SC" "Noto Color Emoji" ])
      ] ++ lib.concatMap (family: lib.mapAttrsToList (localeAlias family) regions) families;
    };
  };
}
