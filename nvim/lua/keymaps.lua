local utils = require("utils")

-- Set <space> as the leader key
vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

-- Clear highlights on search when pressing <Esc> in normal mode
vim.keymap.set("n", "<Esc>", vim.cmd.nohlsearch, { desc = "Clear search results" })

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

-- Tabs (based on Meta key)
for i = 1, 9 do
  local key = "<M-" .. i .. ">"
  local desc = "Go to tab " .. i
  vim.keymap.set("n", key, function() vim.cmd.tabn(i) end, { desc = desc })
end
vim.keymap.set(
  "n",
  "<M-S-Tab>",
  function() vim.cmd.tabprevious() end,
  { desc = "Go to previous tab" }
)
vim.keymap.set("n", "<M-Tab>", function() vim.cmd.tabnext() end, { desc = "Go to next tab" })
vim.keymap.set("n", "<M-t>", function() vim.cmd.tabnew() end, { desc = "Open new tab" })
vim.keymap.set("n", "<M-w>", function() vim.cmd.tabclose() end, { desc = "Close current tab" })

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

-- diff
local function toggle_diff_ignore_whitespace()
  local diffopt = vim.opt.diffopt
  local target = "iwhiteall"
  local exists = false

  for _, v in ipairs(diffopt:get()) do
    if v == target then
      exists = true
      break
    end
  end

  if exists then
    diffopt:remove(target)
    vim.notify("Ignore whitespaces in diff", vim.log.levels.INFO)
  else
    diffopt:append(target)
    vim.notify("Do not ignore whitespaces in diff", vim.log.levels.INFO)
  end

  vim.cmd("diffupdate")
end

vim.keymap.set("n", "<leader>gdw", toggle_diff_ignore_whitespace, {
  desc = "Toggle ignore whitespace in diff",
})

-- Undo tree
vim.keymap.set('n', '<leader>u', '<Cmd>Undotree<CR>', { desc = 'Undo Tree' })
