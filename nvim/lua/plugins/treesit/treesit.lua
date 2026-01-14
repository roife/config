---@type LazyPluginSpec
return {
  "nvim-treesitter/nvim-treesitter",
  build = ":TSUpdate",
  lazy = false,
  opts = {
    install_dir = vim.fs.joinpath(vim.fn.stdpath("data"), "site"),
    highlight = { enable = true },
    indent = { enable = true },
  },

  config = function(_, opts) require("nvim-treesitter.configs").setup(opts) end,
}
