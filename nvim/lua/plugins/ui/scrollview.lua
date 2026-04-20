---@type LazyPluginSpec
return {
  "dstein64/nvim-scrollview",
  event = "VeryLazy",
  opts = {
    excluded_filetypes = {
      "dropbar_menu",
      "cmp_docs",
      "cmp_menu",
      "blink-cmp-menu",
      "blink-cmp-documentation",
      "blink-cmp-signature",
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
    signs_max_per_row = 1,
    visibility = "info",
    base = "left",
    column = 1,

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
