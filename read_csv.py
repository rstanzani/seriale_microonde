# -*- coding: utf-8 -*-
"""
Created on Tue Mar 28 08:57:22 2023

@author: ronny
"""

import pandas #USED ONLY TO AVOID AN IMPORT ERROR FROM MATPLOTLIB IN SOME CONFIGURATIONS
import re
import os

def update_config(config_path, new_csv_path):

    with open(config_path, 'r') as file:
        line = file.readline()
    file.close()
    elem = line.split(";")
    if len(elem) >=2:
        elem[1] = new_csv_path
    else: # case with only one value not ending with ";"
        elem.append(new_csv_path)

    lines = ""
    for i in range(0, 3): # save only 3 values in the csv (to remove old empty values)
        lines += elem[i] + ";"

    with open(config_path, 'w', encoding='utf-8') as file:
        file.write(lines)

    file.close()


def read_and_plot(ui, filepath, is_plot_present = False):
    execute = False
    label = []
    duration = []
    freq = []
    power = []
    msg = 'File correctly imported'
    error = False

    if filepath == "": # in this case it only initializes the canvas
        ui.MplWidget.canvas.axes = ui.MplWidget.canvas.figure.add_subplot(111)
        ui.MplWidget_2.canvas.axes = ui.MplWidget_2.canvas.figure.add_subplot(111)
        error = True

    else:
        print("### Analyzing the filename... ")
        if filepath[-7:] == ".rf.csv": # check if the name is correct and if the file exists
            if os.path.isfile(filepath):
                execute = True
            else:
                msg = "ERROR: missing file, please check the file name."
                print("ERROR: missing file, please check the file name.")
                error = True
        if execute:
            file = open(filepath, 'r')
            lines = file.readlines()
            file.close()

            for i in range(0, len(lines)):
                if i == 0:
                    label.append([lines[i].split(",")[0], lines[i].split(",")[1], lines[i].split(",")[2]])
                    continue
                duration.append(abs(float(lines[i].split(",")[0])))
                freq.append(int(lines[i].split(",")[1]))
                power.append(int(re.split(r"\D+", lines[i].split(",")[2])[0]))

            minfreq = min(freq)
            maxfreq = max(freq)
            minpower = min(power)
            maxpower = max(power)
            minduration = min(duration)

            # control the inserted values
            if  minfreq<2400 or maxfreq>2500:
                msg = "ERROR: wrong range for frequency. Correct range: 2400÷2500 MHz."
                error = True
            if  minpower<0 or maxpower>251:
                msg = "ERROR: wrong range for power. Correct range: 0÷250 W."
                error = True

            for i in freq:
                if i % 2 != 0:
                    msg = "ERROR: odd value for frequency. Tip: the numbers for the frequency should be even."
                    # print(msg)
                    error = True
                    continue
            if minduration < 1:
                msg = "ERROR: the minimum duration should be 1 s"
                error = True

            if not error:
                time = []

                for i in range(0, len(duration)+1):
                    time.append(sum(duration[:i]))
                duration[0]
                freq.append(freq[len(freq)-1])
                power.append(power[len(power)-1])

                if is_plot_present:
                    ui.MplWidget.canvas.axes.clear()
                else:
                    ui.MplWidget.canvas.axes = ui.MplWidget.canvas.figure.add_subplot(111)

                ui.MplWidget.canvas.axes.step(time, freq, color='blue', alpha=0.5, where='post', zorder=-2)
                ui.MplWidget.canvas.axes.set_ylabel("{}".format(label[0][1]), color="blue", fontsize=10)
                ui.MplWidget.canvas.axes.tick_params(axis='y', colors='blue', labelsize=9)
                ui.MplWidget.canvas.axes.fill_between(time, freq, step="post", alpha=0.2, color="blue")
                ui.MplWidget.canvas.axes.set_ylim([minfreq-0.1*(maxfreq-minfreq), maxfreq+0.1*(maxfreq-minfreq)])
                ui.MplWidget.canvas.axes.grid(linestyle = '--', linewidth = 0.4, zorder=-1)

                ui.MplWidget.canvas.axes.scatter(time, freq, facecolor='white', edgecolor='blue', marker="o", alpha=1)
                ui.MplWidget.canvas.axes.set_ylim([minfreq-0.1*(maxfreq-minfreq), maxfreq+0.1*(maxfreq-minfreq)])

                if is_plot_present:
                    ui.MplWidget_2.canvas.axes.clear()
                else:
                    ui.MplWidget_2.canvas.axes = ui.MplWidget_2.canvas.figure.add_subplot(111)

                ui.MplWidget_2.canvas.axes.step(time, power, color='orange', alpha=0.5, where='post', zorder=-2)
                ui.MplWidget_2.canvas.axes.set_xlabel("Time [s]", fontsize=9, labelpad=6)
                ui.MplWidget_2.canvas.axes.set_ylabel("{}".format(label[0][2]), color="orange", fontsize=10, labelpad=-6)
                ui.MplWidget_2.canvas.axes.tick_params(axis='y', colors='orange', labelsize=9)
                ui.MplWidget_2.canvas.axes.fill_between(time, power, step="post", alpha=0.2, color="orange")
                ui.MplWidget_2.canvas.axes.grid(linestyle = '--', linewidth = 0.4, zorder=-1)

                ui.MplWidget_2.canvas.axes.scatter(time, power, facecolor='white', edgecolor='orange', marker="o", alpha=1)
                if maxpower != minpower:
                    ui.MplWidget_2.canvas.axes.set_ylim([minpower-0.1*(maxpower-minpower), maxpower+0.1*(maxpower-minpower)])
                else:
                    ui.MplWidget_2.canvas.axes.set_ylim([minpower-0.1*minpower, maxpower+0.1*maxpower])

                if is_plot_present:
                    ui.MplWidget.canvas.draw()  #TODO very slow with this, understand why
                    ui.MplWidget_2.canvas.draw()

                update_config("config.csv", filepath)

        else:
            print("The filename is wrong.")
            msg = "ERROR: the file has the wrong name. Please retry with another one."
            error = True
    return duration, freq, power, error, msg