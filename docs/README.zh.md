# Only4BMS

<img width="2556" height="1439" alt="스크린샷 2026-02-24 230333" src="https://github.com/user-attachments/assets/68d1891b-891b-4927-ab81-96f7bbc098f7" />

[![Only4BMS AI Battle1](https://img.youtube.com/vi/mrSUp4h7DnE/0.jpg)](https://youtu.be/mrSUp4h7DnE)

7键？不，谢谢。

这是一个基于 Pygame 的 BMS 播放器，它会**强制**将所有 BMS 谱面**重新排列**为 **4 键 (DFJK)** 进行播放。

## 项目概述

Only4BMS 是为那些面对复杂的 7 键或 14 键 BMS 谱面时感叹“我该怎么玩这些？”的 4 键纯粹主义者而创建的。

本项目使用 Pygame 解析 BMS 文件，并提供了一个可以将任何谱面格式**重新映射到 4 条轨道**，并配合按键音进行游玩的环境。

## 主要功能

**强制 4 键映射**：使用数学算法自动将 5 键、7 键、10 键和 14 键谱面分配到 4 条轨道（D、F、J、K）。

**密度检查**：在 7 键谱面合并为 4 键时，检查并可视化音符密度。

## 🛠️ 技术栈

**语言**：Python 3.x

**库**：Pygame（音频与渲染）

**格式**：Be-Music Script (.bms, .bme, .bml)

## 如何游玩（添加歌曲与运行）

1. **获取游戏**：下载预编译的 `Only4BMS.exe` 或自行编译。
2. **启动**：在任何文件夹中运行 `Only4BMS.exe` 即可。
3. **`bms` 文件夹**：启动时，游戏会自动在可执行文件所在目录创建 `bms` 文件夹。如果未找到歌曲，它会生成一个基础的模拟演示曲。
4. **添加您自己的歌曲**：
   - 下载 BMS/BME/BML 文件及相关的媒体文件（音频/BGA 视频）。
   - 将它们解压到 `bms/` 目录下的各自子文件夹中。
   - 示例结构：
     ```text
     [包含 Only4BMS.exe 的目录]
     ├── Only4BMS.exe
     └── bms/
         ├── Awesome Track/
         │   ├── song.bms
         │   ├── audio.wav
         │   └── video.mp4
         └── Another Track/
             └── ...
     ```

## 🤖 AI 训练与多玩家

Only4BMS 具有基于**强化学习 (PPO)** 的 AI 多玩家模式。

### 工作原理
- AI 使用 `stable-baselines3` 在程序生成的节奏音轨和无版演示曲上进行训练。
- **法律合规**：为了确保道德标准，官方发布版本捆绑了在 CI/CD 过程中*仅*使用非商业数据训练的模型。
- **难度**：
  - **NORMAL**：训练 25,000 步。准确率高，但偶尔会有类似人类的错误。
  - **HARD**：训练 40,000 步。几乎完美的时机和连击维持。

### 本地训练
如果您希望在本地训练自己的模型：
1. 安装依赖：`pip install stable-baselines3 shimmy gymnasium torch`
2. 运行训练脚本：`python -m only4bms.ai.train`
3. 生成的 `model_normal.zip` 和 `model_hard.zip` 将保存在 `src/only4bms/ai/` 中。

### 自动化 CI/CD
我们的 GitHub Actions 工作流会在每次发布时使用捆绑的 `Mock Song Demo` 从零开始重新训练 AI 模型。这确保了分发给用户的二进制文件始终是“干净”且优化过的。

<a href="https://minwook-shin.itch.io/only4bms" class="btn">在 itch.io 上游玩</a>

## 透明度声明：

Only4BMS 是一个充满激情的个人项目。

为了简化制作过程，我在代码编写中采用了 AI 辅助技术。

这使我能够突破个人创作的界限，确保最终游戏的精致感和完整性。

## 🤝 贡献

非常欢迎 4 键用户提交错误报告和功能建议！

## 📜 许可证

MIT 许可证 - 欢迎自由修改和分发。请为 4 键用户维护和平。
