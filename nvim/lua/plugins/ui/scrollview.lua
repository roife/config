---@type LazyPluginSpec
return {
  "dstein64/nvim-scrollview",
  event = "VeryLazy",
  opts = {
    winblend = 50,
    winblend_gui = 50,
    floating_windows = true,
    consider_border = true,
    excluded_filetypes = {
      "dropbar_menu",
      "cmp_docs",
      "cmp_menu",
      "blink-cmp-menu",
      "blink-cmp-documentation",
      "blink-cmp-signature",
      "noice",
    },
    signs_on_startup = {
      "cursor",
      "conflicts",
      "diagnostics",
      "keywords",
      "latestchange",
      "loclist",
      "marks",
      "quickfix",
      "search",
      "spell",
    },
    signs_scrollbar_overlap = "over",
    signs_max_per_row = 2,
    visibility = "info",

    cursor_priority = 100,
    latestchange_priority = 90,
  },
  config = function(_, opts)
    local scrollview = require("scrollview")
    local scrollview_gitsigns = require("scrollview.contrib.gitsigns")

    scrollview.setup(opts)
    scrollview_gitsigns.setup {
      add_highlight = "GitSignsAdd",
      change_highlight = "GitSignsChange",
      delete_highlight = "GitSignsDelete",
    }
  end,
}
