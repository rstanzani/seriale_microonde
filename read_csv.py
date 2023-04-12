# -*- coding: utf-8 -*-
"""
Created on Tue Mar 28 08:57:22 2023

@author: ronny
"""
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
            duration.append(abs(int(lines[i].split(",")[0])))
            freq.append(int(lines[i].split(",")[1]))
            power.append(int(re.split(r"\D+", lines[i].split(",")[2])[0]))
    
        minfreq = min(freq)
        maxfreq = max(freq)
        minpower = min(power)
        maxpower = max(power)
        # minduration = min(foldback)
        # maxfoldback = max(foldback)
        
        # validate the inserted values
        if  minfreq<2400 or maxfreq>2500:
            print("ERROR: wrong range for frequency. Correct range: 2400÷2500 MHz.")
            error = True
        if  minpower<0 or maxpower>300:
            print("ERROR: wrong range for power. Correct range: 0÷300 W.")
            error = True
        # if  minfoldback<0 or maxfoldback>250:
        #     print("ERROR: wrong range for foldback. Correct range: 0÷250 W.")
        #     error = True
        for i in freq:
            if i % 2 != 0:
                print("ERROR: odd value for frequency. Tip: the numbers for the frequency should be even.")
                error = True
                continue
    
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
                fig,ax = plt.subplots()

                # axis for frequency step function
                ax.step(time, freq, color='blue', alpha=0.5, where='post')
                ax.set_xlabel("Time [s]", fontsize=14)
                ax.set_ylabel("{}".format(label[0][1]), color="blue", fontsize=14)
                ax.tick_params(axis='y', colors='blue')
                ax.fill_between(time, freq, step="post", alpha=0.2, color="blue")
                ax.set_ylim([minfreq-0.1*(maxfreq-minfreq), maxfreq+0.1*(maxfreq-minfreq)])

                # axis for power step function
                ax2 = ax.twinx()
                ax2.step(time, power, color='orange', alpha=0.5, where='post')
                ax2.set_ylabel("{}".format(label[0][2]), color="orange", fontsize=14)
                ax2.tick_params(axis='y', colors='orange')
                ax2.fill_between(time, power, step="post", alpha=0.2, color="orange")
                ax2.set_ylim([minpower-0.1*(maxpower-minpower), maxpower+0.1*(maxpower-minpower)])

                # axes for scatter plots in front of previous       
                ax3 = ax.twinx()
                ax3.get_yaxis().set_visible(False)
                ax3.scatter(time, freq, facecolor='white', edgecolor='blue', marker="o", alpha=1)
                ax3.set_ylim([minfreq-0.1*(maxfreq-minfreq), maxfreq+0.1*(maxfreq-minfreq)])
                ax4 = ax.twinx()
                ax4.get_yaxis().set_visible(False)
                ax4.scatter(time, power, facecolor='white', edgecolor='orange', marker="o", alpha=1)
                ax4.set_ylim([minpower-0.1*(maxpower-minpower), maxpower+0.1*(maxpower-minpower)])
        
                if savefig:
                    fig.savefig('plot.jpg', format='jpeg', dpi=300)
            if savefig and not showfig:
                print("The image was not created, please enable showfig parameter")

    else:
        print("ERROR: the file is wrong. Please retry with another one.")
    return duration, freq, power


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

















