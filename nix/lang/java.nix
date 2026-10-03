{ pkgs, ... }:
{
  programs.java = {
    enable = true;
    package = pkgs.jdk21;
  };
  home.packages = [ pkgs.jdt-language-server ];
  home.file = {
    ".jdks/21".source = pkgs.jdk21.home;
  };
  home.sessionVariables = {
    JAVA21_HOME = pkgs.jdk21.home;
    JDTLS_JAVA_HOME = pkgs.jdk21.home;
  };
}
