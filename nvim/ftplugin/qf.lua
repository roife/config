local bufnr = vim.api.nvim_get_current_buf()
local winid = vim.api.nvim_get_current_win()

-- Avoid opening other buffers in the quickfix window.
vim.wo[winid][0].winfixbuf = true

vim.keymap.set('n', 'q', '<Cmd>close<CR>', { desc = 'Close Quickfix', buffer = bufnr })
