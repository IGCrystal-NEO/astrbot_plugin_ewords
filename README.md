# astrbot_plugin_ewords

**记单词及复习插件**  
版本：1.1.2  
作者：IGCrystal  
仓库：[https://github.com/IGCrystal/AstrBot_plugin_Ewords](https://github.com/IGCrystal/AstrBot_plugin_Ewords)

## 简介

AstrBot_plugin_Ewords 是一个用于 AstrBot 的记单词及复习插件。  
插件支持以下功能：  
- **记单词**：通过指令抽取不重复的单词，并记录到历史中。  
- **复习**：支持按组复习（使用最新一组记忆）和随机复习，提供中英文提示。  
- **验证**：对上一次复习结果进行验证，并给出反馈。  
- **切换词库**：支持通过指定词库文件切换词库，也可以列出当前可用词库。（默认使用位于插件目录下 `words/CET4.json` 的词库）  
- **清空历史**：清除所有记忆历史。  
- **定时提醒**：设置定时任务，定时提醒用户记单词。

## 安装

1. 将本插件（包括所有代码文件、`used.json`、以及 `words` 目录和词库文件）放置于 AstrBot 插件目录下，例如：  
   `/AstrBot-master/data/plugins/AstrBot_plugin_Ewords/`

2. 确保 `words` 目录下存在默认词库文件 `CET4.json`。如果没有指定词库，插件会自动使用默认词库，并提示“没有指定词库喵，已使用默认词库喵~”。

> [!NOTE]
> 词库来源为 [https://github.com/KyleBing/english-vocabulary](https://github.com/KyleBing/english-vocabulary)

## 使用方法

### 指令说明

- **记单词**  
  命令格式：`/ewords 记单词 <number>` (需要注意空格)
  例如：`/ewords 记单词 15`  
  如果没有输入数字，则默认记 10 个单词；如果输入数字小于 10，也默认记 10 个单词。

- **复习**  
  命令格式：`/ewords 复习 <方式> <复习类型>`  
  - 方式：  
    - `1`：英文→中文（请翻译）  
    - `2`：中文→英文（请写出对应单词）  
  - 复习类型：  
    - `1`：按组复习（使用最新一组记忆）  
    - `2`：随机复习（从所有记忆中随机抽取最多 10 个单词）  
  例如：`/ewords 复习 1 1`

- **验证/核对/校对/答案**  
  命令格式：`/ewords 验证 <答案1> <答案2> ...`  (使用空格分隔答案)
  根据上一次复习内容进行答案验证。

- **切换词库/切换**  
  命令格式：  
  - 切换词库：`/ewords 切换 <文件名>`  
    例如：`/ewords 切换 random`（文件名不需要后缀，会自动补全 .json）  
  - 列出所有词库：`/ewords 切换 list`

- **清空历史/清空**  
  命令格式：`/ewords 清空`  
  清空所有已记单词的历史记录。

- **设置定时/定时**  
  命令格式：`/ewords 设置定时 <参数>` (需要注意空格)
  例如：`/ewords 设置定时 一天` 或 ` /ewords 设置定时 5`  
  传入 “取消” 则取消定时任务。

- **帮助/help**  
  命令格式：`/ewords help`  
  显示所有指令及说明。

## 运行环境

- Python 3.7+
- AstrBot 框架

## 安装依赖

请参考 [requirements.txt](requirements.txt) 文件安装所需依赖。

## 注意事项

- 所有数据文件（词库、used.json）均存放于插件目录下，插件自动通过相对路径定位。
- 默认词库文件为 `CET4.json`，如果不存在将使用内置默认 CET4 词库（`DEFAULT_CET4_VOCAB`）。
- 如果用户在记单词前未指定词库，则默认使用 `CET4.json` 并提示“没有指定词库喵，已使用默认词库喵~”。

## 联系方式

如有问题或建议，请联系 `IGCrystal`。欢迎提交 `PR` ！

