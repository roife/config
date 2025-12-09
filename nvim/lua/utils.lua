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

function M.center_cursor()
  local win = 0
  local view = vim.fn.winsaveview()

  local height = vim.api.nvim_win_get_height(win)
  view.topline = math.max(1, view.lnum - math.floor(height / 2))
  vim.fn.winrestview(view)
end

return M
