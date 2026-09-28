{ rimeFrost, rimeGrammar }:
{ config, lib, pkgs, ... }:
let
  rimeDirectory =
    if pkgs.stdenv.hostPlatform.isDarwin then "${config.home.homeDirectory}/Library/Rime"
    else "${config.xdg.dataHome}/rime";

  userFiles = lib.filterAttrs (_: type: type == "regular")
    (builtins.readDir config.programs.rime.userConfigDirectory);
in
{
  options.programs.rime.userConfigDirectory = lib.mkOption {
    type = lib.types.path;
    description = "Directory whose regular files override the upstream Rime configuration.";
  };

  config.home = {
    file = lib.mapAttrs' (file: _: lib.nameValuePair "${rimeDirectory}/${file}" {
      source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.config/rime/${file}";
    }) userFiles // {
      "${rimeDirectory}/wanxiang-lts-zh-hans.gram" = {
        source = rimeGrammar;
        force = true;
      };
    };

    # Copy the scheme before Emacs starts, preserving config/model links and runtime data.
    activation.deployRime =
      lib.hm.dag.entryBetween [ "reloadSystemd" "setupLaunchAgents" ] [ "linkGeneration" ] ''
        run ${pkgs.coreutils}/bin/mkdir -p ${lib.escapeShellArg rimeDirectory}
        run ${pkgs.rsync}/bin/rsync -rltpc --chmod=u+rwX \
          --exclude=/wanxiang-lts-zh-hans.gram \
          ${lib.escapeShellArgs (lib.mapAttrsToList (file: _: "--exclude=/${file}") userFiles)} \
          ${rimeFrost}/ ${lib.escapeShellArg "${rimeDirectory}/"}
      '';
  };
}
