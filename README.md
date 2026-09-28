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

## 祖先鱼绘图预览

`data/ancestor-fish.json` 保存祖先鱼暂定名称和三个色值。`scripts/render-fish.mjs` 用固定 SVG 轮廓绘制简笔鱼，身体／斑纹／鳍尾分别读取三个颜色，不使用 AI 图片生成。描边、眼睛是固定中性色，不参与遗传。

```sh
node scripts/render-fish.mjs
```

输出透明背景的 `assets/ancestor/fish.svg` 和配色展示页 `assets/ancestor/preview.html`；`preview.png` 为展示页截图。也可传入配置路径和输出目录：`node scripts/render-fish.mjs <config.json> <output-dir>`。复用绘图函数时传入 `body`、`markings`、`fins` 三个 `#RRGGBB` 色值即可。

## 群友变异配色预览

在主仓目录运行，读取宿主现有 Milky 配置，不需要复制凭据：

```sh
venv/bin/python src/infinite-mutation-fishing/scripts/preview-mutation.py 112631066 --output src/infinite-mutation-fishing/previews/demo
node src/infinite-mutation-fishing/scripts/render-fish.mjs src/infinite-mutation-fishing/previews/demo/fish.json src/infinite-mutation-fishing/previews/demo
```

默认随机抽两位非当前机器人成员；`--users <QQ1> <QQ2>` 可复现选定贡献者的顺序，`--parent <fish.json>` 可改用其他亲代。群名片为空时回退昵称并标记来源。头像及身份快照只保存在已忽略的 `previews/`，不写游戏状态，不发消息。

`fish.json` 中的名称、描述供人工或后续文案服务填写；当前脚本只自动生成真实成员快照和配色，不声称已经接入自动 AI 命名。绘图函数支持名称、代数、贡献者标注与描述，动态文本经过 HTML 转义。

保留的工具：

- `qq/profiles.py`：`fetch_members`、`select_contributors`、`fetch_avatar`，只读读取与去重抽样。
- `palette.py`：`extract_avatar_color`，裁掉边缘 8%、忽略透明像素、量化 12 色，选有足够面积的代表色；这是取色启发式，不是主体识别。
- `palette.py`：`mix_colors`，三色等权 OKLab 平均；`mutation_palette`，按贡献者一／二／亲代混合色构造三色。
- `scripts/render-fish.mjs`：`renderFish`，纯 SVG 三色简笔鱼模板。

2026-09-28 在指定群实际验证了两位成员的读取、头像下载、提色、亲代混色与 SVG／PNG 预览。自动测试覆盖混色稳定性、贡献者色与亲代色的映射、透明／灰度头像、小色块过滤和成员选择。

## 运行测试

在主仓目录运行：

```sh
venv/bin/python -m pytest src/infinite-mutation-fishing/tests
```

也可在子仓内使用宿主虚拟环境运行：

```sh
../../venv/bin/python -m pytest
```

QQ 插件依赖宿主已有的 NoneBot、适配器和插件管理器；独立测试 Web 骨架无需启动机器人或连接 Redis。
