# 初始化

- macOS 需要 Command Line Tools、App Store 登录；
- Linux 需要 systemd 用户会话。

安装模式由 Nix 安装器自行选择。已有 daemon 或单用户安装均可复用，初始化脚本和 Fish 会加载对应的 profile，不修改 SELinux 设置。

私钥副本放到 `~/secret-keys.asc`（验证后删除）；智能卡运行 `gpg --card-status`。

```sh
bash -c '
set -euo pipefail
config_dir="$HOME/.config"
if [[ ! -e "$config_dir/.git" ]]; then
    checkout="$(mktemp -d)"
    git clone https://github.com/roife/config.git "$checkout"
    mkdir -p "$config_dir"
    cp -af "$checkout/." "$config_dir/"
    rm -rf -- "$checkout"
fi
git -C "$config_dir" remote set-url origin git@github.com:roife/config.git
exec bash "$config_dir/init.sh"
'
```

重跑：`bash ~/.config/init.sh`。

`--username alice` 指定 Home Manager 用户名及家目录（默认当前用户）。

`--no-gui`（仅 Linux）跳过桌面应用、KDE 和 Rime，并使用终端版 Emacs。

直接用 Nix 构建时，通过 `HOME_MANAGER_USERNAME` 指定用户名（需 `--impure`，默认 `roifewu`）。

可选 `GITHUB_TOKEN` 环境变量会自动用于 Nix 构建。
