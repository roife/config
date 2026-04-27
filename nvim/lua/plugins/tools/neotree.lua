local function sort_key(item)
  if item.type == "directory" then return 1, item.name end
  if item.type == "file" and item.name:sub(-3) == ".rs" then return 0, item.name:sub(1, -4) end
  return 2, item.name
end

local function filesystem_sort(a, b)
  local a_kind, a_group = sort_key(a)
  local b_kind, b_group = sort_key(b)

  if a_kind == 2 or b_kind == 2 then
    if a_kind ~= b_kind then return a_kind < b_kind end
    return a.path < b.path
  end

  if a_group ~= b_group then return a_group < b_group end
  if a_kind ~= b_kind then return a_kind < b_kind end
  return a.path < b.path
end

---@type LazyPluginSpec
return {
  "nvim-neo-tree/neo-tree.nvim",
  branch = "main",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "MunifTanjim/nui.nvim",
  },
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
        padding = 0,
        expander_collapsed = "-",
        expander_expanded = "+",
        last_indent_marker = "│",
      },
      container = {
        right_padding = 0,
      },
      icon = {
        folder_closed = "+",
        folder_open = "-",
        folder_empty = "-",
        default = " ",
        provider = nil,
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
    sort_function = filesystem_sort,
    document_symbols = {
      kinds = {
        Unknown = { name = "Unk" },
        Root = { name = "Root" },
        File = { name = "File" },
        Module = { name = "Mod" },
        Namespace = { name = "Ns" },
        Package = { name = "Pack" },
        Class = { name = "Cls" },
        Method = { name = "Mtd" },
        Property = { name = "Prop" },
        Field = { name = "Fld" },
        Constructor = { name = "Ctor" },
        Enum = { name = "Enum" },
        Interface = { name = "Intf" },
        Function = { name = "Fn" },
        Variable = { name = "Var" },
        Constant = { name = "Cnst" },
        String = { name = "Str" },
        Number = { name = "Num" },
        Boolean = { name = "Bool" },
        Array = { name = "Arr" },
        Object = { name = "Obj" },
        Key = { name = "Key" },
        Null = { name = "Nul" },
        EnumMember = { name = "EnMem" },
        Struct = { name = "Strct" },
        Event = { name = "Evt" },
        Operator = { name = "Op" },
        TypeParameter = { name = "TyPar" },
      },
      renderers = {
        root = {
          { "indent" },
          { "name", zindex = 10 },
        },
        symbol = {
          { "indent", with_expanders = true },
          {
            "container",
            content = {
              { "name", zindex = 10 },
              { "kind_name", zindex = 20, align = "right" },
            },
          },
        },
      },
    },
    renderers = {
      file = {
        { "indent" },
        {
          "container",
          content = {
            { "name", zindex = 10 },
            { "symlink_target", zindex = 10, highlight = "NeoTreeSymbolicLinkTarget" },
            { "clipboard", zindex = 10 },
            { "bufnr", zindex = 10 },
            { "modified", zindex = 20, align = "right" },
            { "diagnostics", zindex = 20, align = "right" },
            { "git_status", zindex = 10, align = "right" },
            { "file_size", zindex = 10, align = "right" },
            { "type", zindex = 10, align = "right" },
            { "last_modified", zindex = 10, align = "right" },
            { "created", zindex = 10, align = "right" },
          },
        },
      },
      terminal = {
        { "indent" },
        { "name" },
        { "bufnr" },
      },
    },
    source_selector = {
      winbar = true,
      statusline = true,
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

        ["gd"] = "codediff_head",
        ["gD"] = "codediff_pr",
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

      codediff_head = function(state)
        local node = state.tree:get_node()
        if not node or node.type ~= "file" then return end

        state.commands.open(state)
        vim.schedule(function() vim.cmd("CodeDiff file HEAD") end)
      end,

      codediff_pr = function(state)
        local node = state.tree:get_node()
        if not node or node.type ~= "file" then return end

        state.commands.open(state)
        vim.schedule(function() vim.cmd("CodeDiff file main...") end)
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
  end,
  keys = {
    { "<leader>e", "<cmd>Neotree toggle<cr>", desc = "File Explorer" },
  },
}
