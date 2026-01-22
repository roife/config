---@type LazyPluginSpec
return {
  "Shatur/neovim-session-manager",
  event = "VeryLazy",
  dependencies = {
    "nvim-lua/plenary.nvim",
  },
  opts = function()
    local config = require("session_manager.config")

    return {
      autoload_mode = config.AutoloadMode.Disabled,
    }
  end,
  config = function(_, opts) require("session_manager").setup(opts) end,
  keys = {
    {
      "<leader>sls",
      "<cmd>SessionManager load_session<CR>",
      desc = "Load selected",
    },
    {
      "<leader>sll",
      "<cmd>SessionManager load_last_session<CR>",
      desc = "Load last",
    },
    { "<leader>sd", "<cmd>SessionManager delete_session<CR>", desc = "Delete" },
    -- { "<leader>scs", "<cmd>SessionManager save_current_session<CR>", desc = "Save" },
    -- { "<leader>scl", "<cmd>SessionManager load_current_dir_session<CR>", desc = "Load" },
    {
      "<leader>sc",
      "<cmd>SessionManager load_current_dir_session<CR>",
      desc = "Load Current",
    },
  },
}
