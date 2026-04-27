---@type LazyPluginSpec
return {
  "folke/sidekick.nvim",
  opts = {
    nes = {
      clear = {
        events = { "InsertEnter" },
        esc = true,
      },
    },
    cli = {
      picker = "fzf-lua",
      ---@type table<string, sidekick.context.Fn>
      context = {
        git_history = function()
          local cmd = { "git", "log", "--pretty=format:%s", "-n", "5" }
          local history = vim.fn.systemlist(cmd)
          return history
        end,
        git_diff = function()
          local cmd = { "git", "diff", "--cached", "-w" }
          local diff = vim.fn.systemlist(cmd)
          return diff
        end,
      },
      prompts = {
        commit = [[# Analyze CHANGES to understand and identify *why*:
{git_diff}.
# Review recent commit conventions:
{git_history}.
# Generate a thoughtful and succinct commit message.
# Commit changes]],
        inline = [[#Analyze the usage of these functions and inline those that are used only once:
{this}.]],
      },
      win = {
        layout = "float",
      },
      tools = {
        codex = {
          cmd = {
            "codex",
            "--disable",
            "apps",
            "--disable",
            "plugins",
          },
        },
      },
    },
    ui = {
      icons = {
        nes = "✦",
      },
    },
  },
  keys = {
    {
      "<tab>",
      function()
        -- if there is a next edit, jump to it, otherwise apply it if any
        if not require("sidekick").nes_jump_or_apply() then
          return "<Tab>" -- fallback to normal tab
        end
      end,
      mode = { "n" },
      expr = true,
      desc = "Goto/Apply Next Edit Suggestion",
    },
    {
      "<leader>aa",
      function() require("sidekick.cli").toggle { name = "codex", focus = true } end,
      desc = "Sidekick Toggle CLI",
    },
    {
      "<C-S-\\>",
      function() require("sidekick.cli").toggle { name = "codex", focus = true } end,
      mode = { "n", "t" },
      desc = "Sidekick Toggle CLI",
    },
    {
      "<leader>ad",
      function() require("sidekick.cli").close() end,
      desc = "Detach a CLI Session",
    },
    {
      "<leader>as",
      function() require("sidekick.cli").send { msg = "{this}" } end,
      mode = { "x", "n" },
      desc = "Send This",
    },
    {
      "<leader>af",
      function() require("sidekick.cli").send { msg = "{file}" } end,
      desc = "Send File",
    },
    {
      "<leader>av",
      function() require("sidekick.cli").send { msg = "{selection}" } end,
      mode = { "x" },
      desc = "Send Visual Selection",
    },
    {
      "<leader>ap",
      function() require("sidekick.cli").prompt() end,
      mode = { "n", "x" },
      desc = "Sidekick Select Prompt",
    },
  },
}
