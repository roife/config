{ pkgs, ... }:
{
  nixpkgs.hostPlatform = "aarch64-darwin";
  system.stateVersion = 6;
  system.primaryUser = "roifewu";
  users.users.roifewu.home = "/Users/roifewu";
  programs.fish.enable = true;
  environment.shells = [ pkgs.fish ];

  # System generations also retain the integrated Home Manager closure.
  nix.gc = {
    automatic = true;
    options = "--delete-older-than 30d";
  };

  nix-homebrew = {
    enable = true;
    user = "roifewu";
  };

  homebrew = {
    enable = true;
    brews = [ "mas" "coreutils" ];
    casks = [
      "bettertouchtool"
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
}
