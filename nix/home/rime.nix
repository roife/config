{ config, lib, pkgs, ... }:
let
  rimeDir =
    if pkgs.stdenv.hostPlatform.isDarwin then "${config.home.homeDirectory}/Library/Rime"
    else "${config.xdg.dataHome}/rime";

  schema = "double_pinyin_flypy";
  grammarModel = "wanxiang-lts-zh-hans";
  segmentSchema = "liberime_regexp_segment";
  segmentBackend = "liberime_regexp_segment_rime_ice";

  # The gateway transports requests; the backend queries canonical dictionary
  # codes, independently of the active input method's double-pinyin spelling.
  segmentSchemas = {
    ${segmentSchema} = {
      schema = {
        schema_id = segmentSchema;
        name = "Emacs word segmentation";
        version = "1";
        dependencies = [ segmentBackend ];
      };
      engine = {
        processors = [ "speller" ];
        segmentors = [ "abc_segmentor" ];
        translators = [ "lua_translator@*liberime_regexp_segment" ];
      };
      speller.alphabet = "abcdefghijklmnopqrstuvwxyz0123456789";
      segment.backends.rime_ice = segmentBackend;
    };
    ${segmentBackend} = {
      schema = { schema_id = segmentBackend; name = "Segmentation dictionary"; version = "1"; };
      speller = { delimiter = " '"; algebra = [ ]; };
      translator = {
        dictionary = "rime_ice";
        prism = segmentBackend;
        enable_user_dict = false;
        enable_completion = false;
      };
    };
  };

  # Patches in *.custom.yaml, following rime-ice's README and others/patch_examples.
  # Only values that differ from upstream are listed; redeploy Rime after switching.
  patches = {
    default = {
      schema_list = [ { inherit schema; } { schema = segmentSchema; } ];
      "menu/page_size" = 9;
      "switcher/hotkeys" = [ ];
      "ascii_composer/switch_key/Caps_Lock" = "noop";
      "ascii_composer/switch_key/Shift_L" = "noop";
      "key_binder/bindings" = [
        { when = "composing"; accept = "Shift+Tab"; send = "Shift+Left"; }
        { when = "composing"; accept = "Tab"; send = "Shift+Right"; }
        { when = "has_menu"; accept = "minus"; send = "Page_Up"; }
        { when = "has_menu"; accept = "equal"; send = "Page_Down"; }
      ];
    };

    ${schema} = {
      grammar = {
        language = grammarModel;
        non_collocation_penalty = -4;
        collocation_max_length = 5;
        collocation_min_length = 2;
        collocation_penalty = -14;
      };
      "translator/contextual_suggestions" = true;
      "translator/max_homophones" = 6;
      "translator/max_homographs" = 2;
    };

    # Double-pinyin spelling for English derivations and radical lookup.
    melt_eng."speller/algebra".__include = "melt_eng.schema.yaml:/algebra_${schema}";
    radical_pinyin."speller/algebra".__include = "radical_pinyin.schema.yaml:/algebra_${schema}";
  };

  # Merged with the colour scheme by nix-colorscheme, which owns squirrel.custom.yaml.
  squirrelPatch = {
    app_options = {
      "com.apple.Spotlight".ascii_mode = true;
      "com.mitchellh.ghostty".ascii_mode = true;
      "org.gnu.Emacs" = { ascii_mode = true; no_inline = true; };
    };
    style = {
      text_orientation = "horizontal";
      candidate_list_layout = "linear";
      candidate_format = "%c %@";
      inline_preedit = true;
      corner_radius = 6;
      hilited_corner_radius = 0;
      border_height = 0;
      border_width = 0;
      line_spacing = 5;
      spacing = 10;
      font_point = 18;
      label_font_point = 15;
      comment_font_point = 15;
    };
  };

  yaml = pkgs.formats.yaml { };
  # Generate "${rimeDir}/NAME.SUFFIX.yaml" from each attribute, transformed by F.
  yamlFiles = suffix: f: lib.mapAttrs' (name: value:
    lib.nameValuePair "${rimeDir}/${name}.${suffix}.yaml" {
      source = yaml.generate "${name}.${suffix}.yaml" (f value);
    });
in
{
  colorscheme.squirrel.extraPatch = squirrelPatch;

  # Link files individually so Rime can still write build/, user dbs and sync/.
  home.file = {
    ${rimeDir} = {
      source = "${pkgs.rime-ice}/share/rime-data";
      recursive = true;
    };
    "${rimeDir}/default.yaml".source = "${pkgs.rime-ice}/share/rime-data/rime_ice_suggestion.yaml";
    "${rimeDir}/lua/liberime_regexp_segment.lua".source =
      config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/code/liberime-regexp/rime/liberime_regexp_segment.lua";
    "${rimeDir}/${grammarModel}.gram" = {
      source = pkgs.fetchurl {
        url = "https://github.com/jetcookies/RIME-LMDG-tracker/releases/download/0-unstable-2026-10-09/${grammarModel}.gram";
        hash = "sha256-YWnzXUiqEBjm7/0Wy2rgfzB5ZM/+XYx5uX+vIWRpO+w=";
      };
      force = true; # Replace the file written by the former activation hook.
    };
  } // yamlFiles "schema" lib.id segmentSchemas
    // yamlFiles "custom" (patch: { inherit patch; }) patches;

  home.packages = [ pkgs.librime ];
}
