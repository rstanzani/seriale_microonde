# -*- coding: utf-8 -*-
"""
Created on Tue Oct  3 12:22:20 2023

@author: ronny
"""

import psutil
import os
import time

name = "UI.exe"
local_path = "D:\\Data\\Lavoro\\Swhard\\DIME\\Microonde\\codice_seriale_python"

while True:
    time.sleep(60)
    if not name in (p.name() for p in psutil.process_iter()):
        os.startfile(f"{local_path}\\UI.exe")
        print(f"Start execution of {name}")