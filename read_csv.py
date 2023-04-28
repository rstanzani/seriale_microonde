# -*- coding: utf-8 -*-
"""
Created on Tue Mar 28 08:57:22 2023

@author: ronny
"""

import pandas #USED ONLY TO AVOID AN IMPORT ERROR FROM MATPLOTLIB IN SOME CONFIGURATIONS
import matplotlib.pyplot as plt
import re

# filepath = "D:\Downloads\Book2.rf.csv"
def read_and_plot(filepath, showfig=False, savefig=False):
    execute = False
    # lists containing the data from the csv
    label = []
    duration = []
    freq = []
    power = []
    msg = 'File correctly imported'

    if filepath[-7:] == ".rf.csv":
        execute = True
    if execute:
        file = open(filepath, 'r')
        lines = file.readlines()
        file.close()

        error = False
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
        # maxfoldback = max(foldback)

        # validate the inserted values
        if  minfreq<2400 or maxfreq>2500:
            msg = "ERROR: wrong range for frequency. Correct range: 2400÷2500 MHz."
            # print(msg)
            error = True
        if  minpower<0 or maxpower>300:
            msg = "ERROR: wrong range for power. Correct range: 0÷300 W."
            # print(msg)
            error = True
        # if  minfoldback<0 or maxfoldback>250:
        #     print("ERROR: wrong range for foldback. Correct range: 0÷250 W.")
        #     error = True
        for i in freq:
            if i % 2 != 0:
                msg = "ERROR: odd value for frequency. Tip: the numbers for the frequency should be even."
                # print(msg)
                error = True
                continue
        if minduration < 1:
            msg = "ERROR: the minimum duration should be 1 s"
            # print(msg)
            error = True

        if not error:
            # step_duration = 5 # seconds
            # time = sum(duration)
            time = []

            for i in range(0, len(duration)+1):
                time.append(sum(duration[:i]))
            duration[0]

            freq.append(freq[len(freq)-1])
            power.append(power[len(power)-1])
            # time = np.linspace(0, sum(duration), sum(duration))

            if showfig:
                fig,ax = plt.subplots(2)

                ax[0].step(time, freq, color='blue', alpha=0.5, where='post', zorder=-2)
                ax[0].set_ylabel("{}".format(label[0][1]), color="blue", fontsize=13, labelpad=10)
                ax[0].tick_params(axis='y', colors='blue', labelsize=9)
                ax[0].fill_between(time, freq, step="post", alpha=0.2, color="blue")
                ax[0].set_ylim([minfreq-0.1*(maxfreq-minfreq), maxfreq+0.1*(maxfreq-minfreq)])
                ax[0].grid(linestyle = '--', linewidth = 0.4, zorder=-1)

                ax[0].scatter(time, freq, facecolor='white', edgecolor='blue', marker="o", alpha=1)
                ax[0].set_ylim([minfreq-0.1*(maxfreq-minfreq), maxfreq+0.1*(maxfreq-minfreq)])

                ax[1].step(time, power, color='orange', alpha=0.5, where='post', zorder=-2)
                ax[1].set_xlabel("Time [s]", fontsize=9, labelpad=6)
                ax[1].set_ylabel("{}".format(label[0][2]), color="orange", fontsize=13, labelpad=1)
                ax[1].tick_params(axis='y', colors='orange', labelsize=9)
                ax[1].fill_between(time, power, step="post", alpha=0.2, color="orange")
                ax[1].grid(linestyle = '--', linewidth = 0.4, zorder=-1)

                ax[1].scatter(time, power, facecolor='white', edgecolor='orange', marker="o", alpha=1)
                if maxpower != minpower:
                    ax[1].set_ylim([minpower-0.1*(maxpower-minpower), maxpower+0.1*(maxpower-minpower)])
                else:
                    ax[1].set_ylim([minpower-0.1*minpower, maxpower+0.1*maxpower])

                if savefig:
                    fig.savefig('plot.jpg', format='jpeg', dpi=300)
            if savefig and not showfig:
                msg = "The image was not created, please enable showfig parameter"
                # print(msg)

    else:
        msg = "ERROR: the file has the wrong name. Please retry with another one."
        # print(msg)
        error = True
    return duration, freq, power, error, msg


#%% Main

# filepath = "D:\Downloads\Book2.rf.csv"
# duration, freq, power = read_and_plot(filepath, showfig=True, savefig=True)


# from tkinter import *
# from tkinter import filedialog

# def openFile():
#     filepath = filedialog.askopenfilename(initialdir="C:\\Users", title="Open file okay?",
#                                           filetypes= (("text files","*.txt"),("all files","*.*")))
#     file = open(filepath,'r')
#     print(file.read())
#     file.close()

# window = Tk()
# button = Button(text="Open",command=openFile)
# button.pack()
# window.mainloop()

















