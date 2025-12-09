---@type LazyPluginSpec
return {
  "ahmedkhalf/project.nvim",
  event = "VeryLazy",
  opts = {
    ignore_lsp = { "jsonls", "yamlls", "taplo" },
  },
  config = function() require("project_nvim").setup {} end,
}
