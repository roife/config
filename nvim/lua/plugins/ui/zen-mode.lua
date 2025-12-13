---@type LazyPluginSpec
return {
  "folke/zen-mode.nvim",
  opts = {},
  keys = {
    {
      "<leader>tz",
      function() require("zen-mode").toggle() end,
      desc = "Zen Mode",
    },
  },
}
