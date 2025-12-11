---@type LazyPluginSpec
return {
  'b0o/incline.nvim',
  event = 'VeryLazy',
  opts = {
    window = {
      margin = {
        horizontal = 0,
      },
    },
    render = function(props)
      local filename = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(props.buf), ':t')
      if filename == '' then
        filename = '[No Name]'
      end
      local modified = vim.bo[props.buf].modified
      return {
        { filename, gui = modified and 'bold,italic' or 'bold' },
      }
    end,
  },
  config = function(_, opts)
    require('incline').setup(opts)
  end,
}
