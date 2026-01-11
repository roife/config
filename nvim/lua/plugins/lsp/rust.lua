---@type LazyPluginSpec
return {
  "mrcjkb/rustaceanvim",
  version = "^6",
  lazy = false,
  opts = {
    server = {
      cmd = { "/Users/roife/.cargo/bin/rust-analyzer" },
      default_settings = {
        ["rust-analyzer"] = {
          cargo = {
            allFeatures = true,
            allTargets = true,
            features = "full",
          },
          checkOnSave = false,
          completion = {
            termSearch = {
              enable = true,
            },
            fullFunctionSignatures = {
              enable = true,
            },
          },
          hover = {
            memoryLayout = {
              size = "both",
            },
            show = {
              traitAssocItems = 5,
            },
            documentation = {
              keywords = {
                -- :enable :json-false
                enable = false,
              },
            },
          },
          inlayHints = {
            lifetimeElisionHints = {
              enable = "skip_trivial",
              useParameterNames = true,
            },
            closureReturnTypeHints = {
              enable = "always",
            },
            discriminantHints = {
              enable = true,
            },
            genericParameterHints = {
              lifetime = {
                enable = true,
              },
            },
          },
          semanticHighlighting = {
            operator = {
              specialization = {
                enable = true,
              },
            },
            punctuation = {
              enable = true,
              specialization = {
                enable = true,
              },
            },
          },
          workspace = {
            symbol = {
              search = {
                kind = "all_symbols",
                scope = "workspace_and_dependencies",
              },
            },
          },
          lru = {
            capacity = 1024,
          },
          diagnostics = {
            enable = true,
          },
        },
      },
    },
  },
  config = function(_, opts)
    ---@module "rustaceanvim"
    vim.g.rustaceanvim = opts
  end,
}
