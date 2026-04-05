-- [[ Install `lazy.nvim` plugin manager ]]
--    See `:help lazy.nvim.txt` or https://github.com/folke/lazy.nvim for more info
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  local lazyrepo = "https://github.com/folke/lazy.nvim.git"
  local out =
    vim.fn.system { "git", "clone", "--filter=blob:none", "--branch=stable", lazyrepo, lazypath }
  if vim.v.shell_error ~= 0 then error("Error cloning lazy.nvim:\n" .. out) end
end

vim.opt.rtp:prepend(lazypath)

require("lazy").setup {
  spec = { { import = "plugins" } },
  install = {
    colorscheme = { "gruvbox-material" },
  },
  diff = {
    cmd = "diffview.nvim",
  },
  change_detection = {
    -- automatically check for config file changes and reload the ui
    enabled = false,
    notify = false, -- get a notification when changes are found
  },
  ui = {
    icons = {
      cmd = "",
      config = "",
      debug = "",
      event = "",
      favorite = "",
      ft = "",
      init = "",
      import = "",
      keys = "",
      lazy = "~",
      loaded = "●",
      not_loaded = "○",
      plugin = "",
      runtime = "",
      require = "",
      source = "",
      start = "▶",
      task = "✔",
      list = {
        "-",
        "+",
        "*",
      },
    },
  },
  performance = {
    rtp = {
      disabled_plugins = {
        "gzip",
        -- "matchit",
        "matchparen",
        "netrwPlugin",
        "tarPlugin",
        "tohtml",
        "tutor",
        "zipPlugin",
      },
    },
  },
}
