# main.py
import re
import random
import datetime
import asyncio
import threading

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

# 全局变量：词库、已使用单词集合、组单词记录
VOCABULARIES = {
    "default": ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape",
                "honeydew", "kiwi", "lemon", "mango", "nectarine", "orange", "papaya"]
}
# 英文单词对应中文释义，用于复习检测（示例数据）
EN_TO_CN = {
    "apple": "苹果", "banana": "香蕉", "cherry": "樱桃", "date": "枣",
    "elderberry": "接骨木莓", "fig": "无花果", "grape": "葡萄",
    "honeydew": "哈密瓜", "kiwi": "猕猴桃", "lemon": "柠檬",
    "mango": "芒果", "nectarine": "油桃", "orange": "橙子", "papaya": "木瓜"
}
used_words = set()  # 已经发送过的单词集合
word_groups = {}    # 按日期记录的单词组，格式：{"YYYY-MM-DD": [word, ...]}

# 定时提醒相关变量
timer_interval = None
timer_task = None

def reset_used_words(vocab_list):
    # 重置used_words集合，确保词库足够
    global used_words
    used_words = set(vocab_list)

def get_unique_words(count, library_name="default"):
    global used_words
    vocab = VOCABULARIES.get(library_name, [])
    available = list(set(vocab) - used_words)
    if len(available) < count:
        # 如果唯一单词不足，重置已使用记录
        reset_used_words(vocab)
        available = list(set(vocab))
    selected = random.sample(available, count)
    used_words.update(selected)
    return selected

def save_word_group(words):
    today = datetime.date.today().isoformat()
    if today in word_groups:
        word_groups[today].extend(words)
    else:
        word_groups[today] = words

def parse_time_interval(time_str):
    # 支持预设：一天, 1小时, 30分钟, 10分钟，或自定义数字（单位：分钟）
    if "一天" in time_str:
        return 24 * 60 * 60
    if "小时" in time_str:
        num = int(''.join(filter(str.isdigit, time_str)) or 1)
        return num * 60 * 60
    if "分钟" in time_str:
        num = int(''.join(filter(str.isdigit, time_str)) or 10)
        return num * 60
    try:
        minutes = int(time_str)
        return minutes * 60
    except:
        return 10 * 60

async def start_timer(context: Context, unified_msg_origin: str):
    global timer_interval, timer_task
    while timer_interval:
        await asyncio.sleep(timer_interval)
        # 发送记单词提醒给用户
        await context.send_message(unified_msg_origin, [{"type": "plain", "data": {"text": "【提醒】该记单词啦！"}}])

@register("word_plugin", "YourName", "记单词及复习插件", "1.0.0", "https://github.com/your_repo")
class WordPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        # 如果需要持久化，可以在 data 目录存储 used_words 和 word_groups
        self.context = context
        self.timer_future = None

    @filter.command("记单词")
    async def add_words(self, event: AstrMessageEvent):
        """
        记单词指令：
        格式：记单词+{数字}
        若数字小于10则默认为10。
        """
        # 匹配命令格式
        pattern = r"记单词\+(\d+)"
        match = re.match(pattern, event.message_str)
        count = int(match.group(1)) if match else 10
        if count < 10:
            count = 10
        # 获取不重复的单词
        words = get_unique_words(count)
        save_word_group(words)
        reply = f"抽取的单词（共{len(words)}个）：\n" + ", ".join(words)
        yield event.plain_result(reply)

    @filter.command("复习")
    async def review_words(self, event: AstrMessageEvent):
        """
        复习指令：
        进入复习交互流程，首先选择复习模式：
         1. 按组复习（输入组日期，格式YYYY-MM-DD）
         2. 随机复习（从历史单词中随机抽取10个）
        然后选择复习方式：
         1. 根据英文拼写判断中文意思
         2. 根据中文意思写出完整单词
         3. 提示生成句子（**包裹的单词）
        """
        # 第一步：选择复习模式
        prompt_mode = ("请选择复习模式：\n"
                       "1. 按组复习（输入指定组的日期，格式YYYY-MM-DD）\n"
                       "2. 随机复习（直接输入数字 2）")
        yield event.plain_result(prompt_mode)
        # 等待用户回复（这里简单模拟，实际请使用会话控制）
        mode_resp = await self.context.wait_for_message(event.unified_msg_origin, timeout=30)
        mode = mode_resp.strip()
        if mode == "1":
            yield event.plain_result("请输入组的日期（YYYY-MM-DD）：")
            date_resp = await self.context.wait_for_message(event.unified_msg_origin, timeout=30)
            group_date = date_resp.strip()
            words = word_groups.get(group_date, [])
            if not words:
                yield event.plain_result(f"未找到日期为 {group_date} 的单词组。")
                return
        elif mode == "2":
            # 随机抽取10个历史单词
            all_used = list(used_words)
            if len(all_used) < 10:
                words = all_used
            else:
                words = random.sample(all_used, 10)
        else:
            yield event.plain_result("无效的复习模式。")
            return

        # 第二步：选择复习方式
        prompt_method = ("请选择复习方式：\n"
                         "1. 根据英文拼写判断中文意思\n"
                         "2. 根据中文意思写出完整单词\n"
                         "3. 提示生成句子判断**包裹单词的中文意思")
        yield event.plain_result(prompt_method)
        method_resp = await self.context.wait_for_message(event.unified_msg_origin, timeout=30)
        method = method_resp.strip()
        # 开始复习每个单词
        for word in words:
            if method == "1":
                # 方式1：根据英文单词提示，让用户输入中文意思
                answer_prompt = f"请回答：单词 **{word}** 的中文意思是？"
                yield event.plain_result(answer_prompt)
                user_answer = await self.context.wait_for_message(event.unified_msg_origin, timeout=30)
                correct = EN_TO_CN.get(word, "未知")
                if re.fullmatch(correct, user_answer.strip()):
                    yield event.plain_result("回答正确！")
                else:
                    yield event.plain_result(f"回答错误，正确答案是：{correct}")
            elif method == "2":
                # 方式2：根据中文提示，让用户写出英文单词（严格匹配）
                correct = word  # 英文单词本身
                chinese = EN_TO_CN.get(word, "未知")
                answer_prompt = f"请回答：中文【{chinese}】对应的英文单词是？"
                yield event.plain_result(answer_prompt)
                user_answer = await self.context.wait_for_message(event.unified_msg_origin, timeout=30)
                if user_answer.strip() == correct:
                    yield event.plain_result("回答正确！")
                else:
                    yield event.plain_result(f"回答错误，正确答案是：{correct}")
            elif method == "3":
                # 方式3：由插件生成提示词，让大语言模型生成包含 **包裹单词** 的句子（此处模拟生成句子）
                sentence = self.generate_sentence_with_word(word)
                answer_prompt = f"请根据下面句子判断**包裹的单词的中文意思：\n{sentence}"
                yield event.plain_result(answer_prompt)
                user_answer = await self.context.wait_for_message(event.unified_msg_origin, timeout=30)
                correct = EN_TO_CN.get(word, "未知")
                if re.fullmatch(correct, user_answer.strip()):
                    yield event.plain_result("回答正确！")
                else:
                    yield event.plain_result(f"回答错误，正确答案是：{correct}")
            else:
                yield event.plain_result("无效的复习方式。")
                return
        # 复习结束，调用大语言模型输出鼓励（这里模拟静态鼓励信息）
        encouragement = "恭喜你完成复习！你真的很棒，继续努力，本公主永远支持你喵～"
        yield event.plain_result(encouragement)

    def generate_sentence_with_word(self, word: str) -> str:
        # 简单生成包含**包裹单词**的句子，实际可调用 LLM 接口生成更优句子
        return f"I enjoy eating **{word}** when the weather is nice."

    @filter.command("更换词库")
    async def change_vocabulary(self, event: AstrMessageEvent):
        """
        更换词库指令：列出当前可用的词库列表。
        """
        if not VOCABULARIES:
            yield event.plain_result("当前没有词库，请先添加词库。")
        else:
            lib_list = "\n".join(f"{idx+1}. {name}" for idx, name in enumerate(VOCABULARIES.keys()))
            reply = f"当前可用词库：\n{lib_list}"
            yield event.plain_result(reply)

    @filter.command("设置定时")
    async def set_timer(self, event: AstrMessageEvent):
        """
        设置定时提醒指令：
        命令格式示例：设置定时一天 / 设置定时1小时 / 设置定时+数字（单位：分钟）
        """
        # 提取时间字符串
        time_str = event.message_str.replace("设置定时", "").strip()
        if not time_str:
            yield event.plain_result("请提供时间参数，如 '一天', '1小时', 或自定义分钟数。")
            return
        seconds = parse_time_interval(time_str)
        global timer_interval, timer_task
        timer_interval = seconds
        # 启动定时任务（如果未启动）
        if not timer_task or timer_task.done():
            timer_task = asyncio.create_task(start_timer(self.context, event.unified_msg_origin))
        yield event.plain_result(f"定时提醒已设置为 {time_str}。")

    async def terminate(self):
        # 当插件卸载时，取消定时任务
        global timer_task, timer_interval
        timer_interval = None
        if timer_task:
            timer_task.cancel()
