from src.tasks.BaseGfTask import BaseGfTask,stamina_re
from src.image.hsv_config import HSVRange as hR

class TestTask(BaseGfTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "测试用"
    def run(self):
        skip_end_match = ["饮品加成", "确认"]
        self.skip_dialogs(end_match=skip_end_match, time_out=60)
