---@type LazyPluginSpec
return {
  "rcarriga/nvim-dap-ui",
  dependencies = { "nvim-neotest/nvim-nio" },
  init = function()
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "dapui_*",
      desc = "Name nvim-dap-ui tabs",
      callback = function() require("utils").set_tabname("dap-ui") end,
    })
  end,
  opts = {
    icons = {
      collapsed = "+",
      current_frame = "*",
      expanded = "-",
    },
  },
  keys = {
    {
      "<leader>du",
      function() require("dapui").toggle() end,
      desc = "Toggle full UI",
    },
    {
      "<leader>de",
      function() require("dapui").eval() end,
      desc = "Evaluate expression",
      mode = { "n", "v" },
    },

    {
      "<leader>ds",
      function()
        require("dapui").float_element("stacks", {
          width = 60,
          height = 20,
          enter = true,
          position = "center",
        })
      end,
      desc = "Open stacks",
    },
    {
      "<leader>dw",
      function()
        require("dapui").float_element("watches", {
          width = 60,
          height = 20,
          enter = true,
          position = "center",
        })
      end,
      desc = "Open watches",
    },
    {
      "<leader>dv",
      function()
        require("dapui").float_element("scopes", {
          width = 60,
          height = 20,
          enter = true,
          position = "center",
        })
      end,
      desc = "Open scopes",
    },
    {
      "<leader>dc",
      function()
        require("dapui").float_element("console", {
          width = 60,
          height = 20,
          enter = true,
          position = "center",
        })
      end,
      desc = "Open console",
    },
    {
      "<leader>dr",
      function()
        require("dapui").float_element("repl", {
          width = 60,
          height = 20,
          enter = true,
          position = "center",
        })
      end,
      desc = "Open repl",
    },
  },
}
