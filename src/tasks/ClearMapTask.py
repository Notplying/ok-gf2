import re
from os import remove
from ok import Logger
from src.tasks.BaseGfTask import BaseGfTask, map_re
from src.image.hsv_config import HSVRange as hR
logger = Logger.get_logger(__name__)


class ClearMapTask(BaseGfTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "推图,可尝试多种识别方式"
        self.description = "从要推的图的最左边开始"
        self.default_config.update({"识别模式": "除杂色ocr1"})
        self.config_description.update({
            '识别模式':'推图时使用的OCR预处理方式\n可尝试普通ocr, 除杂色ocr1(标准白色), 除杂色ocr2(更宽松的白色+部分灰色)\n使用场景分别是:背景和关卡卡片非白色系、关卡卡片非白色系，关卡卡片非白灰色系',
        })
        self.stamina_options = ["普通ocr", "除杂色ocr1","除杂色ocr2"]
        self.config_type["识别模式"] = {
            "type": "drop_down",
            "options": self.stamina_options,
        }

    def run(self):
        count = 0
        clicked = []
        last_fallback_name = None
        last_failed_name = None  # 用来保存上次进入 if not text 分支的关卡名
        last_failed_flag = False  # 标记上次循环是否进入过 if not text 分支
        map_ocr_box = self.box_of_screen(x=486 / 1920, y=323 / 1080, to_x=1.0, to_y=727 / 1080)
        if self.config['识别模式'] != "普通ocr":
            if self.config['识别模式'] == "除杂色ocr1":
                map_frame_processor = self.make_hsv_isolator(hR.WHITE)
            else:
                map_frame_processor = self.make_hsv_isolator(hR.WHITE_GRAY)
        else:
            map_frame_processor = None
        while True:
            last_clicked = None
            self.sleep(2)

            # 根据上次是否失败，选择 OCR 匹配规则
            self.next_frame()
            if last_failed_flag and last_failed_name:
                maps = self.ocr(
                    box=map_ocr_box,
                    match=re.compile(last_failed_name),
                    log=True,
                    frame_processor=map_frame_processor,
                )
                if maps:
                    maps[0].name = "before_one_" + maps[0].name
                    print(self.frame.shape)
                    maps[0].x = maps[0].x - 80 / 256 * self.frame.shape[1]
                last_failed_flag = False  # 使用一次后清除标记
            else:
                maps = self.ocr(
                    box=map_ocr_box,
                    match=map_re,
                    log=True,
                    frame_processor=map_frame_processor,
                )

            maps = sorted(maps, key=lambda obj: obj.x)
            self.log_debug('maps: {}'.format(maps))

            if len(maps) == 0:
                if count == 0:
                    raise Exception('未找到要推的图!')
                else:
                    self.log_info(f'推图完成, 共{count}个!', notify=True)
                    return

            checked = False
            current_map = None
            for i in range(len(maps)):
                current_map = maps[i]
                if current_map.name not in clicked:
                    clicked.append(current_map.name)
                    checked = True
                    last_clicked = current_map
                    self.click(current_map, after_sleep=2)
                    break

            if not checked:
                # 当前兜底目标
                fallback = maps[-1]
                if last_fallback_name == fallback.name:
                    self.log_info(f'推图完成, 共{count}个!', notify=True)
                    return
                last_fallback_name = fallback.name
                self.click(fallback, after_sleep=2)
                self.back(after_sleep=2)
                continue

            self.sleep(1)
            if len(maps[0].name) > 10:
                pass
            if boxes := self.wait_ocr(box="right", match=["特殊奖励", '观看', '挑战'], time_out=3, log=True):
                if self.find_boxes(boxes, match=["特殊奖励"]):
                    text = self.find_boxes(boxes, match=['观看', '挑战'])
                    if not text:
                        # 保存当前失败的关卡名，标记上次进入过该分支
                        last_failed_name = current_map.name
                        last_failed_flag = True

                        if current_map.name in clicked:
                            clicked.remove(current_map.name)
                        self.back(after_sleep=2)
                        continue

                    # 正常处理挑战或观看
                    self.click(text, after_sleep=2)
                    count += 1
                    if text[0].name == '挑战':
                        self.auto_battle(end_match=map_re, has_dialog=True)
                    else:
                        self.skip_dialogs(end_match=map_re)

                    if last_clicked:
                        self.log_debug(f'重新点击上一次关卡: {last_clicked.name}')
                        if self.wait_click_ocr(match=last_clicked.name, time_out=3, log=True, after_sleep=1):
                            self.back(after_sleep=2)
                else:
                    self.back(after_sleep=2)
            self.sleep(1)
