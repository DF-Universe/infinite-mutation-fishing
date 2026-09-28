# 无限融合变异捕鱼

几乎完全通过 QQ 群指令游玩的捕鱼小游戏。公共鱼群、金币和经验沿用捕鱼的思路；鱼种由群友贡献推动原创变异，逐代形成族谱。

完整讨论整理见 [游戏设计文档](docs/game-design.md)。文档中的已定规则和待定数值分开记录。

## 当前状态

仅完成设计文档、本地独立 Git 仓库和宿主加载骨架，未实现捕鱼、变异生成、抽奖、装备或存档逻辑。暂不配置远程地址；本地仓库不等于已配置可递归克隆的 Git submodule，后续确定远程后再补 `.gitmodules`。

## 宿主接入

- 目录：`src/infinite-mutation-fishing`，包：`infinite_mutation_fishing`。
- 主仓 `src/quart.py` 将子仓 `src/` 加入包搜索路径并安装 Web Blueprint。
- 主仓 `bot.py` 加载 `infinite_mutation_fishing.qq.mutation_fishing`。入口末段保持唯一，避免与红叶镇的 `plugin` 注册名冲突。
- 健康检查：`GET http://localhost:8000/web/api/infinite-mutation-fishing/health`，`stage: scaffold` 表示只有初始化骨架。
- QQ 插件名：`无限融合变异捕鱼`，沿用宿主插件管理，默认关闭；在目标群启用后发送 `变异捕鱼` 或 `无限融合变异捕鱼`，返回初始化说明。
- 使用适配器无关的命令回复；群身份兼容宿主当前 Milky、QQ 官方群事件及 OneBot 的 `group_id`。私聊不触发游戏命令。
- 当前不提供 Web 玩家页面，因此无需前端构建。

## 测试

在主仓目录运行：

```sh
venv/bin/python -m pytest src/infinite-mutation-fishing/tests
```

也可在子仓内使用宿主虚拟环境运行：

```sh
../../venv/bin/python -m pytest
```

QQ 插件依赖宿主已有的 NoneBot、适配器和插件管理器；独立测试 Web 骨架无需启动机器人或连接 Redis。
