import tkinter as tk
from tksheet import Sheet

class MSDOS_Spreadsheet(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # 1. DOS-like Terminal Window Setup
        self.title("MS-DOS Spreadsheet 1.0")
        self.geometry("800x600")
        self.configure(bg="#000080")  # Dark Blue background
        
        # 2. Add retro menu bar
        menubar = tk.Menu(self, bg="#c0c0c0", fg="#000000", relief="flat")
        file_menu = tk.Menu(menubar, tearoff=0, bg="#c0c0c0", fg="#000000")
        file_menu.add_command(label="New")
        file_menu.add_command(label="Open")
        file_menu.add_command(label="Save")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

        # 3. Create the Spreadsheet Canvas
        self.frame = tk.Frame(self, bg="#000080")
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 4. Initialize the Tksheet
        self.sheet = Sheet(self.frame, header_font=("Courier", 10, "bold"), font=("Courier", 10))
        self.sheet.pack(fill="both", expand=True)
        
        # Retro Theme modifications for tksheet
        self.sheet.set_table_background_color("#000000")
        self.sheet.set_grid_color("#00ff00")      # Bright Green grid lines
        self.sheet.set_text_color("#00ff00")        # Bright Green text
        
        self.sheet.enable_bindings(("single", "drag_select", "arrowkeys", "edit_cell"))

if __name__ == "__main__":
    app = MSDOS_Spreadsheet()
    app.mainloop()

