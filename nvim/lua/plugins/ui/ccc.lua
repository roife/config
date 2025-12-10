---@type LazyPluginSpec
return {
  "uga-rosa/ccc.nvim",
  event = "VeryLazy",
  opts = {
    highlighter = {
      auto_enable = true,
      lsp = true,
    },
  },
  config = function(_, opts)
    require("ccc").setup(opts)
    vim.cmd.CccHighlighterEnable()
  end,
}
