{ pkgs, ... }:
{
  home.packages = with pkgs; [ ruff pyrefly ];

  programs.uv = {
    enable = true;
    tool.packages = [ "twitter-cli" ];
  };
}
