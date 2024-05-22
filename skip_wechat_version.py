#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import traceback
from pymem import Pymem

address = [0x2367624, 0x2385AF0, 0x2385C44, 0x239C98C, 0x239EAFC, 0x23A1604]
skip_version = 0x63090A13   # 3.9.10.19 计算方法：https://jsrun.net/L55Kp


def fix_version(pm: Pymem):
    dll_base = 0
    for m in list(pm.list_modules()):
        path = m.filename
        if path.endswith("WeChatWin.dll"):
            dll_base = m.lpBaseOfDll
            break
    for offset in address:
        addr = offset + dll_base
        v = pm.read_uint(addr)
        if v == skip_version:  # 已经修复过了
            continue
        if v != 0x6307001e:  # 不是 3.7.0.30的微信版本
            raise Exception("当前微信版本不是3.7.0.30版本")
        print(f"地址{hex(addr)}更新数值为{hex(skip_version)}")
        pm.write_uint(addr, skip_version)
    print("好了，可以扫码登录了")


if __name__ == "__main__":
    try:
        if len(sys.argv) > 2:
            print("ERROR: 输入参数错误, 正确的参数为：[skip_version]")
            sys.exit(1)
        if len(sys.argv) > 1:
            skip_version = int(sys.argv[1], 16)
        fix_version(Pymem("WeChat.exe"))
    except Exception as e:
        traceback.print_exc()
        print(f"{e}，请确认微信程序已经打开！")