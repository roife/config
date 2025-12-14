local utils = require("utils")

-- Set <space> as the leader key
vim.g.mapleader = " "
vim.g.maplocalleader = "  "

-- Clear highlights on search when pressing <Esc> in normal mode
vim.keymap.set("n", "<Esc>", vim.cmd.nohlsearch, { desc = "Clear search results" })

-- Exit terminal mode in the builtin terminal with a shortcut
vim.keymap.set("t", "jj", vim.cmd.stopinsert, { desc = "Exit terminal mode" })
vim.keymap.set("i", "jj", "<Esc>", { noremap = true, silent = true })

--  Use CTRL+<hjkl> to switch between windows
vim.keymap.set("n", "<C-h>", function() vim.cmd.wincmd("h") end, { desc = "Move focus to left" })

vim.keymap.set("n", "<C-l>", function() vim.cmd.wincmd("l") end, { desc = "Move focus to right" })

vim.keymap.set("n", "<C-j>", function() vim.cmd.wincmd("j") end, { desc = "Move focus to lower" })

vim.keymap.set("n", "<C-k>", function() vim.cmd.wincmd("k") end, { desc = "Move focus to upper" })

-- Swap the behavior for moving by physical lines and display lines
vim.keymap.set({ "n", "x", "o" }, "j", "gj")
vim.keymap.set({ "n", "x", "o" }, "k", "gk")
vim.keymap.set({ "n", "x", "o" }, "gj", "j")
vim.keymap.set({ "n", "x", "o" }, "gk", "k")

-- Simulating Emacs keybindings
-- Cursor movement
vim.keymap.set({ "c" }, "<C-a>", "<Home>", { desc = "BOL" })
vim.keymap.set({ "i" }, "<C-a>", "<C-o>^", { desc = "BOL" })
vim.keymap.set({ "c", "i" }, "<C-e>", "<End>", { desc = "EOL" })
vim.keymap.set({ "n", "i" }, "<C-n>", "<Down>", { desc = "Next line" })
vim.keymap.set({ "n", "i" }, "<C-p>", "<Up>", { desc = "Prev line" })
vim.keymap.set("i", "<C-b>", "<Left>", { desc = "Back char" })
vim.keymap.set("i", "<C-f>", "<Right>", { desc = "Forward char" })
vim.keymap.set("i", "<M-b>", "<C-o>b", { desc = "Back word" })
vim.keymap.set("i", "<M-f>", "<C-o>w", { desc = "Forward word" })
-- Killing/yanking
vim.keymap.set("i", "<C-k>", "<C-o>D", { desc = "Kill to EOL" })
vim.keymap.set("i", "<C-y>", '<C-r>"', { desc = "Yank last kill" })
-- Normal mode
vim.keymap.set("n", "<C-a>", "^", { desc = "Bol" })
vim.keymap.set("n", "<C-e>", "$", { desc = "Eol" })

-- Disable righ-click popups
vim.keymap.set({ "n", "i", "v" }, "<RightMouse>", utils.noop)

-- Diagnostic keymaps
vim.keymap.set(
  "n",
  "<leader>q",
  vim.diagnostic.setloclist,
  { desc = "Open diagnostic [Q]uickfix list" }
)

-- Quickfix keymaps
local function toggle_quickfix()
  for _, win in ipairs(vim.fn.getwininfo()) do
    if win.quickfix == 1 then return vim.cmd.cclose() end
  end
  vim.cmd.copen()
end
vim.keymap.set("n", "<leader>q", toggle_quickfix, { desc = "Toggle Quickfix" })

vim.api.nvim_create_autocmd("FileType", {
  pattern = "qf",
  callback = function(args)
    local bufnr = args.buf
    vim.keymap.set("n", "q", vim.cmd.close, { buffer = bufnr })
  end,
})

-- Repeatable moves
local function set_repeatable_move(key, element_name, forward_fn, backward_fn)
  local forward, backward = utils.make_repeatable_move_pair(forward_fn, backward_fn)
  vim.keymap.set("n", "]" .. key, forward, { desc = "Next " .. element_name })
  vim.keymap.set("n", "[" .. key, backward, { desc = "Prev " .. element_name })
end

set_repeatable_move(
  "d",
  "diagnostic",
  function() vim.diagnostic.jump { count = vim.v.count1 } end,
  function() vim.diagnostic.jump { count = -vim.v.count1 } end
)

set_repeatable_move(
  "q",
  "quickfix",
  function() return pcall(vim.cmd.cnext, { count = vim.v.count1 }) end,
  function() return pcall(vim.cmd.cprevious, { count = vim.v.count1 }) end
)

set_repeatable_move(
  "b",
  "buffer",
  function() return pcall(vim.cmd.bnext, { count = vim.v.count1 }) end,
  function() return pcall(vim.cmd.bprevious, { count = vim.v.count1 }) end
)

-- Treesitter
vim.keymap.set("n", "<leader>hi", vim.show_pos, { desc = "Inspect" })
vim.keymap.set("n", "<leader>ht", vim.treesitter.inspect_tree, { desc = "Treesit Tree" })
vim.keymap.set("n", "<leader>hq", vim.treesitter.query.edit, { desc = "Treesit Query" })
