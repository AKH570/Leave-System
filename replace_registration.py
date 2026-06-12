import shutil
import os

src = r'e:\Project-django\LeaveSystem\LeaveManagementSystem\templates\authentication\registration_new.html'
dst = r'e:\Project-django\LeaveSystem\LeaveManagementSystem\templates\authentication\registration.html'

if os.path.exists(src):
    shutil.copy2(src, dst)
    print(f"Successfully copied {src} to {dst}")
    os.remove(src)
    print(f"Removed {src}")
else:
    print(f"Source file not found: {src}")
