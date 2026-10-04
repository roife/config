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
    cp -a "$checkout/." "$config_dir/"
    rm -rf -- "$checkout"
fi
git -C "$config_dir" remote set-url origin git@github.com:roife/config.git
exec bash "$config_dir/init.sh"
'
```

重跑：`bash ~/.config/init.sh`。

可选 `GITHUB_TOKEN` 环境变量会自动用于 Nix 构建。
