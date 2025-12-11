---@type LazyPluginSpec
return {
  "DrKJeff16/project.nvim",
  cmd = { -- Lazy-load by commands
    "Project",
    "ProjectAdd",
    "ProjectConfig",
    "ProjectDelete",
    "ProjectHistory",
    "ProjectRecents",
    "ProjectRoot",
    "ProjectSession",
  },
  dependencies = { -- OPTIONAL
    "nvim-lua/plenary.nvim",
    "ibhagwan/fzf-lua",
  },
  opts = {},
}
