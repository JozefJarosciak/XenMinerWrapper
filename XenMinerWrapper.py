import os
import re
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
import requests
import psutil
import tkinter as tk
from tkinter import messagebox, ttk

# Constants
DEFAULT_MINER_LOCATION = 'https://github.com/jacklevin74/xenminer/blob/main/miner.py'
ETH_ADDRESS_PATTERN = re.compile(r'^0x[0-9a-fA-F]{40}$')
HASH_PER_SECOND_PATTERN = re.compile(r',\s*([\d.]+)')
DIFFICULTY_PATTERN = re.compile(r"Updating difficulty to (\d+)")


class MinerApp(tk.Tk):
    def __init__(self):

        super().__init__()

        # Initialize variables
        self.miner_hash_rates = {}
        self.valid_hash_count = 0
        self.lock = threading.Lock()
        self.current_difficulty = 0  # Initialize to a default value


        # GUI setup
        self.title("XEN.pub's XenMiner Wrapper")
        self.geometry("800x600")
        self.setup_ui()
        self.running_processes = []
        self.update_total_hash_rate()

    def setup_ui(self):
        # Footer Frame
        self.footer_frame = self.create_footer_frame()

        # Create links in the footer
        self.create_links_in_footer()

        # XenMiner location label and textbox
        self.miner_location = self.create_label_and_entry("XenMiner GitHub Location", 0, DEFAULT_MINER_LOCATION)

        # Ethereum address label and textbox
        self.eth_address = self.create_label_and_entry("Your Ethereum Address", 1, self.load_eth_address())

        # Python environment label and textbox
        self.python_env = self.create_label_and_entry("Python Environment Location", 2, self.load_python_env())

        # Combobox for parallel execution
        self.create_label_and_combobox("Parallel Executions (one per core)", 3)

        # Frame for the buttons
        self.button_frame = tk.Frame(self)
        self.button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        # Run script button inside the frame
        self.run_btn = tk.Button(self.button_frame, text="Run", command=self.run_script)
        self.run_btn.grid(row=4, column=0, padx=5)

        # Stop script button inside the frame
        self.stop_btn = tk.Button(self.button_frame, text="Stop", command=self.stop_script, state=tk.DISABLED)
        self.stop_btn.grid(row=4, column=1, padx=5)

        # Tabs for parallel executions
        self.tab_control = ttk.Notebook(self)
        self.tab_control.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        self.grid_rowconfigure(6, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.footer_frame.grid(row=7, column=0, columnspan=2)

    def create_label_and_entry(self, label_text, row, default_value=""):
        tk.Label(self, text=label_text).grid(row=row, column=0, padx=10, pady=10, sticky="e")
        entry = tk.Entry(self, width=70)
        entry.grid(row=row, column=1, padx=10, pady=10, sticky="w")
        entry.insert(0, default_value)
        return entry

    def create_label_and_combobox(self, label_text, row):
        tk.Label(self, text=label_text).grid(row=row, column=0, padx=10, pady=10, sticky="e")
        max_parallel = psutil.cpu_count(logical=False)
        values = [str(i) for i in range(1, max_parallel + 1)]
        self.num_parallel = ttk.Combobox(self, values=values)
        self.num_parallel.set("1")
        self.num_parallel.grid(row=row, column=1, padx=10, pady=10, sticky="w")


    def run_script(self):
        # Disable the Run button and Enable the Stop button
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        eth_address = self.eth_address.get().strip()
        miner_location = self.miner_location.get().strip().replace("github.com", "raw.githubusercontent.com").replace("/blob", "")
        python_env = self.python_env.get().strip()

        self.save_eth_address()
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
        with self.lock:
            self.running_processes.append(process)

        try:
            miner_script = requests.get(miner_location).text
        except:
            messagebox.showerror("Error", "Failed to fetch the miner script!")
            return

        # Update the Ethereum address in the script
        miner_script = re.sub(r'account = "0x[0-9a-fA-F]{40}"', f'account = "{eth_address}"', miner_script)

        with open("miner.py", "w") as f:
            f.write(miner_script)

        for tab in self.tab_control.tabs():
            self.tab_control.forget(tab)

        self.add_new_tab(miner_script, eth_address)

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
            self.run_miner_script(output_display, i)

    def run_miner_script(self, output_widget, miner_number):
        python_env = self.python_env.get().strip()
        def get_hash_per_second(line):
            # Using regex to find the first number after the first comma.
            match = re.search(r',\s*([\d.]+)', line)

            if match:
                # Return the extracted number as a float.
                return float(match.group(1))
            else:
                # Return None if no match is found.
                return None
        def extract_difficulty(line):
            match = re.search(r"Updating difficulty to (\d+)", line)
            if match:
                return int(match.group(1))
            return None


        def run():
            last_hash_per_second = None
            process = subprocess.Popen(
                [python_env, 'miner.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            with self.lock:
                self.running_processes.append(process)

            while True:
                line = process.stdout.readline()
                if not line:
                    break
                # Append the line to the Text widget if Parse Output is checked
                if "valid hash" in line:
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.last_found_block_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"Detected a valid hash (mined a new block) at {current_time}!")

                    with self.lock:
                        self.valid_hash_count += 1
                    continue
                hash_per_second = get_hash_per_second(line)
                if hash_per_second:
                    self.miner_hash_rates[miner_number] = hash_per_second
                    output_widget.insert(tk.END, f"Hash Rate: {hash_per_second}\n")
                    output_widget.yview(tk.END)  # Auto-scroll to the bottom
                else:
                    output_widget.insert(tk.END, line)
                    output_widget.yview(tk.END)  # Auto-scroll to the bottom


                difficulty_update = extract_difficulty(line)
                if difficulty_update is not None:
                    self.current_difficulty = difficulty_update

            process.wait()

        threading.Thread(target=run, daemon=True).start()

    def reset_footer_labels(self):
        self.footer_blocks_var.set("Found Blocks: --")
        self.footer_hash_rate_var.set("Total Hash/s: --")
        self.footer_latest_found_var.set("Latest Block (time): --")
        self.footer_difficulty_var.set("Current Difficulty: --")


    def update_total_hash_rate(self):
        self.footer_blocks_var.set(f"Found Blocks: {self.valid_hash_count:,}")
        total_hash_rate = sum(self.miner_hash_rates.values())
        self.footer_hash_rate_var.set(f"Total Hash/s: {total_hash_rate:,.2f}")

        # Assuming self.last_found_block_time holds the time of the latest found block
        if hasattr(self, 'last_found_block_time'):
            self.footer_latest_found_var.set(f"Latest Found: {self.last_found_block_time}")

        if isinstance(self.current_difficulty, (int, float)):
            self.footer_difficulty_var.set(f"Current Difficulty: {self.current_difficulty:,}")
        else:
            self.footer_difficulty_var.set(f"Current Difficulty: {self.current_difficulty}")

        self.after(1000, self.update_total_hash_rate)  # Schedule this method to run every 0.5 seconds


    def open_webpage(self, url):
        webbrowser.open(url)

    def load_python_env(self):
        if os.path.exists('python_env.txt'):
            with open('python_env.txt', 'r') as f:
                return f.read().strip()

    def save_python_env(self):
        with open('python_env.txt', 'w') as f:
            f.write(self.python_env.get())

    def load_eth_address(self):
        if os.path.exists('eth_address.txt'):
            with open('eth_address.txt', 'r') as f:
                return f.read().strip()

    def save_eth_address(self):
        with open('eth_address.txt', 'w') as f:
            f.write(self.eth_address.get())

    def validate_ethereum_address(self, address):
        return ETH_ADDRESS_PATTERN.match(address)

    def add_new_tab(self, content, eth_address):
        tab = ttk.Frame(self.tab_control)
        self.tab_control.add(tab, text="MINER SCRIPT", sticky="nsew")

        download_time = datetime.now().strftime("%a %b %d %Y at %I:%M:%S %p")
        download_info = f"Last download: {download_time}\nOriginal Github Ethereum address has been replaced by your own: {eth_address}\n\n"

        v_scroll = tk.Scrollbar(tab, orient="vertical")
        v_scroll.grid(row=0, column=1, sticky="ns")

        script_display = tk.Text(tab, wrap=tk.WORD, yscrollcommand=v_scroll.set, font=("Arial", 10))
        script_display.tag_configure("download_info", foreground="blue", font=("Arial", 10, "bold"))
        script_display.insert(tk.END, download_info, "download_info")  # Apply the "download_info" tag to this content
        script_display.insert(tk.END, content)
        script_display.grid(row=0, column=0, sticky="nsew")

        v_scroll.config(command=script_display.yview)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.tab_control.select(tab)
    def stop_script(self):
        with self.lock:
            for process in self.running_processes:
                try:
                    process.terminate()
                except Exception as e:
                    print(f"Error stopping process: {e}")
            self.running_processes.clear()

        for tab in self.tab_control.tabs():
            self.tab_control.forget(tab)
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.current_difficulty = 0
        time.sleep(1)
        self.reset_footer_labels()
        self.update_idletasks()  # Force the GUI to update immediately


    def on_closing(self):
        self.reset_footer_labels()
        self.stop_script()
        self.destroy()

    def create_footer_frame(self):
        footer_frame = ttk.Frame(self)
        # Define StringVars for dynamic values
        self.footer_blocks_var = tk.StringVar(value="Found Blocks: --")
        self.footer_hash_rate_var = tk.StringVar(value="Total Hash/s: --")
        self.footer_latest_found_var = tk.StringVar(value="Latest Block (time): 0")
        self.footer_difficulty_var = tk.StringVar(value=f"Current Difficulty: {self.current_difficulty}")

        # Create labels using the StringVars
        footer_blocks_label = ttk.Label(footer_frame, textvariable=self.footer_blocks_var)
        footer_hash_rate_label = ttk.Label(footer_frame, textvariable=self.footer_hash_rate_var)
        footer_latest_found_label = ttk.Label(footer_frame, textvariable=self.footer_latest_found_var)
        footer_difficulty_label = ttk.Label(footer_frame, textvariable=self.footer_difficulty_var)

        # Position the labels in a grid layout
        footer_difficulty_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        footer_hash_rate_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        footer_blocks_label.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        footer_latest_found_label.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        return footer_frame

    def create_links_in_footer(self):
        """
        Create links in the footer frame.
        """
        links_label = tk.Label(self.footer_frame, text="Links:")
        links_label.grid(row=1, column=0)

        link1 = tk.Label(self.footer_frame, text="XenMiner", fg="blue", cursor="hand2")
        link1.bind("<Button-1>", lambda e: self.open_webpage("https://github.com/jacklevin74/xenminer"))
        link1.grid(row=1, column=1)

        link2 = tk.Label(self.footer_frame, text="XenMinerWrapper", fg="blue", cursor="hand2")
        link2.bind("<Button-1>", lambda e: self.open_webpage("https://github.com/JozefJarosciak/XenMinerWrapper/"))
        link2.grid(row=1, column=2)

        link3 = tk.Label(self.footer_frame, text="Xen.pub", fg="blue", cursor="hand2")
        link3.bind("<Button-1>", lambda e: self.open_webpage("https://xen.pub"))
        link3.grid(row=1, column=3)


if __name__ == "__main__":
    app = MinerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

