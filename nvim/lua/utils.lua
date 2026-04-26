local M = {}

--- Wrapper for tree-sitter repeatable move,
---@param forward_move_fn function
---@param backward_move_fn function
function M.make_repeatable_move_pair(forward_move_fn, backward_move_fn)
  local function move_fn(opts) return (opts.forward and forward_move_fn or backward_move_fn)() end

  local checked = false
  local function ensure_repeatable()
    if checked then return end
    checked = true
    local ok, ts_repeatable = pcall(require, "nvim-treesitter-textobjects.repeatable_move")
    if ok then move_fn = ts_repeatable.make_repeatable_move(move_fn) end
  end

  return function()
    ensure_repeatable()
    return move_fn { forward = true }
  end, function()
    ensure_repeatable()
    return move_fn { forward = false }
  end
end

function M.noop() end

function M.empty_str(...) return "" end

function M.set_tabname(name)
  if not name or name == "" or (vim.t.tabname and vim.t.tabname ~= "") then return end
  vim.t.tabname = name
end

---shortens path by turning apple/orange -> a/orange
---@param path string
---@param sep string path separator
---@param max_len integer maximum length of the full filename string
---@return string
function M.shorten_path(path, sep, max_len)
  local len = #path
  if len <= max_len then return path end

  local segments = vim.split(path, sep)
  for idx = 1, #segments - 1 do
    if len <= max_len then break end

    local segment = segments[idx]
    local shortened = segment:sub(1, vim.startswith(segment, ".") and 2 or 1)
    segments[idx] = shortened
    len = len - (#segment - #shortened)
  end

  return table.concat(segments, sep)
end

--- Adjusts the brightness of a color represented as an integer (0xRRGGBB).
--- @param color_int integer The color as an integer (0xRRGGBB).
--- @param amount integer The amount to adjust the brightness (positive to brighten, negative to darken).
--- @return integer The adjusted color as an integer (0xRRGGBB).
function M.adjust_brightness(color_int, amount)
  local r = math.floor(color_int / 0x10000)
  local g = math.floor((color_int % 0x10000) / 0x100)
  local b = color_int % 0x100

  r = math.min(255, math.max(0, r + amount))
  g = math.min(255, math.max(0, g + amount))
  b = math.min(255, math.max(0, b + amount))

  return (r * 0x10000) + (g * 0x100) + b
end

return M
