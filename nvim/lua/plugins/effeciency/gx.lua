---@type LazyPluginSpec
return {
  "chrishrb/gx.nvim",
  submodules = false,
  keys = { { "gx", vim.cmd.Browse, mode = { "n", "x" } } },
  cmd = { "Browse" },
  opts = {
    open_callback = function(url)
      vim.fn.setreg("+", url) -- for example, you can set the url to clipboard here
    end,

    handlers = {
      jira = {
        name = "jira",
        handle = function(mode, line, _)
          local ticket = require("gx.helper").find(line, mode, "(%u+-%d+)")
          if ticket and #ticket < 20 then
            return "http://jira.company.com/browse/" .. ticket
          end
        end,
      },
      rust = {
        name = "rust",
        filename = "Cargo.toml",
        handle = function(mode, line, _)
          local crate = require("gx.helper").find(line, mode, "(%w+)%s-=%s")

          if crate then
            return "https://crates.io/crates/" .. crate
          end
        end,
      },
    },
  },
}
