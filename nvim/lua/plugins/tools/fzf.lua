---@type LazyPluginSpec
return {
  "ibhagwan/fzf-lua",
  init = function()
    ---@diagnostic disable-next-line: duplicate-set-field
    vim.ui.select = function(...)
      require("fzf-lua").register_ui_select()
      vim.ui.select(...)
    end
  end,
  cmd = { "FzfLua" },
  opts = {
    files = {
      formatter = "path.filename_first",
    },
    lsp = {
      symbols = {
        symbol_style = 3,
      },
    },
    unique_line_items = true,
  },
  keys = {
    {
      "<leader>ff",
      function() require("fzf-lua").files() end,
      desc = "Files",
    },
    {
      "<leader>fb",
      function() require("fzf-lua").buffers() end,
      desc = "Buffers",
    },
    {
      "<leader>fl",
      function() require("fzf-lua").lines() end,
      desc = "Buffers",
    },
    {
      "<leader>f?",
      function() require("fzf-lua").help_tags() end,
      desc = "Help tags",
    },
    {
      "<leader>fo",
      function() require("fzf-lua").oldfiles() end,
      desc = "Old files",
    },
    {
      "<leader>fm",
      function() require("fzf-lua").marks() end,
      desc = "Marks",
    },
    {
      "<leader>fls",
      function() require("fzf-lua").lsp_document_symbols() end,
      desc = "Document Symbols",
    },
    {
      "<leader>flS",
      function() require("fzf-lua").lsp_workspace_symbols() end,
      desc = "Workspace Symbols",
    },
    {
      "<leader>fc",
      function() require("fzf-lua").commands() end,
      desc = "Commands",
    },
    {
      "<leader>fj",
      function() require("fzf-lua").jumps() end,
      desc = "Jumplist",
    },
    {
      "<leader>fs",
      function() require("fzf-lua").live_grep_native() end,
      desc = "Search by live grep",
    },
    {
      "<leader>fr",
      function() require("fzf-lua").registers() end,
      desc = "Registers",
    },
    {
      "<leader>fR",
      function() require("fzf-lua").resume() end,
      desc = "Resume,",
    },
    {
      "<leader>fk",
      function() require("fzf-lua").keymaps() end,
      desc = "Keymaps",
    },

    -- git
    {
      "<leader>fgc",
      function() require("fzf-lua").git_commits() end,
      desc = "Commits",
    },
    {
      "<leader>fgb",
      function() require("fzf-lua").git_branches() end,
      desc = "Branchs",
    },
    {
      "<leader>fgt",
      function() require("fzf-lua").git_tags() end,
      desc = "Tags",
    },
    {
      "<leader>fgs",
      function() require("fzf-lua").git_status() end,
      desc = "Tags",
    },

    -- dap
    {
      "<leader>fde",
      function() require("fzf-lua").dap_commands() end,
      desc = "Commands",
    },
    {
      "<leader>fdc",
      function() require("fzf-lua").dap_configurations() end,
      desc = "Configurations",
    },
    {
      "<leader>fdb",
      function() require("fzf-lua").dap_breakpoints() end,
      desc = "Breakpoints",
    },
    {
      "<leader>fdv",
      function() require("fzf-lua").dap_variables() end,
      desc = "Variables",
    },
    {
      "<leader>fdf",
      function() require("fzf-lua").dap_frames() end,
      desc = "Frames",
    },
  },
}
