import threading
import tkinter as tk
from tkinter import ttk, messagebox
import requests
import os
import re
import subprocess
from datetime import datetime
import psutil
import webbrowser

class MinerApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("XEN.pub's XenMiner Wrapper")
        self.geometry("800x600")

        # Footer Frame
        self.footer_frame = self.create_footer_frame()

        # Create links in the footer
        self.create_links_in_footer()

        # XenMiner location label and textbox
        tk.Label(self, text="XenMiner GitHub Location").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.miner_location = tk.Entry(self, width=70)
        self.miner_location.insert(0, "https://github.com/jacklevin74/xenminer/blob/main/miner.py")
        self.miner_location.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Ethereum address label and textbox
        tk.Label(self, text="Your Ethereum Address").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.eth_address = tk.Entry(self, width=70)
        self.eth_address.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        # Python environment label and textbox
        tk.Label(self, text="Python Environment Location").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.python_env = tk.Entry(self, width=70)
        self.python_env.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        # Load saved python environment path
        self.load_python_env()
        # Load saved ethereum address
        self.load_eth_address()

        # Combobox for parallel execution
        tk.Label(self, text="Parallel Executions (one per core)").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        max_parallel = psutil.cpu_count(logical=False)  # get the number of physical cores
        self.num_parallel = ttk.Combobox(self, values=[str(i) for i in range(1, max_parallel+1)])
        self.num_parallel.set("1")
        self.num_parallel.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        # Frame for the buttons
        self.button_frame = tk.Frame(self)
        self.button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        # Run script button inside the frame
        self.run_btn = tk.Button(self.button_frame, text="Run", command=self.run_script)
        self.run_btn.grid(row=0, column=0, padx=5)

        # Stop script button inside the frame
        self.stop_btn = tk.Button(self.button_frame, text="Stop", command=self.stop_script, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5)

        # Tabs for parallel executions
        self.tab_control = ttk.Notebook(self)
        self.tab_control.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        self.grid_rowconfigure(5, weight=1)  # Make sure the notebook expands vertically
        self.grid_columnconfigure(1, weight=1)  # Make sure the notebook expands horizontally



        # List to store running processes
        self.running_processes = []



    def run_script(self):
        # Disable the Run button and Enable the Stop button
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        eth_address = self.eth_address.get().strip()
        miner_location = self.miner_location.get().strip().replace("github.com", "raw.githubusercontent.com").replace("/blob", "")
        python_env = self.python_env.get().strip()

        # Save ethereum address
        self.save_eth_address()
        # Save python environment path
        self.save_python_env()

        if not python_env:
            messagebox.showerror("Error", "Please specify the path to Python Environment! (e.g. C:\python\python.exe)")
            return

        # Check if the Ethereum address and XenMiner location are provided
        if not self.validate_ethereum_address(eth_address):
            messagebox.showerror("Error", "Invalid Ethereum Address!")
            return

        if not miner_location:
            messagebox.showerror("Error", "XenMiner Location cannot be empty!")
            return

        process = subprocess.Popen([python_env, 'miner.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # Add the new process to the list of running processes
        self.running_processes.append(process)

        # Download miner.py from the given location
        try:
            miner_script = requests.get(miner_location).text
        except:
            messagebox.showerror("Error", "Failed to fetch the miner script!")
            return

        # Update the Ethereum address in the script
        miner_script = re.sub(r'account = "0x[0-9a-fA-F]{40}"', f'account = "{eth_address}"', miner_script)

        # Save the updated script locally
        with open("miner.py", "w") as f:
            f.write(miner_script)

        # Clear existing tabs
        for tab in self.tab_control.tabs():
            self.tab_control.forget(tab)

        # Display the script in a new tab
        self.add_new_tab(miner_script, eth_address)

        # Create new tabs for parallel executions
        for i in range(int(self.num_parallel.get())):
            tab = ttk.Frame(self.tab_control)
            self.tab_control.add(tab, text=f"Miner #{i+1}")

            # Vertical Scrollbar for the output
            v_scroll = tk.Scrollbar(tab, orient="vertical")
            v_scroll.grid(row=0, column=1, sticky="ns")

            output_display = tk.Text(tab, wrap=tk.WORD, yscrollcommand=v_scroll.set)
            output_display.grid(row=0, column=0, sticky="nsew")

            v_scroll.config(command=output_display.yview)
            # Grid configuration
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

            # Start the script for this tab
            self.run_miner_script(output_display)


    def run_miner_script(self, output_widget):
        python_env = self.python_env.get().strip()
        max_lines = 5000  # set the maximum number of lines
        lines_since_last_trim = 0  # counter for lines added since the last trim
        trim_frequency = 2500  # trim the widget every 50 lines

        def run():
            nonlocal lines_since_last_trim
            process = subprocess.Popen([python_env, 'miner.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            while True:
                line = process.stdout.readline()
                if not line:
                    break
                output_widget.insert(tk.END, line)
                output_widget.yview(tk.END)  # Auto-scroll to the bottom
                lines_since_last_trim += 1

                # Trim the text widget content to last 1000 lines, but do so every 50 lines
                if lines_since_last_trim >= trim_frequency:
                    for _ in range(trim_frequency):
                        if int(output_widget.index(tk.END).split('.')[0]) > max_lines + 1:  # +1 because of the empty last line in Text widget
                            output_widget.delete(1.0, 2.0)  # delete the first line
                    lines_since_last_trim = 0

            process.wait()  # Wait until the process completes

        # Using a thread to avoid blocking the main UI
        threading.Thread(target=run, daemon=True).start()


    def open_webpage(self, url):
        webbrowser.open(url)

    def load_python_env(self):
        if os.path.exists('python_env.txt'):
            with open('python_env.txt', 'r') as f:
                self.python_env.delete(0, tk.END)
                self.python_env.insert(0, f.read())

    def save_python_env(self):
        with open('python_env.txt', 'w') as f:
            f.write(self.python_env.get())

    def load_eth_address(self):
        if os.path.exists('eth_address.txt'):
            with open('eth_address.txt', 'r') as f:
                self.eth_address.delete(0, tk.END)
                self.eth_address.insert(0, f.read())

    def save_eth_address(self):
        with open('eth_address.txt', 'w') as f:
            f.write(self.eth_address.get())

    def validate_ethereum_address(self, address):
        # Ethereum addresses start with '0x' followed by 40 hexadecimal characters
        return re.match(r'^0x[0-9a-fA-F]{40}$', address)

    def add_new_tab(self, content, eth_address):
        tab = ttk.Frame(self.tab_control)
        self.tab_control.add(tab, text="MINER SCRIPT", sticky="nsew")

        # Get the current date and time in the desired format
        download_time = datetime.now().strftime("%a %b %d %Y at %I:%M:%S %p")
        download_info = f"Last download: {download_time}\nOriginal Github Ethereum address has been replaced by your own: {eth_address}\n\n"

        # Vertical Scrollbar
        v_scroll = tk.Scrollbar(tab, orient="vertical")
        v_scroll.grid(row=0, column=1, sticky="ns")

        script_display = tk.Text(tab, wrap=tk.WORD, yscrollcommand=v_scroll.set, font=("Arial", 10))
        script_display.tag_configure("download_info", foreground="blue", font=("Arial", 10, "bold"))
        script_display.insert(tk.END, download_info, "download_info")  # Apply the "download_info" tag to this content
        script_display.insert(tk.END, content)
        script_display.grid(row=0, column=0, sticky="nsew")

        v_scroll.config(command=script_display.yview)

        # Grid configuration
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # Make sure this tab is shown in front of all others
        self.tab_control.select(tab)





    def stop_script(self):
        # Stop all running processes
        for process in self.running_processes:
            try:
                process.terminate()
            except Exception as e:
                print(f"Error stopping process: {e}")

        # Clear the list of running processes
        self.running_processes.clear()

        # Clear existing tabs
        for tab in self.tab_control.tabs():
            self.tab_control.forget(tab)

        # Re-enable the Run button and Disable the Stop button
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def on_closing(self):
        # This function is triggered when the window is closed
        self.stop_script()
        self.destroy()

    def create_footer_frame(self):
        """
        Create and return the footer frame.
        """
        footer_frame = tk.Frame(self)
        footer_frame.grid(row=6, column=0, columnspan=2, pady=10, sticky="ew")
        return footer_frame

    def create_links_in_footer(self):
        """
        Create links in the footer frame.
        """
        links_info = [
            {"text": "XenMiner", "url": "https://github.com/jacklevin74/xenminer"},
            {"text": "XenMinerWrapper", "url": "https://github.com/JozefJarosciak/XenMinerWrapper/"},
            {"text": "Xen.pub", "url": "https://xen.pub"},
            {"text": "X.com (Jack)", "url": "https://twitter.com/mrJackLevin"},
            {"text": "X.com (Jozef)", "url": "https://twitter.com/jarosciak"}
        ]

        # Create a label with the text "Links:" and place it in the footer frame.
        links_label = tk.Label(self.footer_frame, text="Links:")
        links_label.grid(row=0, column=0)  # Adjust the grid placement as needed.

        for index, link in enumerate(links_info):
            # The column for link_label should start from 1 and increment by 2 each time
            link_label = tk.Label(self.footer_frame, text=link["text"], fg="blue", cursor="hand2")
            link_label.bind("<Button-1>", lambda e, url=link["url"]: self.open_webpage(url))
            link_label.grid(row=0, column=index*2 + 1, sticky="w")

            # Add | separator after each link except the last one
            if index < len(links_info) - 1:
                separator_label = tk.Label(self.footer_frame, text="|")
                separator_label.grid(row=0, column=index*2 + 2, padx=(5, 5), sticky="w")

if __name__ == "__main__":
    app = MinerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)  # Add the close event handler
    app.mainloop()
