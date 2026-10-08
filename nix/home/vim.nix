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

      let mapleader = " "

      " Display and navigation.
      set cursorline
      set linebreak breakindent
      set showmatch matchtime=2
      set list listchars=tab:»·,trail:·,extends:›,precedes:‹,nbsp:␣
      set scrolloff=5 sidescrolloff=5
      set splitbelow splitright
      " Click to focus, drag to select/resize, and use the wheel to scroll.
      set mouse=a mousemodel=extend
      set laststatus=2 ruler
      let &statusline = '%f %h%m%r%=%y %{&fileencoding ==# "" ? &encoding : &fileencoding}[%{&fileformat}] %l:%c %P'

      " Editing, search and completion.
      set autoindent
      set expandtab tabstop=4 shiftwidth=4 softtabstop=4
      set incsearch hlsearch ignorecase smartcase
      set hidden
      set backspace=indent,eol,start
      set history=1000
      set completeopt=menuone,noselect
      set wildmenu
      set wildmode=longest:full,full wildignorecase
      set wildignore+=*/.git/*,*/node_modules/*,*/target/*,*/.venv/*,*.pyc,*.o,*.swp
      set diffopt+=vertical
      " The macOS system Vim does not include the internal diff engine.
      if &diffopt =~# '\<internal\>'
        set diffopt+=algorithm:histogram diffopt+=indent-heuristic
      endif

      " Use ripgrep for :grep and populate Vim's quickfix list.
      if executable('rg')
        set grepprg=rg\ --vimgrep\ --smart-case\ --
        set grepformat=%f:%l:%c:%m
      endif

      " Keep recovery files out of project directories.
      call mkdir(expand('~/.vim/backup'), 'p', 0700)
      call mkdir(expand('~/.vim/swap'), 'p', 0700)
      call mkdir(expand('~/.vim/undo'), 'p', 0700)
      set backup backupdir=~/.vim/backup//
      set directory=~/.vim/swap//
      set undofile undodir=~/.vim/undo//
      set autoread

      augroup user_vim
        autocmd!
        " Use two spaces where that is the usual project convention.
        autocmd FileType nix,lua,javascript,javascriptreact,typescript,typescriptreact,json,html,css,scss,yaml,ruby
              \ setlocal expandtab tabstop=2 shiftwidth=2 softtabstop=2
        autocmd FileType make setlocal noexpandtab tabstop=8 shiftwidth=8 softtabstop=0

        " Restore the last cursor position, except in Git commit/rebase buffers.
        autocmd BufReadPost *
              \ if &filetype !~# 'commit\|rebase' && line("'\"") > 1 && line("'\"") <= line('$') |
              \   execute "normal! g`\"" |
              \ endif

        " Reload externally changed files when there are no unsaved edits.
        autocmd FocusGained,BufEnter *
              \ if mode() !=# 'c' && getcmdwintype() ==# "" | checktime | endif
      augroup END

      " Move through wrapped lines; counts still move by actual lines.
      nnoremap <expr> j v:count ? 'j' : 'gj'
      nnoremap <expr> k v:count ? 'k' : 'gk'
      nnoremap <silent> <Esc><Esc> :nohlsearch<CR>
      nnoremap <silent> <leader>/ :nohlsearch<CR>
      nnoremap n nzzzv
      nnoremap N Nzzzv

      " Keep the selection when changing indentation.
      xnoremap < <gv
      xnoremap > >gv

      " Save, browse buffers, and move between splits.
      nnoremap <silent> <leader>w :update<CR>
      nnoremap <silent> [b :bprevious<CR>
      nnoremap <silent> ]b :bnext<CR>
      nnoremap <leader>b :ls<CR>:buffer<Space>
      nnoremap <C-h> <C-w>h
      nnoremap <C-j> <C-w>j
      nnoremap <C-k> <C-w>k
      nnoremap <C-l> <C-w>l

      " Browse search/compiler results and per-window location lists.
      nnoremap <silent> [q :cprevious<CR>
      nnoremap <silent> ]q :cnext<CR>
      nnoremap <silent> [l :lprevious<CR>
      nnoremap <silent> ]l :lnext<CR>
      nnoremap <silent> <leader>qo :copen<CR>
      nnoremap <silent> <leader>qc :cclose<CR>

      " Optional display aids; keep line numbers off by default.
      nnoremap <silent> <leader>un :set number!<CR>
      nnoremap <silent> <leader>ul :set list!<CR>
      nnoremap <silent> <leader>us :set spell!<CR>
      " Toggle mouse capture when terminal-native selection is needed.
      nnoremap <silent> <leader>um :let &mouse = &mouse ==# "" ? "a" : ""<CR>

      " Explicit system clipboard access when supported by this Vim build.
      if has('clipboard')
        nnoremap <leader>y "+y
        xnoremap <leader>y "+y
        nnoremap <leader>Y "+yy
        nnoremap <leader>p "+p
        nnoremap <leader>P "+P
      endif
    '';
  };
}
