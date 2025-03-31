import re
import json
import random
import datetime
import asyncio
import logging
import os
from typing import List, Dict, Any

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register

# 配置日志
logger = logging.getLogger("WordPlugin")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# 内置默认CET4词库（示例，可根据需要扩展）
DEFAULT_CET4_VOCAB = [
    "abandon", "ability", "able", "about", "above", "abroad", "absence", "absolute",
    "absorb", "abstract", "abuse", "academic", "accent", "acceptable", "access", "accident"
]

@register("word_plugin", "IGCrystal", "记单词及复习插件", "1.1.2", "https://github.com/IGCrystal/AstrBot_plugin_Ewords")
class WordPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.context = context
        self.timer_task = None
        self.logger = logger

        # 从 config 中读取配置（如果有配置传入），否则使用默认值
        default_word_count = config.get("default_word_count", 10) if config else 10
        enable_timer = config.get("enable_timer", False) if config else False
        reminder_interval = config.get("reminder_interval", 60) if config else 60

        # 默认英文到中文映射（若词库能提供，则会自动更新）
        self.EN_TO_CN = {
            "apple": "苹果",
            "banana": "香蕉",
            "cherry": "樱桃",
            "date": "枣",
            "elderberry": "接骨木莓",
            "fig": "无花果",
            "grape": "葡萄",
            "honeydew": "哈密瓜",
            "kiwi": "猕猴桃",
            "lemon": "柠檬",
            "mango": "芒果",
            "nectarine": "油桃",
            "orange": "橙子",
            "papaya": "木瓜"
        }

        # 数据文件均放在插件目录下
        base_dir = os.path.dirname(__file__)
        self.vocab_dir = os.path.join(base_dir, "words")
        self.default_vocab_filename = "CET4.json"  # 默认词库文件名
        self.vocab_file = os.path.join(self.vocab_dir, self.default_vocab_filename)
        self.used_file = os.path.join(base_dir, "used.json")

        # 加载词库和使用记录
        self.vocabularies = self.load_vocab()
        self.used_words = set()
        self.word_groups = {}  # 格式：{ "group_id": [words] }
        self.load_used_data()

        # 存储最后一次复习数据
        self.last_review_words: List[str] = []
        self.last_review_mode: str = ""  # 仅支持 "1" 或 "2"

        # 标识是否切换过词库，默认未切换，使用默认词库
        self.vocab_switched = False

    # 辅助函数：将列表转换为每项前带序号的字符串
    def format_list_with_numbers(self, items: List[str]) -> str:
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

    # 加载词库：若文件不存在或格式不正确，则使用默认CET4词库
    def load_vocab(self) -> Dict[str, List[str]]:
        if not os.path.exists(self.vocab_file):
            self.logger.info(f"词库文件 {self.vocab_file} 不存在，使用默认CET4词库")
            return {"default": DEFAULT_CET4_VOCAB}
        try:
            with open(self.vocab_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                words = []
                mapping = {}
                for entry in data:
                    if isinstance(entry, dict) and "word" in entry:
                        word = entry["word"]
                        words.append(word)
                        if "translations" in entry and isinstance(entry["translations"], list) and entry["translations"]:
                            mapping[word] = entry["translations"][0].get("translation", "未知")
                if mapping:
                    self.EN_TO_CN = mapping
                self.logger.info(f"成功加载词库（列表格式），共 {len(words)} 个单词")
                return {"default": words}
            elif isinstance(data, dict):
                self.logger.info("成功加载词库（字典格式）")
                return data
            else:
                self.logger.error("词库文件格式不正确，使用默认CET4词库")
                return {"default": DEFAULT_CET4_VOCAB}
        except Exception as e:
            self.logger.error(f"加载词库失败：{e}，使用默认CET4词库")
            return {"default": DEFAULT_CET4_VOCAB}

    def load_used_data(self):
        try:
            with open(self.used_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.used_words = set(data.get("used_words", []))
                self.word_groups = data.get("word_groups", {})
                self.logger.info("成功加载使用记录")
        except Exception as e:
            self.logger.error(f"加载使用记录失败：{e}")
            self.used_words = set()
            self.word_groups = {}

    def save_used_data(self):
        data = {
            "used_words": list(self.used_words),
            "word_groups": self.word_groups
        }
        try:
            with open(self.used_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info("使用记录已保存")
        except Exception as e:
            self.logger.error(f"保存使用记录失败：{e}")

    def reset_used_words(self, vocab_list: List[str]):
        self.used_words = set(vocab_list)
        self.save_used_data()
        self.logger.info("已重置使用记录")

    def get_unique_words(self, count: int, library_name: str = "default") -> List[str]:
        vocab = self.vocabularies.get(library_name, [])
        if count > len(vocab):
            self.logger.info(f"请求单词数 {count} 超过词库总数 {len(vocab)}，自动调整为 {len(vocab)}")
            count = len(vocab)
        available = list(set(vocab) - self.used_words)
        if len(available) < count:
            self.logger.info("可用单词不足，重置使用记录")
            self.reset_used_words(vocab)
            available = list(set(vocab))
        count = min(count, len(available))
        selected = random.sample(available, count)
        self.used_words.update(selected)
        self.save_used_data()
        self.logger.info(f"获取 {count} 个不重复的单词")
        return selected

    def save_word_group(self, words: List[str]):
        group_id = datetime.date.today().isoformat()
        if group_id in self.word_groups:
            # 合并时去重并保持顺序
            combined = list(dict.fromkeys(self.word_groups[group_id] + words))
            self.word_groups[group_id] = combined
        else:
            self.word_groups[group_id] = words
        self.save_used_data()
        self.logger.info(f"保存单词组：{group_id}")

    def get_latest_group(self) -> List[str]:
        if not self.word_groups:
            return []
        latest_group = sorted(self.word_groups.keys())[-1]
        return self.word_groups.get(latest_group, [])

    def parse_time_interval(self, time_str: str) -> int:
        self.logger.info(f"解析时间参数：{time_str}")
        if "一天" in time_str:
            return 24 * 60 * 60
        if "小时" in time_str:
            num = int(''.join(re.findall(r'\d+', time_str)) or 1)
            return num * 60 * 60
        if "分钟" in time_str:
            num = int(''.join(re.findall(r'\d+', time_str)) or 10)
            return num * 60
        try:
            minutes = int(time_str)
            return minutes * 60
        except:
            return 10 * 60

    async def start_timer(self, unified_msg_origin: str, interval: int):
        self.logger.info(f"开始持续定时提醒，每 {interval} 秒提醒一次")
        while True:
            await asyncio.sleep(interval)
            try:
                message_chain = MessageChain().message("【提醒】该记单词啦！")
                await self.context.send_message(unified_msg_origin, message_chain)
                self.logger.info("发送定时提醒")
            except Exception as e:
                self.logger.error(f"发送定时提醒失败：{e}")

    @filter.command_group("ewords")
    def ewords(self):
        """记单词插件指令组"""
        pass

    @ewords.command("记单词")
    async def add_words(self, event: AstrMessageEvent):
        self.logger.info("接收到记单词指令")
        pattern = r"记单词\s*(\d+)"
        match = re.search(pattern, event.message_str)
        # 如果没有匹配到数字，则默认count为10
        count = int(match.group(1)) if match and match.group(1) else 10
        if count < 10:
            count = 10
        # 如果用户没有切换词库，则提示使用默认词库
        prompt = ""
        if not self.vocab_switched:
            prompt = "没有指定词库喵，已使用默认词库喵~ 默认为CET4喵~\n"
        words = self.get_unique_words(count)
        self.save_word_group(words)
        # 输出格式为：序号. 单词 - 单词意思
        result_lines = []
        for i, word in enumerate(words):
            translation = self.EN_TO_CN.get(word, "未知")
            result_lines.append(f"{i+1}. {word} - {translation}")
        reply = prompt + f"抽取的单词（共{len(words)}个）：\n" + "\n".join(result_lines)
        self.logger.info("记单词指令执行完毕")
        yield event.plain_result(reply)


    @ewords.command("复习")
    async def review_words(self, event: AstrMessageEvent):
        self.logger.info("接收到复习指令")
        self.load_used_data()  # 重新加载最新记录
        tokens = event.message_str.strip().split()
        if len(tokens) < 4:
            self.logger.error("复习指令参数不完整")
            yield event.plain_result("请完整输入复习指令，例如：/ewords 复习 1 1")
            return
        mode = tokens[2]  # 复习方式：1（英文→中文），2（中文→英文）
        if mode not in ["1", "2"]:
            self.logger.error(f"复习方式参数错误：{mode}")
            yield event.plain_result("复习方式不正确，请输入 1 或 2 喵～")
            return
        rtype = tokens[3]  # 复习类型：1 按组复习，2 随机复习
        self.last_review_mode = mode
        words = []
        if rtype == "1":
            group = self.get_latest_group()
            if not group:
                self.logger.error("无按组记录")
                yield event.plain_result("没有按组记录，请先使用记单词指令记录单词喵～")
                return
            words = group
            words = list(dict.fromkeys(words))
        elif rtype == "2":
            all_used = list(self.used_words)
            words = random.sample(all_used, min(10, len(all_used)))
        else:
            self.logger.error(f"复习类型参数错误：{rtype}")
            yield event.plain_result("复习类型不正确，请输入 1 或 2 喵～")
            return

        if not words:
            self.logger.error("无可复习单词")
            yield event.plain_result("没有可复习的单词喵～")
            return

        self.last_review_words = words
        if mode == "1":
            content = "复习开始！请翻译下面的单词：\n" + self.format_list_with_numbers(words)
        elif mode == "2":
            prompts = [self.EN_TO_CN.get(w, "未知") for w in words]
            content = "复习开始！请写出下列中文对应的英文单词：\n" + self.format_list_with_numbers(prompts)
        self.logger.info("复习内容已发送")
        yield event.plain_result(content)
        yield event.plain_result("请使用 /ewords 验证 指令，后跟空格分隔的答案，检查你的复习结果喵～")

    @ewords.command("验证", alias={'核对', '校对', '答案'})
    async def verify(self, event: AstrMessageEvent):
        self.logger.info("接收到验证指令")
        tokens = event.message_str.strip().split()
        if len(tokens) < 3:
            self.logger.error("验证指令参数不完整")
            yield event.plain_result("请在验证指令中输入你的答案，例如：/ewords 验证 苹果 香蕉 ...")
            return
        user_answers = tokens[2:]
        if not self.last_review_words:
            self.logger.error("没有复习记录")
            yield event.plain_result("没有找到上一次的复习记录，请先进行复习喵～")
            return
        expected = []
        if self.last_review_mode == "1":
            for w in self.last_review_words:
                expected.append(self.EN_TO_CN.get(w, "未知"))
        elif self.last_review_mode == "2":
            expected = self.last_review_words
        else:
            self.logger.error("复习方式记录错误")
            yield event.plain_result("复习方式记录错误喵～")
            return

        if len(user_answers) != len(expected):
            self.logger.error("答案数量不匹配")
            yield event.plain_result(f"答案数量不匹配，应该有 {len(expected)} 个答案喵～")
            return

        correct = sum(1 for ua, exp in zip(user_answers, expected) if ua.strip().lower() == exp.lower())
        feedback = [f"{i+1}. {'正确' if ua.strip().lower() == exp.lower() else f'错误（正确答案：{exp}）'}"
                    for i, (ua, exp) in enumerate(zip(user_answers, expected))]
        reply = f"验证结果：{correct}/{len(expected)} 正确\n" + "\n".join(feedback)
        self.logger.info("验证完成")
        yield event.plain_result(reply)

    @ewords.command("切换", alias={'切换词库'})
    async def switch_vocab(self, event: AstrMessageEvent):
        self.logger.info("接收到切换词库指令")
        if not os.path.exists(self.vocab_dir):
            os.makedirs(self.vocab_dir)
            self.logger.info(f"目录 {self.vocab_dir} 不存在，已创建。")
        tokens = event.message_str.strip().split()
        # 如果用户没有指定词库文件名，则提示使用默认词库
        if len(tokens) < 3 or not tokens[2].strip():
            yield event.plain_result("没有指定词库喵，已使用默认词库喵~")
            return
        param = tokens[2].strip()
        if param.lower() == "list":
            try:
                files = os.listdir(self.vocab_dir)
                vocab_files = [f for f in files if f.endswith(".json")]
                if not vocab_files:
                    yield event.plain_result("没有找到任何词库文件喵～")
                else:
                    reply = "可用词库列表：\n" + self.format_list_with_numbers(vocab_files)
                    yield event.plain_result(reply)
            except Exception as e:
                yield event.plain_result(f"获取词库列表失败: {e}")
            return
        if not param.endswith(".json"):
            param += ".json"
        vocab_path = os.path.join(self.vocab_dir, param)
        try:
            with open(vocab_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                words = []
                mapping = {}
                for entry in data:
                    if isinstance(entry, dict) and "word" in entry:
                        word = entry["word"]
                        words.append(word)
                        if "translations" in entry and isinstance(entry["translations"], list) and entry["translations"]:
                            mapping[word] = entry["translations"][0].get("translation", "未知")
                self.vocabularies["default"] = words
                self.EN_TO_CN = mapping
                self.reset_used_words(words)
                yield event.plain_result(f"成功切换词库为 '{param}' 喵～")
                self.logger.info(f"成功切换词库为 {param}")
            else:
                yield event.plain_result("词库文件格式不正确喵～")
        except Exception as e:
            yield event.plain_result(f"切换词库失败: {e}")

    @ewords.command("清空", alias={'清空历史'})
    async def clear_history(self, event: AstrMessageEvent):
        self.logger.info("接收到清空记忆指令")
        self.used_words = set()
        self.word_groups = {}
        self.save_used_data()
        yield event.plain_result("已清空所有记忆历史喵～")

    @ewords.command("设置定时", alias={'定时'})
    async def set_timer(self, event: AstrMessageEvent):
        self.logger.info("接收到设置定时指令")
        tokens = event.message_str.strip().split(maxsplit=2)
        if len(tokens) < 3:
            self.logger.error("设置定时参数不完整")
            yield event.plain_result("请提供时间参数，如 '一天', '1小时', 自定义分钟数，或 '取消' 来取消定时提醒。")
            return
        param = tokens[2].strip()
        if param == "取消":
            if self.timer_task and not self.timer_task.done():
                self.timer_task.cancel()
                self.logger.info("定时任务已取消")
                yield event.plain_result("定时提醒已取消喵～")
            else:
                yield event.plain_result("当前没有定时任务喵～")
            return
        time_str = param
        seconds = self.parse_time_interval(time_str)
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
            self.logger.info("旧定时任务已取消")
        self.timer_task = asyncio.create_task(
            self.start_timer(event.unified_msg_origin, seconds)
        )
        self.logger.info(f"定时提醒设置为 {time_str}")
        yield event.plain_result(f"定时提醒已设置为 {time_str}，请注意查收消息喵～")

    @ewords.command("help", alias={'帮助'})
    async def show_help(self, event: AstrMessageEvent):
        self.logger.info("接收到帮助指令")
        help_text = (
            "【ewords 指令组】可用指令列表：\n"
            "1. /ewords 记单词 <数字> —— 记单词（例如：/ewords 记单词 15）\n"
            "2. /ewords 复习 <方式> <复习类型> —— 复习指令\n"
            "    方式：1（英文→中文），2（中文→英文）\n"
            "    复习类型：1 按组复习（使用最新一组记录），2 随机复习\n"
            "    例如：/ewords 复习 1 1\n"
            "3. /ewords 验证 <答案1> <答案2> ... —— 验证上次复习答案\n"
            "4. /ewords 切换 <文件名|list> —— 切换词库或列出词库文件（例如：/ewords 切换 random 或 /ewords 切换 list）\n"
            "5. /ewords 清空 —— 清空所有记忆历史\n"
            "6. /ewords 设置定时 <参数> —— 设置定时提醒（例如：/ewords 设置定时 一天 或 /ewords 设置定时 5，传入‘取消’会取消提醒）\n"
            "7. /ewords help —— 显示帮助喵♡～"
        )
        yield event.plain_result(help_text)

    def generate_sentence_with_word(self, word: str) -> str:
        return f"I enjoy eating **{word}** when the weather is nice."

    async def terminate(self):
        if self.timer_task:
            self.timer_task.cancel()
            self.logger.info("定时任务已取消")

