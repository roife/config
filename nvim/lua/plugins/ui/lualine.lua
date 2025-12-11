local function lsp()
  local clients = vim.lsp.get_clients()
  local buf = vim.api.nvim_get_current_buf()
  clients = vim
    .iter(clients)
    :filter(function(client) return client.attached_buffers[buf] end)
    :filter(function(client) return client.name ~= "GitHub Copilot" end)
    :map(function(client) return client.name end)
    :totable()
  local info = table.concat(clients, " ")
  if info == "" then
    return ""
  else
    return info
  end
end

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

local function dap_or_lsp()
  if osv() ~= "" then
    return osv()
  elseif dap() ~= "" then
    return dap()
  else
    return lsp()
  end
end

local function dap_or_lsp_and_filetype()
  local dap_or_lsp = dap_or_lsp()
  if dap_or_lsp and dap_or_lsp ~= "" then dap_or_lsp = " (" .. dap_or_lsp .. ")" end
  return vim.bo.filetype .. dap_or_lsp
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
    tabline = {
      lualine_a = {
        mode,
      },
      lualine_b = {
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
      lualine_c = {
        "branch",
        {
          "diagnostics",
          symbols = { error = "✘ ", warn = "! ", info = "⚑ ", hint = "ℹ " },
        },
        --          { "%{%v:lua.dropbar()%}", separator = { left = "", right = "" } },
      },
      lualine_x = {
        {
          name = "overseer-placeholder",
          function() return "" end,
        },
        dap_or_lsp_and_filetype,
        {
          "encoding",
          show_bomb = true,
          separator = "",
        },
        {
          "fileformat",
          icons_enabled = true,
          symbols = {
            unix = "LF",
            dos = "CRLF",
            mac = "CR",
          },
        },
      },
      lualine_y = {
        "filesize",
        -- { "progress", separator = "·" },
      },
      lualine_z = {
        "location",
      },
    },
    sections = nil,
    options = {
      icons_enabled = false,
      theme = "auto",
      disabled_filetypes = {
        statusline = {
          "alpha",
        },
      },
      always_divide_middle = true,
      globalstatus = true,
      section_separators = { left = "", right = "" },
      component_separators = { left = "", right = "│" },
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
  config = function(_, opts)
    require("lualine").setup(opts)
    vim.o.laststatus = 0
  end,
}
