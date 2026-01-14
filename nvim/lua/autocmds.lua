-- Restore last cursor position
vim.api.nvim_create_autocmd("BufRead", {
  desc = "Restore last cursor position",
  callback = function(args)
    local bufnr = args.buf
    local line, col = unpack(vim.api.nvim_buf_get_mark(bufnr, '"'))
    local winid = vim.api.nvim_get_current_win()

    local end_line = vim.api.nvim_buf_line_count(bufnr)
    local end_col = #vim.api.nvim_buf_get_lines(bufnr, end_line - 1, end_line, true)[1]

    if line < end_line or (line == end_line and col <= end_col) then
      vim.api.nvim_win_set_cursor(winid, { line, col })
    end
  end,
})

-- Reload buffer
vim.api.nvim_create_autocmd({
  "FocusGained",
  "BufEnter",
  "CursorHold",
}, {
  desc = "Reload buffer on focus",
  callback = function()
    if vim.fn.getcmdwintype() == "" then vim.cmd("checktime") end
  end,
})

-- Quickfix
vim.api.nvim_create_autocmd("FileType", {
  pattern = "qf",
  desc = "Disallow change buf for quickfix",
  callback = function() vim.wo.winfixbuf = true end,
})

-- Treesitter
vim.api.nvim_create_autocmd("FileType", {
  desc = "Enable treesitter features for supported filetypes",
  callback = function(args)
    local bufnr = args.buf
    local filetype = args.match
    local lang = vim.treesitter.language.get_lang(filetype)
    if lang and vim.treesitter.language.add(lang) then
      -- Highlighting
      vim.treesitter.start(bufnr, lang)
      -- Folds
      vim.wo[0][0].foldmethod = "expr"
      vim.wo[0][0].foldexpr = "v:lua.vim.treesitter.foldexpr()"
      -- Indentation
      vim.bo.indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
    end
  end,
})
