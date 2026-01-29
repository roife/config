local function split_and_shorten(path, maxlen)
  local sep = package.config:sub(1, 1)
  local parts = vim.split(path, sep, { plain = true })

  if #parts == 0 then
    return "", ""
  end

  local tail = parts[#parts]
  table.remove(parts, #parts)

  if #parts == 0 then
    return "", tail
  end

  local len = #path
  if len <= maxlen then
    return path:sub(1, #path - #tail - 1), tail
  end

  if parts[1] ~= ".." then
    len = len - (#parts[1] - 1)
    parts[1] = parts[1]:sub(1, 1)
  end

  for i = 2, #parts do
    if len <= maxlen then
      break
    end

    if #parts[i] > 1 then
      len = len - (#parts[i] - 1)
      parts[i] = parts[i]:sub(1, 1)
    end
  end

  local head = table.concat(parts, sep)
  return head, tail
end

---@type LazyPluginSpec
return {
  'b0o/incline.nvim',
  opts = {
    hide = {
      focused_win = true,
      only_win = true,
    },
    window = {
      margin = {
        horizontal = 0,
        vertical = 0,
      },
    },
    render = function(props)
      local buf = props.buf
      local name = vim.api.nvim_buf_get_name(buf)
      local buftype = vim.bo[buf].buftype

      local path = ""
      local filename = ""
      if buftype ~= "" or name == "" then
        filename = vim.fn.expand('%')
      else
        path = vim.fn.fnamemodify(name, ":~:.")
        path, filename = split_and_shorten(path, 20)
      end

      local sep = path ~= "" and package.config:sub(1, 1) or ""
      local modified = vim.bo[props.buf].modified
      local line = vim.api.nvim_win_get_cursor(props.win)[1]
      return {
        path,
        sep,
        { filename, gui = modified and 'bold,italic' or 'bold' },
        ":",
        line,
      }
    end
  },
}
