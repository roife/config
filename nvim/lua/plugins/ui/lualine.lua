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

local function osv_or_dap_and_filetype()
  local osv_or_dap = osv_or_dap()
  if osv_or_dap and osv_or_dap ~= "" then osv_or_dap = " (" .. osv_or_dap .. ")" end
  return vim.bo.filetype .. osv_or_dap
end

local function mode()
  -- Map of modes to their respective shorthand indicators
  local mode_map = {
    n = "N", -- Normal mode
    i = "I", -- Insert mode
    v = "V", -- Visual mode
    [""] = "V", -- Visual block mode
    V = "V", -- Visual line mode
    c = "C", -- Command-line mode
    no = "N", -- NInsert mode
    s = "S", -- Select mode
    S = "S", -- Select line mode
    ic = "I", -- Insert mode (completion)
    R = "R", -- Replace mode
    Rv = "R", -- Virtual Replace mode
    cv = "C", -- Command-line mode
    ce = "C", -- Ex mode
    r = "R", -- Prompt mode
    rm = "M", -- More mode
    ["r?"] = "?", -- Confirm mode
    ["!"] = "!", -- Shell mode
    t = "T", -- Terminal mode
  }
  -- Return the mode shorthand or [UNKNOWN] if no match
  return mode_map[vim.fn.mode()] or "[UNKNOWN]"
end

---@type LazyPluginSpec
return {
  "nvim-lualine/lualine.nvim",
  init = function() vim.o.laststatus = 0 end,
  event = "VeryLazy",
  opts = {
    sections = {
      lualine_a = {
        {
          "tabs",
          mode = 2,
          use_mode_colors = true,
          show_modified_status = true, -- Shows a symbol next to the tab name if the file has been modified.
          symbols = {
            modified = "*", -- Text to show when the file is modified.
          },
        },
      },
      lualine_b = {
        { "%{%v:lua.dropbar()%}", separator = { left = "", right = "" }, color = "nil" },
      },
      lualine_c = {},
      lualine_x = {
        {
          name = "overseer-placeholder",
          function() return "" end,
        },
        {
          "encoding",
          show_bomb = true,
          separator = "",
          cond = function() return vim.bo.fileencoding:lower() ~= "utf-8" or vim.bo.bomb end,
        },
        "branch",
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
      lualine_y = {
        osv_or_dap_and_filetype,
      },
      lualine_z = {
        "location",
      },
    },
    options = {
      icons_enabled = false,
      theme = "auto",
      always_divide_middle = true,
      globalstatus = true,
      section_separators = { left = "", right = "" },
      component_separators = { left = "", right = "|" },
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
