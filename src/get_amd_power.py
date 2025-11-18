import time
import os

class CPUPower:
    def __init__(self):
        base_path = "/sys/class/powercap"
        core_paths = []
        for entry in os.listdir(base_path):
            if entry.startswith("intel-rapl") or entry.startswith("amd-rapl"):  # Cover AMD and Intel naming
                root = os.path.join(base_path, entry)
                # Look for energy_uj files for all subdomains (each core or domain)
                for sub in os.listdir(root):
                    energy_path = os.path.join(root, sub, "energy_uj")
                    if os.path.isfile(energy_path):
                        core_paths.append(energy_path)
        self.core_energy_path = core_paths[0]
        self.prev_energy = self.read_energy_uj()

    def read_energy_uj(self):
        try:
            with open(self.core_energy_path, 'r') as f:
                return int(f.read().strip())
        except Exception as e:
            return None

    def compute_power_all_cores(self, interval=1):
        curr_energy = self.read_energy_uj()
        delta = curr_energy - self.prev_energy
        if delta < 0:
            delta += 2**32  # handle counter wrap
        power = (delta / 1_000_000) / interval  # in watts
        self.prev_energy = curr_energy
        return power
