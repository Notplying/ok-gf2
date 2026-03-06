if __name__ == '__main__':
    from src.config import config
    from ok import OK

    config = config
    config["ocr"]["params"]["use_openvino"] = False
    config["profile_name"] = "direct-ml"

    ok = OK(config)
    ok.start()
