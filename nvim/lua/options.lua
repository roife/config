-- Hint: use `:h <option>` to figure out the meaning if needed

--  Schedule the setting after `UiEnter` because it can increase startup-time.
vim.schedule(function() vim.o.clipboard = "unnamedplus" end)

vim.opt.completeopt = { "menu", "menuone", "noselect" } -- always show the popup menu but don't insert any completion

vim.o.jumpoptions = "stack" -- keeps a full stack of jumps

vim.o.undofile = true

-- Tab
vim.o.tabstop = 4 -- number of visual spaces per TAB
vim.o.softtabstop = 4 -- number of spaces in tab when editing
vim.o.shiftwidth = 4 -- insert 4 spaces on a tab
vim.o.expandtab = true -- tabs are spaces
vim.o.breakindent = true -- Wrapped line will continue visually indented

-- Mouse
vim.o.mouse = "a" -- allow the mouse to be used in nvim
vim.o.mousemoveevent = true -- fire CursorMoved-style events on mouse move
vim.keymap.set({ "n", "i", "v" }, "<ScrollWheelLeft>", "<Nop>", { noremap = true, silent = true })
vim.keymap.set({ "n", "i", "v" }, "<ScrollWheelRight>", "<Nop>", { noremap = true, silent = true })

-- UI
-- vim.o.background = "light"
vim.o.cursorline = true -- highlight cursor line
vim.o.showtabline = 0 -- disable tabline
vim.o.signcolumn = "yes" -- Keep signcolumn on by default
vim.o.showmode = false -- remove "-- INSERT --" mode hint
vim.o.smoothscroll = true
vim.o.termguicolors = true
vim.o.title = true
vim.o.titlestring = "%t - Nvim"
vim.o.conceallevel = 2 -- hide most concealed text unless on the line (used by Markdown/LaTeX).
vim.opt.shortmess:append("I") -- don't show welcome message
vim.o.confirm = true -- prompt to save when closing modified buffers instead of failing.
vim.o.laststatus = 0 -- prompt to save when closing modified buffers instead of failing.
vim.opt.fillchars:append("diff:╱")
vim.opt.diffopt:append("iwhiteall")

-- Scrolling
vim.o.scrolloff = 5
vim.o.sidescrolloff = 5

-- Sets how neovim will display certain whitespace characters in the editor.
vim.o.list = true
vim.opt.listchars = { tab = "» ", trail = "·", nbsp = "␣" }

-- Splitting
vim.o.splitkeep = "screen" -- keep windows’ view stable when splitting/closing
vim.o.splitbelow = true -- open new vertical split bottom
vim.o.splitright = true -- open new horizontal splits right

-- Searching
vim.o.incsearch = true -- search as characters are entered
vim.o.ignorecase = true -- ignore case in searches by default
vim.o.smartcase = true -- but make it case sensitive if an uppercase is entered
vim.o.inccommand = "split" -- Preview substitutions live, as you type!

-- Performance
vim.o.updatetime = 750
vim.o.timeoutlen = 600

-- Folding
vim.o.foldcolumn = "0"
vim.o.foldlevel = 99
vim.o.foldlevelstart = 99
vim.o.foldenable = true

-- Line Numbers
--vim.opt.relativenumber = true
--vim.opt.numberwidth = 2
