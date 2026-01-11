---@type LazyPluginSpec
return {
  "ahkohd/difft.nvim",
  event = "VeryLazy",
  keys = {
    {
      "<leader>gdD",
      function()
        if Difft.is_visible() then
          Difft.hide()
        else
          Difft.diff()
        end
      end,
      desc = "Toggle Difft",
    },
  },
  config = function()
    require("difft").setup {
      command = "GIT_EXTERNAL_DIFF='difft --color=always' git diff",
      layout = "float",
    }
  end,
}
