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

---@type LazyPluginSpec
return {
  "nvim-lualine/lualine.nvim",
  event = "VeryLazy",
  dependencies = {
    "Bekaboo/dropbar.nvim",
  },
  opts = {
    sections = {
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
        {
          require("noice").api.status.mode.get,
          cond = require("noice").api.status.mode.has,
          color = { fg = "#ff9e64" },
        },
      },
      lualine_b = {
        {
          "filename",
          file_status = true,
          newfile_status = true,
          path = 1,

          symbols = {
            modified = "*",
            readonly = "%",
            unnamed = "[No Name]",
            newfile = "[New]",
          },
        },
      },
      lualine_c = {
        { "%{%v:lua.dropbar()%}", separator = { left = "", right = "" }, color = "nil" },
      },
      lualine_x = {
        {
          name = "overseer-placeholder",
          function() return "" end,
        },
        osv_or_dap,
        "location",
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
      },
      lualine_z = {
        "branch",
      },
    },
    inactive_sections = {
      lualine_a = {
        {
          "filename",
          file_status = true,
          newfile_status = true,
          path = 1,

          shorting_target = 40,
          symbols = {
            modified = "*",
            readonly = "%",
            unnamed = "[No Name]",
            newfile = "[New]",
          },
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
      always_show_tabline = false,
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
    },
  },
  config = function(_, opts) require("lualine").setup(opts) end,
}
