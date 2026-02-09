---@type LazyPluginSpec
return {
  "nvim-neo-tree/neo-tree.nvim",
  branch = "main",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "MunifTanjim/nui.nvim",
  },
  init = function()
    vim.api.nvim_create_autocmd("BufEnter", {
      group = vim.api.nvim_create_augroup("load_neo_tree", {}),
      desc = "Loads neo-tree when openning a directory",
      callback = function(args)
        local stats = vim.uv.fs_stat(args.file)

        if not stats or stats.type ~= "directory" then return end

        require("neo-tree")

        return true
      end,
    })
  end,
  opts = {
    default_source = "last",
    enable_cursor_hijack = true,
    sources = { "filesystem", "buffers", "git_status", "document_symbols" },
    event_handlers = {
      {
        event = "neo_tree_popup_input_ready",
        handler = function(args)
          vim.keymap.set("i", "<Esc>", vim.cmd.stopinsert, { noremap = true, buffer = args.bufnr })
        end,
      },
    },
    default_component_configs = {
      modified = { symbol = "*" },
      indent = {
        expander_collapsed = "+",
        expander_expanded = "-",
      },
      icon = {
        folder_closed = "+",
        folder_open = "-",
        folder_empty = "-",
        default = " ",
      },
      git_status = {
        symbols = {
          added = "+",
          modified = "*",
          deleted = "x",
          renamed = "↺",
          unstaged = "*",
          staged = "✔",
          untracked = "?",
          ignored = "-",
          conflict = "!",
        },
      },
      symlink_target = {
        enabled = true,
      },
    },
    document_symbols = {
      kinds = {
        Unknown = { icon = "?" },
        Root = { icon = "Rt" },
        File = { icon = "Fl" },
        Module = { icon = "Md" },
        Namespace = { icon = "Ns" },
        Package = { icon = "Pk" },
        Class = { icon = "Cl" },
        Method = { icon = "Mt" },
        Property = { icon = "Pr" },
        Field = { icon = "Fd" },
        Constructor = { icon = "Cr" },
        Enum = { icon = "En" },
        Interface = { icon = "If" },
        Function = { icon = "Fn" },
        Variable = { icon = "Vr" },
        Constant = { icon = "Cn" },
        String = { icon = "St" },
        Number = { icon = "Nr" },
        Boolean = { icon = "Bl" },
        Array = { icon = "Ar" },
        Object = { icon = "Ob" },
        Key = { icon = "Ke" },
        Null = { icon = "Nu" },
        EnumMember = { icon = "Em" },
        Struct = { icon = "St" },
        Event = { icon = "Ev" },
        Operator = { icon = "Op" },
        TypeParameter = { icon = "Tp" },
      },
      renderers = {
        root = {
          { "indent" },
          { "icon", default = "C" },
          { "name", zindex = 10 },
        },
        symbol = {
          { "indent", with_expanders = true },
          { "kind_icon", default = "?" },
          { "name", zindex = 10 },
        },
      },
    },
    source_selector = {
      winbar = true,
      sources = {
        {
          source = "filesystem",
          display_name = "Files",
        },
        {
          source = "git_status",
          display_name = "Git",
        },
        {
          source = "document_symbols",
          display_name = "Syms",
        },
        {
          source = "buffers",
          display_name = "Bufs",
        },
      },
    },
    window = {
      mappings = {
        ["<Space>"] = "none",
        ["/"] = "none",

        ["gx"] = "system_open",

        ["h"] = "smart_h",
        ["l"] = "smart_l",

        -- Swap default split behavior
        ["S"] = "open_vsplit",
        ["s"] = "open_split",

        -- Modify default behavior of preview.
        -- Using floating window causes strange behavior,
        -- such as statuscolumn not being applied
        ["P"] = {
          "toggle_preview",
          config = {
            use_float = false,
            use_image_nvim = true,
          },
        },
      },
    },
    commands = {
      system_open = function(state)
        local node = state.tree:get_node()
        local path = node:get_id()
        vim.ui.open(path)
      end,

      smart_h = function(state)
        local node = state.tree:get_node()
        if node.type == "directory" and node:is_expanded() then
          if state.name == "filesystem" then
            require("neo-tree.sources.filesystem.commands").toggle_node(state)
          else
            require("neo-tree.sources.common.commands").toggle_node(state)
          end
        else
          require("neo-tree.ui.renderer").focus_node(state, node:get_parent_id())
        end
      end,

      smart_l = function(state)
        local node = state.tree:get_node()
        if node.type == "directory" then
          if not node:is_expanded() then
            if state.name == "filesystem" then
              require("neo-tree.sources.filesystem.commands").toggle_node(state)
            else
              require("neo-tree.sources.common.commands").toggle_node(state)
            end
          elseif node:has_children() then
            require("neo-tree.ui.renderer").focus_node(state, node:get_child_ids()[1])
          end
        elseif node.type == "file" then
          require("neo-tree.sources.common.commands").open(state)
        end
      end,
    },
    filesystem = {
      hijack_netrw_behavior = "disabled",
      group_empty_dirs = true,
      follow_current_file = {
        enabled = true,
      },
    },
  },
  config = function(_, opts)
    local function on_move(data)
      require("snacks").rename.on_rename_file(data.source, data.destination)
    end
    local events = require("neo-tree.events")
    opts.event_handlers = opts.event_handlers or {}
    vim.list_extend(opts.event_handlers, {
      { event = events.FILE_MOVED, handler = on_move },
      { event = events.FILE_RENAMED, handler = on_move },
    })
    require("neo-tree").setup(opts)
    vim.api.nvim_create_augroup("load_neo_tree", {})
  end,
  keys = {
    { "<leader>e", "<cmd>Neotree toggle<cr>", desc = "File Explorer" },
  },
}
