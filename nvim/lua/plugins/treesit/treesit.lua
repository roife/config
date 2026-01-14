---@type LazyPluginSpec
return {
  "nvim-treesitter/nvim-treesitter",
  build = ":TSUpdate",
  lazy = false,
  config = function(_, opts) require("nvim-treesitter.configs").setup(opts) end,
}
