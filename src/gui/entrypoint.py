"""Entrypoint for the GUI application. Design is old-school MS-DOS style, with a single window and a single frame."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from timecheck import TimeCheck

class TimeCheckGUI:
    """GUI application for TimeCheck."""

    def __init__(self, timecheck: TimeCheck) -> None:
        self.timecheck = timecheck

        # Window configuration
        self.root = tk.Tk()
        self.root.title("TimeCheck")
        self.root.geometry("800x600")
        self.root.configure(bg="black")

        # Text terminal (i.e. the screen)
        self.display = tk.Text(
            self.root, 
            bg="black",
            fg="#00ff00",
            font=("Courier", 12, "bold"),
            insertbackground="white",
            relief=tk.FLAT,
            bd=0, 
            padx=10,
            pady=10
        )
        self.display.pack(expand=True, fill=tk.BOTH)

        # Add retro menu bar
        menubar = tk.Menu(self.root, bg="#c0c0c0", fg="#000000", relief="flat")

        file_menu = tk.Menu(menubar, tearoff=0, bg="#c0c0c0", fg="#000000")
        file_menu.add_command(label="New")
        file_menu.add_command(label="Open")
        file_menu.add_command(label="Save")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

        ## JONAH: add in tabs that click through important spreadsheets for entry. Make main display an entry dashboard.

        # Bind events:
        self.display.bind("<Key>", self.check_key)
        self.display.bind("<Return>", self.execute_command)

        # Init
        self.current_dir = Path(__file__).resolve().parent
        self.draw_prompt()


    def draw_prompt(self):
        self.display.insert(tk.END, f"{self.current_dir}>")
        self.display.see(tk.END)

        self.display.mark_set("input_start", tk.INSERT)

    def check_key(self, event):
        
        # Prevent user from deleting prompt or previous lines
        insert_idx = self.display.index(tk.INSERT)
        prompt_idx = self.display.index("input_start")

        # if backspace into prompt or before:
        if event.keysym == "BackSpace" and self.display.compare(insert_idx, "<=", prompt_idx):
            return "break"
    
    def execute_command(self, event):
        
        # Get input after the prompt
        user_input = self.display.get("input_start", tk.END).strip().lower()
        self.display.insert(tk.END, "\n")        

        # Command process if/else chain
        if user_input == "help":
            self.display.insert(tk.END, "Available commands: DIR, HELP, CLS, VER\n")
        elif user_input == "dir":
            self.display.insert(tk.END, f"Directory is {os.getcwd}")
        elif user_input == "cls":
            self.display.delete("1.0", tk.END)
        elif user_input == "ver":
            self.display.insert(tk.END, "MS-DOS Version 6.22\n")
        elif user_input != "":
            self.display.insert(tk.END, f"Bad command or file name: '{user_input}'\n")

        self.draw_prompt()
        return "break" # Prevent the Return key from adding a newline in the Text widget
        

    def run(self) -> None:
        self.root.mainloop()

if __name__ == "__main__":
    timecheck = TimeCheck(name="Amanda")
    gui = TimeCheckGUI(timecheck)
    gui.run()
