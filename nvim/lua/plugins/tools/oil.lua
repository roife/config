---@type LazyPluginSpec
return {
  "stevearc/oil.nvim",
  enabled = false,
  lazy = false,
  keys = {
    {
      "-",
      function() require("oil").open() end,
      desc = "Open parent directory",
    },
  },
  opts = {
    skip_confirm_for_simple_edits = true,
    cleanup_delay_ms = false,
    keymaps = {
      ["<C-s>"] = "actions.select_split",
      ["<C-v>"] = "actions.select_vsplit",
    },
  },
}
