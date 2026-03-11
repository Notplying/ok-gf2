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
        # self.default_config.update({"识别模式": "除杂色ocr1"})
        # self.config_description.update({
        #     '识别模式':'推图时使用的OCR预处理方式\n可尝试普通ocr, 除杂色ocr1(标准白色), 除杂色ocr2(更宽松的白色+部分灰色)\n使用场景分别是:背景和关卡卡片非白色系、关卡卡片非白色系，关卡卡片非白灰色系',
        # })
        # self.stamina_options = ["普通ocr", "除杂色ocr1","除杂色ocr2"]
        # self.config_type["识别模式"] = {
        #     "type": "drop_down",
        #     "options": self.stamina_options,
        # }

    def run(self):
        count = 0
        clicked = []
        last_fallback_name = None
        last_failed_name = None  # 用来保存上次进入 if not text 分支的关卡名
        last_failed_flag = False  # 标记上次循环是否进入过 if not text 分支
        map_ocr_box = self.box_of_screen(x=0, y=323 / 1080, to_x=1.0, to_y=727 / 1080)
        processors = [None, self.make_hsv_isolator(hR.WHITE), self.make_hsv_isolator(hR.WHITE_GRAY)]
        while True:
            last_clicked = None
            self.sleep(2)
            # 根据上次是否失败，选择 OCR 匹配规则
            self.next_frame()
            map_name_groups = []
            if last_failed_flag and last_failed_name:

                maps = []
                pattern = re.compile(re.escape(last_failed_name))

                for p in processors:
                    maps = self.ocr(box=map_ocr_box, match=pattern, log=True, frame_processor=p)
                    if maps:
                        break

                if maps:
                    maps=[maps[0]]  # 只保留第一个，避免重复点击
                    maps[0].name = "before_one_" + maps[0].name
                    maps[0].x = int(maps[0].x - 80 / 256 * self.width)  # 往左扩展一些识别区域，增加找到的概率
                    map_name_groups = [set([maps[0].name])]
                else:
                    map_name_groups = []
                last_failed_flag = False
            else:

                maps = []
                for p in processors:
                    maps.extend(self.ocr(box=map_ocr_box, match=map_re, log=True, frame_processor=p))

                maps,map_name_groups  = merge_maps(maps, x_threshold=40/1920*self.width, y_threshold=40/1080*self.height)

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
            for i, current_map in enumerate(maps):
                # 找到对应的名字组
                name_group = map_name_groups[i]  # map_name_groups 和 maps 是一一对应的
                # 判断这个组的所有名字是否已经点击过
                if not any(name in clicked for name in name_group):
                    # 全部加入 clicked
                    clicked.extend(name_group)
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
            if boxes := self.wait_ocr(box="right", match=["特殊奖励", '观看', '挑战'], time_out=3, log=True):
                if self.find_boxes(boxes, match=["特殊奖励"]):
                    text = self.find_boxes(boxes, match=['观看', '挑战'])
                    if not text:
                        # 保存当前失败的关卡名，标记上次进入过该分支
                        last_failed_name = current_map.name
                        last_failed_flag = True
                        clicked = [name for name in clicked if name not in name_group]      
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


def merge_maps(maps, x_threshold=40, y_threshold=40):
    merged = []  # 存最终的 map 对象
    merged_names = []  # 存每个合并组的所有 name

    for m in maps:
        for i, exist in enumerate(merged):
            if abs(m.x - exist.x) < x_threshold and abs(m.y - exist.y) < y_threshold:
                # 坐标取平均
                exist.x = int((exist.x + m.x) / 2)
                exist.y = int((exist.y + m.y) / 2)
                # 将当前 map 的名字加入该组
                merged_names[i].add(m.name)
                break
        else:
            merged.append(m)
            merged_names.append(set([m.name]))  # 新组，名字放入 set

    return merged, merged_names
