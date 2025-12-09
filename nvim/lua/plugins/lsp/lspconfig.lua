---@type LazyPluginSpec
return {
  "neovim/nvim-lspconfig",
  event = {
    "Filetype",
  },
  dependencies = {
    "folke/neoconf.nvim",
  },
  keys = {
    {
      "<leader>lR",
      function() vim.cmd.LspRestart() end,
      desc = "Reload",
    },
    {
      "<leader>lI",
      function() vim.cmd.LspInfo() end,
      desc = "Info",
    },
  },
  config = function(_, opts)
      vim.lsp.config('lua_ls', {
          cmd = { '/Users/roife/code/lua-language-server/bin/lua-language-server' }
      })
  end,
}
