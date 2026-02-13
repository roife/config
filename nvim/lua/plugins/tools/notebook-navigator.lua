---@LazyPluginSpec
return {
  "vandalt/NotebookNavigator.nvim",
  keys = {
    { "]h", function() require("notebook-navigator").move_cell "d" end },
    { "[h", function() require("notebook-navigator").move_cell "u" end },
    { "<localleader>X", "<cmd>lua require('notebook-navigator').run_cell()<cr>" },
    { "<localleader>x", "<cmd>lua require('notebook-navigator').run_and_move()<cr>" },
  },
  dependencies = {
    "hkupty/iron.nvim", -- repl provider
  },
  event = "VeryLazy",
  config = function(_, opts)
    local nn = require "notebook-navigator"
    nn.setup{}
  end,
}
