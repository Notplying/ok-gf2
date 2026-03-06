if __name__ == '__main__':
    from src.config import config
    from ok import OK

    config = config
    config["ocr"]["params"]["Global.with_openvino"] = False
    config["profile_name"] = "direct-ml"
    config['debug'] = True

    ok = OK(config)
    ok.start()
