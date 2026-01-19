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
      {
        name = "Typst build blog post",
        builder = function()
          return {
            cmd = { "typst" },
            args = {
              "compile",
              vim.fn.expand("%:p"),
              "--root",
              vim.fn.getcwd(),
            },
            default_component_params = {
              errorformat = [[%Eerror: %m,]]
                .. [[%Wwarning: %m,]]
                .. [[%C %#┌─ %f:%l:%c,]]
                .. [[%-G%.%#]],
            },
          }
        end,
        condition = {
          filetype = { "typst" },
        },
      },
      {
        name = "Typst open blog post",
        builder = function()
          return {
            cmd = { "open" },
            args = {
              vim.fn.expand('%:r') .. '.pdf'
            },
          }
        end,
        condition = {
          filetype = { "typst" },
        },
      },
    }
    for _, template in ipairs(templates) do
      overseer.register_template(template)
    end
  end,
}
