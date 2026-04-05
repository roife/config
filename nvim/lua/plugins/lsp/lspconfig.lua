---@type LazyPluginSpec
return {
  "neovim/nvim-lspconfig",
  event = {
    "FileType",
  },
  dependencies = {
    "folke/neoconf.nvim",
  },
}
