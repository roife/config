local function dap()
  ---@diagnostic disable-next-line: redefined-local
  local dap = package.loaded["dap"]
  if dap then return dap.status() end
  return ""
end

local function osv()
  ---@diagnostic disable-next-line: redefined-local
  local osv = package.loaded["osv"]
  if osv and osv.is_running() then return "Running as debuggee" end
  return ""
end

local function osv_or_dap()
  if osv() ~= "" then
    return osv()
  elseif dap() ~= "" then
    return dap()
  else
    return ""
  end
end

local function is_macro_recording()
  local rec = vim.fn.reg_recording()
  return rec and rec ~= ""
end

local function get_macro_recording() return "Recoding @" .. vim.fn.reg_recording() end

local mode_to_highlight = {
  ["n"] = "normal",
  ["i"] = "insert",
  ["v"] = "visual",
  ["V"] = "visual",
  [""] = "visual",
  ["R"] = "replace",
  ["c"] = "command",
  ["t"] = "terminal",
}

local function get_mode_highlight()
  local mode = vim.api.nvim_get_mode().mode
  return mode_to_highlight[mode] or "_normal"
end

---@type LazyPluginSpec
return {
  "nvim-lualine/lualine.nvim",
  event = "VeryLazy",
  dependencies = {
    "Bekaboo/dropbar.nvim",
  },
  opts = {
    tabline = {
      lualine_a = {
        {
          "tabs",
          mode = 2,
          use_mode_colors = true,
          show_modified_status = false, -- Shows a symbol next to the tab name if the file has been modified.

          -- HACK: show custom tabname
          padding = { left = 1, right = 0 },
          fmt = function(_, ctx)
            local ok, custom_tabname = pcall(vim.api.nvim_tabpage_get_var, ctx.tabId, "tabname")
            if not ok or not custom_tabname or custom_tabname == "" then return "" end
            return custom_tabname .. " "
          end,
        },
      },
      lualine_b = {},
      lualine_c = {
        { "%{%v:lua.dropbar()%}", separator = { left = "", right = "" }, color = "nil" },
      },
      lualine_x = {
        {
          name = "overseer-placeholder",
          function() return "" end,
        },
        osv_or_dap,
        {
          get_macro_recording,
          cond = is_macro_recording,
        },
        {
          "lsp_status",
          icon = "",
          symbols = {
            spinner = { "|", "/", "-", "\\" },
            done = "",
            separator = " ",
          },
          show_name = true,
        },
      },
      lualine_y = {
        {
          "encoding",
          show_bomb = true,
          separator = "",
          cond = function() return vim.bo.fileencoding:lower() ~= "utf-8" or vim.bo.bomb end,
        },
        {
          "fileformat",
          icons_enabled = true,
          symbols = {
            unix = "LF",
            dos = "CRLF",
            mac = "CR",
          },
          cond = function() return vim.bo.fileformat ~= "unix" end,
        },
        "branch",
      },
      lualine_z = {
        {
          "project",
          format = "full",
        },
      },
    },
    sections = {
      lualine_a = {
        {
          "filename",
          file_status = false,
          newfile_status = true,
          path = 1,

          symbols = {
            modified = "*",
            readonly = "%%",
            unnamed = "[No Name]",
            newfile = "[New]",
          },

          fmt = function(str)
            local mode = get_mode_highlight()
            vim.api.nvim_set_hl(0, "LualinePathMixed", {
              fg = vim.api.nvim_get_hl(0, { name = "lualine_b_normal" }).bg,
              bg = vim.api.nvim_get_hl(0, { name = "lualine_a_" .. mode }).bg,
              nocombine = false,
            })

            vim.api.nvim_set_hl(0, "LualineFilename", {
              fg = vim.api.nvim_get_hl(0, { name = "lualine_a_" .. mode }).fg,
              bg = vim.api.nvim_get_hl(0, { name = "lualine_a_" .. mode }).bg,
              bold = true,
              italic = vim.bo.modified,
              underline = vim.bo.readonly,
            })

            if str == "" or str:find("://", 1, true) then return "%#LualineFilename#" .. str end

            local path, fname = str:match("^(.*[/\\\\])([^/\\\\]+)$")
            if not path then return "%#LualineFilename#" .. str end

            return "%#LualinePathMixed#" .. path .. "%#LualineFilename#" .. fname
          end,
        },
      },
      lualine_b = {
        {
          "searchcount",
          maxcount = 999,
          timeout = 500,
        },
        {
          function() return require("symbol_marks").lualine.get() end,
          cond = function() return require("symbol_marks").lualine.has() end,
        },
      },
      lualine_c = {},
      lualine_x = {},
      lualine_y = {},
      lualine_z = {
        "location",
      },
    },
    inactive_sections = {
      lualine_a = {
        {
          "filename",
          file_status = false,
          newfile_status = true,
          path = 1,

          symbols = {
            modified = "*",
            readonly = "%%",
            unnamed = "[No Name]",
            newfile = "[New]",
          },

          fmt = function(str)
            vim.api.nvim_set_hl(0, "LualineInactiveFilename", {
              fg = vim.api.nvim_get_hl(0, { name = "lualine_a_normal" }).bg,
              bg = vim.api.nvim_get_hl(0, { name = "lualine_a_inactive" }).bg,
              bold = true,
              italic = vim.bo.modified,
              underline = vim.bo.readonly,
            })

            if str == "" or str:find("://", 1, true) then
              return "%#LualineInactiveFilename#" .. str
            end

            local path, fname = str:match("^(.*[/\\\\])([^/\\\\]+)$")
            if not path then return "%#LualineInactiveFilename#" .. str end

            return "%#lualine_a_inactive#"
              .. path
              .. "%#LualineInactiveFilename#"
              .. fname
              .. "%#lualine_a_inactive#"
          end,
        },
      },
      lualine_b = {},
      lualine_c = {},
      lualine_x = {},
      lualine_y = {},
      lualine_z = {
        "location",
      },
    },
    options = {
      icons_enabled = false,
      theme = "auto",
      always_divide_middle = true,
      always_show_tabline = true,
      globalstatus = false,
      section_separators = { left = "", right = "" },
      component_separators = { left = "", right = "" },
    },
    extensions = {
      "man",
      "quickfix",
      "nvim-tree",
      "neo-tree",
      "toggleterm",
      "symbols-outline",
      "aerial",
      "fugitive",
      "nvim-dap-ui",
      "mundo",
      "lazy",
      "fzf",
      "oil",
      "overseer",
    },
  },
  config = function(_, opts) require("lualine").setup(opts) end,
}
