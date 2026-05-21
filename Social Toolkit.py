from customtkinter import filedialog
import customtkinter as ctk
import subprocess
import threading
import requests
import zipfile
import shutil
import json
import sys
import os

# Interal Files (.exe)
def get_asset_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# External Files
if getattr(sys, 'frozen', False):
    # Running as compiled .exe -> Look at the folder containing the .exe
    EXE_DIR = os.path.dirname(sys.executable)
else:
    # Running in development (VS Code) -> Look at current script folder
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

app_name = "Social Toolkit"
configBase = os.path.join(os.path.expanduser("~"), "AppData", "Local", app_name)
configFile = os.path.join(configBase, "config.json")

socialWorld_TempZip = os.path.join(EXE_DIR, "Templates", "SocialVR World.zip")
socialSDK_UnityPackage = os.path.join(EXE_DIR, "Data", "SocialSDK-v1.4.unitypackage")


socialSDK_Url = "https://github.com/ChristianHiland/Social-Toolkit/raw/refs/heads/master/Data/SocialSDK-v1.4.unitypackage"
worldTemplate_Url = "https://github.com/ChristianHiland/Social-Toolkit/raw/refs/heads/master/Templates/SocialVR%20World.zip"
versionsFile_online = "https://raw.githubusercontent.com/ChristianHiland/Social-Toolkit/refs/heads/master/Data/Versions.json"
versions_file = os.path.join(EXE_DIR, "Data", "Versions.json")


def copy_and_unpack_zip(source_zip: str, target_folder: str):
    if not os.path.exists(source_zip):
        print(f"Error: Source zip file not found at {source_zip}")
        return False

    # 2. Make sure the target directory exists
    os.makedirs(target_folder, exist_ok=True)

    # Get the file name from the source path (e.g., "Template.zip")
    zip_name = os.path.basename(source_zip)
    # Define the destination path for the copy
    destination_zip_path = os.path.join(target_folder, zip_name)

    try:
        print(f"Copying {zip_name} to target folder...")
        shutil.copy2(source_zip, destination_zip_path)

        print(f"Extracting {zip_name}...")
        with zipfile.ZipFile(destination_zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_folder)

        os.remove(destination_zip_path)
        return True
    except Exception as e:
        print(f"An error occurred during processing: {e}")
        return False

def downloadFile(url: str, target: str) -> bool:
    try:
        with requests.get(url, stream=True) as response:
            response.raise_for_status()

            with open(target, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"Download Failed: {e}")
        return False

# Project Element
class ProjectCardFrame(ctk.CTkFrame):
    """A reusable sub-frame that represents an individual project row/card."""

    def __init__(self, master, project_name, project_path, open_callback):
        super().__init__(master, fg_color="#2B2B2B", corner_radius=8)

        # Configure internal card columns
        self.columnconfigure(0, weight=1)  # Project text fills space
        self.columnconfigure(1, weight=0)  # Button stays tight on the right

        # Project Title & Path Info
        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        name_label = ctk.CTkLabel(text_frame, text=project_name, font=("Arial", 14, "bold"))
        name_label.pack(anchor="w")

        path_label = ctk.CTkLabel(text_frame, text=project_path, font=("Arial", 11), text_color="gray")
        path_label.pack(anchor="w")

        # Action Button (Open in Unity / Configure)
        # We pass the specific project path back to the callback function
        open_btn = ctk.CTkButton(
            self,
            text="Open Project",
            width=100,
            command=lambda: open_callback(project_path)
        )
        open_btn.grid(row=0, column=1, padx=15, pady=10, sticky="e")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Social Toolkit")
        self.geometry("1000x600")

        self.titleText = ctk.CTkLabel(self, text="SocialVR Toolkit", font=("Arial", 30))
        self.titleText.pack(pady=10)

        # Loading config
        self.user_config = {}
        self.check_first_time_setup()

        self.start_async_update()

    def check_first_time_setup(self):
        if os.path.exists(configFile):
            try:
                with open(configFile, "r") as f:
                    self.user_config = json.load(f)
                self.initialize_main_interface()
            except Exception as e:
                print(f"Error loading config, restarting setup: {e}")
                self.initialize_setup_interface()
        else:
            self.initialize_setup_interface()

    def initialize_main_interface(self):
        # Project Creation Frame

        self.actionFrame = ctk.CTkFrame(self)
        self.actionFrame.pack(pady=10, padx=40)
        self.actionFrame.columnconfigure(0, weight=1)

        self.projectNameInput = ctk.CTkTextbox(self.actionFrame, height=25, activate_scrollbars=False)
        self.projectNameInput.grid(row=0, column=0, padx=8, pady=15, sticky="e")
        self.projectNameInput.insert("0.0", "Project Name\n")

        self.projectTypeOption = ctk.StringVar(value="World")
        self.projectType = ctk.CTkOptionMenu(self.actionFrame, values=["World", "Avatar"],
                                             variable=self.projectTypeOption)
        self.projectType.grid(row=0, column=1, padx=15, pady=15, sticky="e")

        self.createProjectBtn = ctk.CTkButton(self.actionFrame, text="Create", command=self.start_async_process)
        self.createProjectBtn.grid(row=0, column=2, padx=10, sticky="e")

        # Projects

        self.statusText = ctk.CTkLabel(self, text="", font=("Arial", 25))
        self.statusText.pack(pady=1)

        # Projects List

        self.projectsFrame = ctk.CTkFrame(self, width=800, height=500)
        self.projectsFrame.grid_propagate(False)
        self.projectsFrame.pack(expand=True, pady=(0, 5))

        self.projectsFrame.columnconfigure(0, weight=1)
        self.projectsFrame.columnconfigure(1, weight=0)
        self.projectsFrame.rowconfigure(1, weight=1)

        # 1. Header Row
        self.header_label = ctk.CTkLabel(self.projectsFrame, text="Your SocialVR Projects", font=("Arial", 20, "bold"))
        self.header_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Refresh Button
        self.refresh_btn = ctk.CTkButton(self.projectsFrame, text="Refresh List", width=100, command=self.load_projects)
        self.refresh_btn.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="e")

        # 2. Main Scrollable Container for Project Cards
        self.scroll_container = ctk.CTkScrollableFrame(self.projectsFrame, label_text="")
        self.scroll_container.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        self.project_cards = []

        self.load_projects()

    #
    # Project Functions
    #

    def load_projects(self):
        for card in self.project_cards:
            card.destroy()
        self.project_cards.clear()

        current_projects = os.listdir(self.user_config["project_path"])

        for folder_name in current_projects:
            full_project_path = os.path.join(self.user_config["project_path"], folder_name)

            if os.path.isdir(full_project_path):
                card = ProjectCardFrame(
                    master=self.scroll_container,
                    project_name=folder_name,
                    project_path=full_project_path,  # The full built path
                    open_callback=self.open_selected_project
                )
                card.pack(fill="x", padx=10, pady=5)
                self.project_cards.append(card)

    def open_selected_project(self, target_path):
        unity_exe = self.user_config.get("unity_path")

        if not unity_exe or not os.path.exists(unity_exe):
            print("Error: Unity Editor path is missing or invalid. Check your config.")
            return

        print(f"Detaching process and launching Unity for: {target_path}")

        cmd = [ unity_exe, "-projectPath", target_path ]

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS
            )
            self.update_status(f"Opening '{os.path.basename(target_path)}' in Unity...", "green")
        except Exception as e:
            print(f"Failed to launch Unity: {e}")
            self.update_status("Failed to launch Unity Editor.", "red")

    #
    # First Time setup
    #

    def initialize_setup_interface(self):
        """Builds the first-time installation configuration screen."""
        self.setup_frame = ctk.CTkFrame(master=self)
        self.setup_frame.pack(pady=30, padx=30, fill="both", expand=True)

        title = ctk.CTkLabel(master=self.setup_frame, text="First-Time Setup Wizard", font=("Arial", 20, "bold"))
        title.pack(pady=15)

        desc = ctk.CTkLabel(master=self.setup_frame, text="Please specify your local paths to get started.",
                            font=("Arial", 12))
        desc.pack(pady=5)

        # Unity Editor Path Row
        self.unity_path_var = ctk.StringVar(value="Not Selected")
        unity_label = ctk.CTkLabel(master=self.setup_frame, text="Unity Editor Executable (Unity.exe):",
                                   font=("Arial", 12, "bold"))
        unity_label.pack(anchor="w", padx=20, pady=(10, 0))

        unity_btn = ctk.CTkButton(master=self.setup_frame, text="Browse File", command=self.browse_unity_exe)
        unity_btn.pack(side="top", anchor="w", padx=20, pady=5)

        self.unity_display = ctk.CTkLabel(master=self.setup_frame, textvariable=self.unity_path_var, text_color="gray")
        self.unity_display.pack(anchor="w", padx=20)

        # Unity Editor Path Row
        self.project_path_var = ctk.StringVar(value="Not Selected")
        project_label = ctk.CTkLabel(master=self.setup_frame, text="Project Folder",
                                   font=("Arial", 12, "bold"))
        project_label.pack(anchor="w", padx=20, pady=(10, 0))

        project_btn = ctk.CTkButton(master=self.setup_frame, text="Browse Folder", command=self.browse_project_path)
        project_btn.pack(side="top", anchor="w", padx=20, pady=5)

        self.project_display = ctk.CTkLabel(master=self.setup_frame, textvariable=self.project_path_var, text_color="gray")
        self.project_display.pack(anchor="w", padx=20)

        # Save & Finish Button
        self.save_btn = ctk.CTkButton(master=self.setup_frame, text="Save and Launch", state="disabled",
                                      command=self.save_configuration)
        self.save_btn.pack(side="bottom", pady=20)

    def browse_unity_exe(self):
        """Opens native file explorer to locate Unity.exe."""
        file_path = filedialog.askopenfilename(
            title="Select Unity.exe",
            filetypes=[("Executable Files", "*.exe")]
        )
        if file_path:
            self.unity_path_var.set(file_path)
            self.user_config["unity_path"] = file_path
            # Enable the save button once the required path is populated
            self.save_btn.configure(state="normal")

    def browse_project_path(self):
        """Opens native file explorer to locate Unity.exe."""
        file_path = filedialog.askdirectory(title="Select Project Path")
        if file_path:
            self.project_path_var.set(file_path)
            self.user_config["project_path"] = file_path
            # Enable the save button once the required path is populated
            self.save_btn.configure(state="normal")

    def save_configuration(self):
        """Creates directories and dumps path variables safely to JSON."""
        try:
            # Ensure folder tree structure exists
            os.makedirs(configBase, exist_ok=True)

            with open(configFile, "w") as f:
                json.dump(self.user_config, f, indent=4)

            # Tear down setup screen and move forward
            self.setup_frame.pack_forget()
            self.initialize_main_interface()
        except Exception as e:
            print(f"Failed to save configuration settings: {e}")

    #
    # Threading for Unity project setup
    #


    def update_status(self, text, color="white"):
        """Safely update the UI status text from the main thread loop."""
        self.statusText.configure(text=text, text_color=color)

    def start_async_process(self):
        # Disable the button so the user doesn't accidentally click it twice
        self.createProjectBtn.configure(state="disabled")
        self.update_status("Starting background process...", "yellow")

        # Spin up the background worker thread
        # daemon=True ensures the thread dies automatically if the user closes the GUI app
        worker_thread = threading.Thread(target=self.background_worker, daemon=True)
        worker_thread.start()

    def start_async_update(self):
        # Disable the button so the user doesn't accidentally click it twice
        self.createProjectBtn.configure(state="disabled")
        self.update_status("Checking for updates", "yellow")

        # Spin up the background worker thread
        # daemon=True ensures the thread dies automatically if the user closes the GUI app
        worker_thread = threading.Thread(target=self.checkVersionsApply, daemon=True)
        worker_thread.start()

    def background_worker(self):
        # Step 1
        self.after(0, self.update_status, "Step 1/2: Extracting template...", "yellow")

        copy_and_unpack_zip(socialWorld_TempZip, self.user_config["project_path"] + f"/{self.projectNameInput.get("1.0", "end-1c")}")

        # Step 2
        self.after(0, self.update_status, "Step 2/2: Importing Unity Package (Headless)...", "yellow")

        cmd = [
            self.user_config["unity_path"],
            "-batchmode",
            "-nographics",
            "-projectPath", self.user_config["project_path"] + f"/{self.projectNameInput.get("1.0", "end-1c")}",
            "-importPackage", socialSDK_UnityPackage,
            "-quit"
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.after(0, self.on_process_complete, True)
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")

    def on_process_complete(self, success):
        """Runs back on the main thread once the background worker finishes."""
        self.createProjectBtn.configure(state="normal")
        if success:
            self.update_status("Success!", "green")
        else:
            self.update_status("Error occurred...", "red")

    def checkVersionsApply(self):
        try:
            response = requests.get(versionsFile_online)
            response.encoding = 'utf-8-sig'

            response.raise_for_status()

            # 4. Access the plain text content
            onlineVersionData = response.json()
            print(onlineVersionData)

            localVersionData = {}
            with open(versions_file, "r") as f:
                localVersionData = json.load(f)

            updated = False

            if onlineVersionData["SDK"] != localVersionData["SDK"]:
                self.after(0, self.update_status, "Updating SocialSDK Unitypackage", "yellow")
                downloadFile(socialSDK_Url, socialSDK_UnityPackage)
                localVersionData["SDK"] = onlineVersionData["SDK"]
                updated = True

            if onlineVersionData["World Template"] != localVersionData["World Template"]:
                self.after(0, self.update_status, "Updating Social World Template", "yellow")
                downloadFile(worldTemplate_Url, socialWorld_TempZip)
                localVersionData["World Template"] = onlineVersionData["World Template"]
                updated = True

            if updated:
                with open(versions_file, "w") as f:
                    json.dump(localVersionData, f, indent=4)

            self.after(0, self.on_process_complete, True)
        except requests.exceptions.HTTPError as err:
            print(f"HTTP error occurred: {err}")
            self.after(0, self.on_process_complete, False)
        except Exception as err:
            print(f"An error occurred: {err}")
            self.after(0, self.on_process_complete, False)

app = App()
app.mainloop()