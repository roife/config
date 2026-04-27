--- @type LazyPluginSpec
return {
  "folke/twilight.nvim",
  event = "VeryLazy",
  keys = {
    { "<leader>tw", "<cmd>Twilight<cr>", desc = "Toggle Twilight" },
  },
  opts = {
    expand = { -- for treesitter, we we always try to expand to the top-most ancestor with these types
      "function",
      "method",
      "table",
      "section",
    },
  },
}
