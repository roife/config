---@type LazyPluginSpec
return {
  "folke/noice.nvim",
  event = "VeryLazy",
  init = function()
    vim.o.cmdheight = 0

    -- Make sure to load noice when notify is called
    ---@diagnostic disable-next-line: duplicate-set-field
    vim.notify = function(...) require("noice").notify(...) end
  end,
  dependencies = {
    "MunifTanjim/nui.nvim",
    "rcarriga/nvim-notify",
  },
  opts = {
    routes = {
      {
        filter = { event = "msg_show", min_height = 20 },
        view = "cmdline_output",
      },
    },
    cmdline = {
      format = {
        cmdline = { icon = "❯" },
        filter = { icon = "" },
        search_down = {
          view = "cmdline",
          icon = "Search:",
        },
        search_up = {
          view = "cmdline",
          icon = "Search (reversed):",
        },
        lua = { icon = "" },
        help = { icon = "" },
        input = { icon = "" },
        substitute = {
          pattern = {
            "^:%s*%%s?n?o?m?/",
            "^:'<,'>%s*s?n?m?/",
            "^:%d+,%d+%s*s?n?m?/",
          },
          icon = "Replacing:",
          view = "cmdline",
          lang = "regex",
        },
      },
    },
    popupmenu = {
      kind_icons = false,
    },
    markdown = {
      hover = {
        ["%[.-%]%((%S-)%)"] = function(...) vim.ui.open(...) end,
      },
    },
    lsp = {
      progress = {
        throttle = 100,
      },
      override = {
        ["vim.lsp.util.convert_input_to_markdown_lines"] = true,
        ["vim.lsp.util.stylize_markdown"] = true,
        ["cmp.entry.get_documentation"] = true,
      },
    },
    views = {
      hover = {
        size = {
          max_width = 80,
        },
      },
    },
    presets = {
      long_message_to_split = true,
      command_palette = true,
    }
  },
  keys = {
    {
      "<leader>fn",
      "<Cmd>Noice fzf<CR>",
      desc = "Noitification",
    },
  },
}
