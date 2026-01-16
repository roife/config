---@type LazyPluginSpec
return {
  "stevearc/overseer.nvim",
  keys = {
    { "<leader>rr", "<cmd>OverseerRun<CR>", desc = "Run" },
    { "<leader>rl", "<cmd>OverseerToggle<CR>", desc = "List" },
    { "<leader>rn", "<cmd>OverseerBuild<CR>", desc = "New" },
    { "<leader>ra", "<cmd>OverseerTaskAction<CR>", desc = "Action" },
    { "<leader>ri", "<cmd>OverseerInfo<CR>", desc = "Info" },
    { "<leader>rc", "<cmd>OverseerClearCache<CR>", desc = "Clear cache" },
  },
  opts = function()
    return {
      dap = false,
      component_aliases = {
        default = {
          "on_exit_set_status",
          "on_complete_notify",
          { "on_output_quickfix", items_only = true, open_on_match = true, focus = true },
          "on_complete_dispose",
          "unique",
        },
      },
    }
  end,
  config = function(_, opts)
    local overseer = require("overseer")

    overseer.setup(opts)

    do -- For lazy loading lualine component
      local success, lualine = pcall(require, "lualine")
      if not success then return end
      local lualine_cfg = lualine.get_config()
      for i, item in ipairs(lualine_cfg.tabline.lualine_x) do
        if type(item) == "table" and item.name == "overseer-placeholder" then
          lualine_cfg.tabline.lualine_x[i] = "overseer"
        end
      end
      lualine.setup(lualine_cfg)
    end

    local templates = {
      {
        name = "C++ build single file",
        builder = function()
          return {
            cmd = { "c++" },
            args = {
              "-g",
              vim.fn.expand("%:p"),
              "-o",
              vim.fn.expand("%:p:t:r"),
            },
          }
        end,
        condition = {
          filetype = { "cpp" },
        },
      },
    }
    for _, template in ipairs(templates) do
      overseer.register_template(template)
    end
  end,
}
