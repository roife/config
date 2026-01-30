---@type LazyPluginSpec
return {
  "otavioschwanck/fzf-lua-explorer.nvim",
  dependencies = { "ibhagwan/fzf-lua" },
  keys = {
    { "<leader>fe", function() require('fzf-lua-explorer').explorer() end, desc = "Explorer" }
  },
  opts = {
    show_icons = false,
    create_file_from_input = true,
  },
  config = function(_, opts)
    require("fzf-lua-explorer").setup(opts)
  end
}
