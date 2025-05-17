import subprocess
import re
import psutil
import pyamdgpuinfo

try:
    device_count = pyamdgpuinfo.detect_gpus()
    if device_count > 0:
        gpu = pyamdgpuinfo.get_gpu(0)
except:
    gpu = None

def get_cpu_temp():
    """Attempt to get CPU temperature using various methods."""
    # Try psutil first (best cross-platform option)
    try:
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            if temps:
                # Check common temperature sources
                for key in ['coretemp', 'cpu_thermal', 'k10temp', 'acpitz']:
                    if key in temps and temps[key]:
                        return temps[key][0].current
    except:
        pass
    
    # Try platform-specific methods
    import platform
    system = platform.system()
    
    if system == 'Linux':
        # Read from thermal zone
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read().strip()) / 1000.0
        except:
            pass
        
        # Try vcgencmd (for Raspberry Pi)
        try:
            output = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
            return float(re.search(r'temp=(\d+\.\d+)', output).group(1))
        except:
            pass
    
    elif system == 'Windows':
        # Try WinTmp
        try:
            import WinTmp
            return WinTmp.CPU_Temp()
        except:
            pass
        
        # Try WMI
        try:
            import wmi
            w = wmi.WMI(namespace="root\\wmi")
            temperature_info = w.MSAcpi_ThermalZoneTemperature()[0]
            return (temperature_info.CurrentTemperature / 10.0) - 273.15
        except:
            pass
    
    
    print(f"Warning: Could not retrieve CPU temp.")
    return 0

def get_gpu_temp():
    """Attempt to get GPU temperature using various methods."""
    # Try NVIDIA GPU first
    try:
        # Try using pynvml library
        try:
            from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, \
                              nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU, nvmlShutdown
            
            nvmlInit()
            device_count = nvmlDeviceGetCount()
            
            if device_count > 0:
                handle = nvmlDeviceGetHandleByIndex(0)
                temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                nvmlShutdown()
                return temp
            
            nvmlShutdown()
        except:
            # Try using nvidia-smi command
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader']).decode()
            return float(output.strip().split('\n')[0])
    except:
        pass
    
    # Try AMD GPU
    try:
        return gpu.query_temperature()
    except:
        pass
    
    # Try Windows-specific methods
    import platform
    if platform.system() == 'Windows':
        try:
            import WinTmp
            return WinTmp.GPU_Temp()
        except:
            pass
    
    print(f"Warning: Could not retrieve GPU temp.")
    return 0

def get_cpu_usage():
    """Get CPU usage percentage."""
    try:
        return psutil.cpu_percent(interval=None)
    except:
        print("Warning: Could not retrieve CPU usage.")
        return 0

def get_gpu_usage():
     # GPU usage implementation
    try:
        if gpu is None:
            try:
                # NVIDIA GPUs using pynvml
                from pynvml import (nvmlInit, nvmlShutdown,
                                nvmlDeviceGetHandleByIndex,
                                nvmlDeviceGetUtilizationRates)
                nvmlInit()
                try:
                    handle = nvmlDeviceGetHandleByIndex(0)
                    utilization = nvmlDeviceGetUtilizationRates(handle)
                    return int(utilization.gpu)
                finally:
                    nvmlShutdown()
            except:
                output = subprocess.check_output(
                    ['nvidia-smi', '--query-gpu=utilization.gpu',
                        '--format=csv,noheader']
                ).decode().strip()
                return int(output.split()[0])
        else: 
            return int(gpu.query_load()*100)
    except:
        print("Could not retrieve gpu usage.")
        return 0

def get_system_metrics():
    """
    Retrieve comprehensive system metrics including CPU/GPU temperatures and usage percentages.
    
    Returns:
        dict: Dictionary containing:
            - cpu_temp: CPU temperature in Celsius (float or None)
            - gpu_temp: GPU temperature in Celsius (float or None)
            - cpu_usage: CPU utilization percentage (float)
            - gpu_usage: GPU utilization percentage (float or None)
    """
    metrics = {
        'cpu_temp': int(get_cpu_temp()),
        'gpu_temp': int(get_gpu_temp()),
        'cpu_usage': int(get_cpu_usage()),
        'gpu_usage': int(get_gpu_usage())
    }

   

    return metrics


