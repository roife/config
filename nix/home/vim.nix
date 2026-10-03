{ lib, pkgs, ... }:
{
  programs.vim = {
    enable = true;
    packageConfigurable = pkgs.vim;
    # Home Manager otherwise adds vim-sensible even when plugins = [ ].
    plugins = lib.mkForce [ ];

    extraConfig = ''
      set nocompatible
      syntax enable
      filetype plugin indent on

      set number
      set autoindent
      set expandtab tabstop=4 shiftwidth=4 softtabstop=4
      set incsearch hlsearch ignorecase smartcase
      set hidden
      set backspace=indent,eol,start
      set wildmenu
      set laststatus=2 ruler
      set scrolloff=3
      set splitbelow splitright

      " Keep undo history between sessions.
      call mkdir(expand('~/.vim/undo'), 'p', 0700)
      set undofile undodir=~/.vim/undo//

      nnoremap <silent> <Esc><Esc> :nohlsearch<CR>
    '';
  };
}
