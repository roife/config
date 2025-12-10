return {
  "sundbp/strict-paredit.nvim", -- or local path, see below
  dependencies = {
    "nvim-treesitter/nvim-treesitter",
  },
  ft = { "clojure", "fennel", "scheme", "lisp", "racket", "janet", "hy", "query", "rust", "lua" },
  opts = {
    -- your options here (see Configuration below)
  },
}
