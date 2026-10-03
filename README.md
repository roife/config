# 初始化

- macOS 需要 Command Line Tools、App Store 登录；
- Linux 需要 systemd 用户会话。

macOS 和 Linux 均使用 Nix 多用户 daemon 安装；初始化脚本会通过 `--daemon` 安装。已有单用户安装需先迁移。

私钥副本放到 `~/private-key.asc`（验证后删除）；智能卡运行 `gpg --card-status`。

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
