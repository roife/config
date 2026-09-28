{ rimeFrost, rimeGrammar }:
{ config, lib, pkgs, ... }:
let
  rimeDirectory =
    if pkgs.stdenv.hostPlatform.isDarwin then "${config.home.homeDirectory}/Library/Rime"
    else "${config.xdg.dataHome}/rime";

  upstreamFiles = lib.listToAttrs (map (source: {
    name = lib.removePrefix "${rimeFrost}/" (builtins.unsafeDiscardStringContext source);
    value = source;
  }) (lib.filesystem.listFilesRecursive "${rimeFrost}"));

  userFiles = lib.mapAttrs (name: _:
    config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.config/rime/${name}"
  ) (lib.filterAttrs (_: type: type == "regular")
    (builtins.readDir config.programs.rime.userConfigDirectory));

  gramFile = {
    "wanxiang-lts-zh-hans.gram" = rimeGrammar;
  };

  files = upstreamFiles // userFiles // gramFile;
in
{
  options.programs.rime.userConfigDirectory = lib.mkOption {
    type = lib.types.path;
    description = "Directory whose regular files override the upstream Rime configuration.";
  };

  # Home Manager removes obsolete upstream links and leaves runtime data alone.
  config.home.file = lib.mapAttrs' (name: source:
    lib.nameValuePair "${rimeDirectory}/${name}" {
      inherit source;
    }
  ) files;
}
