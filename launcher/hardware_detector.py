"""
Hardware Detection Module for PyPottery Suite
Detects OS, CPU, GPU (CUDA/MPS/ROCm), and system resources
"""

import platform
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import shutil


@dataclass
class GPUInfo:
    """Information about a GPU device"""
    index: int
    name: str
    memory_total_mb: int
    memory_free_mb: int
    driver_version: str = ""
    cuda_version: str = ""


@dataclass
class HardwareInfo:
    """Complete hardware information for the system"""
    # OS Info
    os_name: str  # Windows, Darwin, Linux
    os_version: str
    architecture: str  # x86_64, arm64, etc.
    
    # CPU Info
    cpu_name: str
    cpu_cores: int
    cpu_threads: int
    
    # Memory
    ram_total_gb: float
    ram_available_gb: float
    
    # GPU Info
    cuda_available: bool = False
    cuda_version: Optional[str] = None
    cuda_compatible: bool = True  # True unless outdated driver detected
    driver_warning: Optional[str] = None
    cudnn_version: Optional[str] = None
    mps_available: bool = False  # Apple Silicon
    rocm_available: bool = False  # AMD ROCm
    gpus: List[GPUInfo] = field(default_factory=list)
    
    # Recommendations
    recommended_pytorch_variant: str = "cpu"
    pytorch_index_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "os_name": self.os_name,
            "os_version": self.os_version,
            "architecture": self.architecture,
            "cpu_name": self.cpu_name,
            "cpu_cores": self.cpu_cores,
            "cpu_threads": self.cpu_threads,
            "ram_total_gb": self.ram_total_gb,
            "ram_available_gb": self.ram_available_gb,
            "cuda_available": self.cuda_available,
            "cuda_version": self.cuda_version,
            "cuda_compatible": self.cuda_compatible,
            "driver_warning": self.driver_warning,
            "cudnn_version": self.cudnn_version,
            "mps_available": self.mps_available,
            "rocm_available": self.rocm_available,
            "gpus": [{"index": g.index, "name": g.name, 
                      "memory_total_mb": g.memory_total_mb,
                      "memory_free_mb": g.memory_free_mb} for g in self.gpus],
            "recommended_pytorch_variant": self.recommended_pytorch_variant,
            "pytorch_index_url": self.pytorch_index_url
        }


def get_os_info() -> tuple:
    """Get operating system information"""
    os_name = platform.system()  # Windows, Darwin, Linux
    os_version = platform.version()
    architecture = platform.machine()  # x86_64, AMD64, arm64
    
    return os_name, os_version, architecture


def get_cpu_info() -> tuple:
    """Get CPU information"""
    cpu_name = platform.processor() or "Unknown"
    
    # Try to get better CPU name on Windows
    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
            winreg.CloseKey(key)
        except:
            pass
    elif platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_name = line.split(":")[1].strip()
                        break
        except:
            pass
    elif platform.system() == "Darwin":
        try:
            result = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                cpu_name = result.stdout.strip()
        except:
            pass
    
    cpu_cores = os.cpu_count() or 1
    
    # Try to get physical vs logical cores
    try:
        import psutil
        cpu_threads = psutil.cpu_count(logical=True)
        cpu_cores_physical = psutil.cpu_count(logical=False)
    except ImportError:
        cpu_threads = cpu_cores
        cpu_cores_physical = cpu_cores
    
    return cpu_name, cpu_cores_physical, cpu_threads


def get_memory_info() -> tuple:
    """Get RAM information in GB"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        ram_total = mem.total / (1024 ** 3)
        ram_available = mem.available / (1024 ** 3)
    except ImportError:
        # Fallback without psutil
        ram_total = 8.0  # Assume 8GB
        ram_available = 4.0
        
        if platform.system() == "Linux":
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if "MemTotal" in line:
                            ram_total = int(line.split()[1]) / (1024 ** 2)
                        elif "MemAvailable" in line:
                            ram_available = int(line.split()[1]) / (1024 ** 2)
            except:
                pass
    
    return round(ram_total, 2), round(ram_available, 2)


def detect_nvidia_cuda() -> tuple:
    """Detect NVIDIA GPU and CUDA availability"""
    cuda_available = False
    cuda_version = None
    cudnn_version = None
    gpus = []
    
    # Try nvidia-smi first (works without PyTorch)
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            # Get CUDA version from nvidia-smi
            result = subprocess.run(
                [nvidia_smi, "--query-gpu=driver_version,name,memory.total,memory.free", 
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                cuda_available = True
                lines = result.stdout.strip().split("\n")
                for idx, line in enumerate(lines):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        gpus.append(GPUInfo(
                            index=idx,
                            name=parts[1],
                            memory_total_mb=int(float(parts[2])),
                            memory_free_mb=int(float(parts[3])),
                            driver_version=parts[0]
                        ))
            
            # Get CUDA version
            result = subprocess.run([nvidia_smi], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "CUDA Version" in line:
                        # Extract version like "CUDA Version: 12.6"
                        import re
                        match = re.search(r"CUDA Version:\s*(\d+\.\d+)", line)
                        if match:
                            cuda_version = match.group(1)
                        break
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
    
    # Try to get cuDNN version if PyTorch is available
    try:
        import torch
        if torch.cuda.is_available():
            cuda_available = True
            if not cuda_version:
                cuda_version = torch.version.cuda
            cudnn_version = str(torch.backends.cudnn.version()) if torch.backends.cudnn.is_available() else None
            
            # Get GPU info from PyTorch if not already populated
            if not gpus:
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    gpus.append(GPUInfo(
                        index=i,
                        name=props.name,
                        memory_total_mb=props.total_memory // (1024 * 1024),
                        memory_free_mb=0  # Can't get free memory easily without GPUtil
                    ))
    except ImportError:
        pass
    
    return cuda_available, cuda_version, cudnn_version, gpus


def detect_apple_mps() -> bool:
    """Detect Apple Silicon MPS availability"""
    if platform.system() != "Darwin":
        return False
    
    # Check if running on Apple Silicon
    if platform.machine() not in ("arm64", "aarch64"):
        return False
    
    # Try PyTorch MPS backend
    try:
        import torch
        return hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    except ImportError:
        # Assume MPS available on Apple Silicon even without PyTorch
        return True


def detect_amd_rocm() -> bool:
    """Detect AMD ROCm availability"""
    # Check for rocm-smi
    rocm_smi = shutil.which("rocm-smi")
    if rocm_smi:
        try:
            result = subprocess.run([rocm_smi], capture_output=True, timeout=10)
            if result.returncode == 0:
                return True
        except:
            pass
    
    # Check for HIP runtime
    hip_path = os.environ.get("HIP_PATH") or os.path.exists("/opt/rocm")
    return bool(hip_path)


def get_pytorch_recommendation(cuda_available: bool, cuda_version: Optional[str],
                               mps_available: bool, rocm_available: bool) -> tuple:
    """Determine recommended PyTorch variant and index URL"""
    
    if cuda_available and cuda_version:
        # Map CUDA version to PyTorch wheel
        major_minor = cuda_version.split(".")[:2]
        cuda_key = "".join(major_minor)
        
        # Available CUDA versions for PyTorch
        cuda_map = {
            "126": ("cu126", "https://download.pytorch.org/whl/cu126"),
            "124": ("cu124", "https://download.pytorch.org/whl/cu124"),
            "121": ("cu121", "https://download.pytorch.org/whl/cu121"),
            "118": ("cu118", "https://download.pytorch.org/whl/cu118"),
        }
        
        # Find best match (prefer exact, then lower)
        for key in ["126", "124", "121", "118"]:
            if int(cuda_key) >= int(key):
                return cuda_map[key]
        
        # Fallback to latest
        return "cu126", "https://download.pytorch.org/whl/cu126"
    
    elif mps_available:
        # Apple Silicon uses default PyPI (MPS is auto-enabled)
        return "mps", None
    
    elif rocm_available:
        return "rocm", "https://download.pytorch.org/whl/rocm6.2"
    
    else:
        # CPU only
        if platform.system() == "Linux":
            return "cpu", "https://download.pytorch.org/whl/cpu"
        else:
            # Windows/macOS CPU uses default PyPI
            return "cpu", None


def detect_hardware() -> HardwareInfo:
    """
    Perform complete hardware detection.
    Returns HardwareInfo dataclass with all system information.
    """
    # OS Info
    os_name, os_version, architecture = get_os_info()
    
    # CPU Info
    cpu_name, cpu_cores, cpu_threads = get_cpu_info()
    
    # Memory Info
    ram_total, ram_available = get_memory_info()
    
    # GPU Detection
    cuda_available, cuda_version, cudnn_version, gpus = detect_nvidia_cuda()
    mps_available = detect_apple_mps()
    rocm_available = detect_amd_rocm()
    
    # Check CUDA version compatibility (Require >= 12.4)
    cuda_compatible = True
    driver_warning = None
    
    if cuda_available and cuda_version:
        try:
            # Simple float parsing for "12.4" or "12.6"
            # Extracts major.minor from string
            parts = cuda_version.split(".")
            if len(parts) >= 2:
                ver_float = float(f"{parts[0]}.{parts[1]}")
                if ver_float < 12.4:
                    cuda_compatible = False
                    driver_warning = (
                        f"Your NVIDIA driver (CUDA {cuda_version}) is too old.\n"
                        f"PyPottery requires CUDA 12.4 or newer.\n"
                        f"Please update your NVIDIA drivers."
                    )
        except Exception:
            pass  # Parsing failed, assume compatible
    
    
    # Get PyTorch recommendation
    variant, index_url = get_pytorch_recommendation(
        cuda_available, cuda_version, mps_available, rocm_available
    )
    
    return HardwareInfo(
        os_name=os_name,
        os_version=os_version,
        architecture=architecture,
        cpu_name=cpu_name,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        ram_total_gb=ram_total,
        ram_available_gb=ram_available,
        cuda_available=cuda_available,
        cuda_version=cuda_version,
        cuda_compatible=cuda_compatible,
        driver_warning=driver_warning,
        cudnn_version=cudnn_version,
        mps_available=mps_available,
        rocm_available=rocm_available,
        gpus=gpus,
        recommended_pytorch_variant=variant,
        pytorch_index_url=index_url
    )


def get_hardware_summary(info: HardwareInfo) -> str:
    """Generate a human-readable hardware summary"""
    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║                    HARDWARE DETECTION                        ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ OS: {info.os_name} {info.architecture}".ljust(63) + "║",
        f"║ CPU: {info.cpu_name[:50]}".ljust(63) + "║",
        f"║ Cores: {info.cpu_cores} physical, {info.cpu_threads} logical".ljust(63) + "║",
        f"║ RAM: {info.ram_total_gb:.1f} GB total, {info.ram_available_gb:.1f} GB available".ljust(63) + "║",
        "╠══════════════════════════════════════════════════════════════╣",
    ]
    
    if info.cuda_available:
        lines.append(f"║ ✅ CUDA: {info.cuda_version}".ljust(63) + "║")
        for gpu in info.gpus:
            lines.append(f"║    GPU {gpu.index}: {gpu.name[:45]}".ljust(63) + "║")
            lines.append(f"║         VRAM: {gpu.memory_total_mb} MB".ljust(63) + "║")
    elif info.mps_available:
        lines.append("║ ✅ Apple MPS (Metal Performance Shaders)".ljust(63) + "║")
    elif info.rocm_available:
        lines.append("║ ✅ AMD ROCm".ljust(63) + "║")
    else:
        lines.append("║ ❌ No GPU acceleration detected (CPU only)".ljust(63) + "║")
    
    lines.extend([
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ Recommended PyTorch: {info.recommended_pytorch_variant}".ljust(63) + "║",
        "╚══════════════════════════════════════════════════════════════╝",
    ])
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Test hardware detection
    print("Detecting hardware...")
    info = detect_hardware()
    print(get_hardware_summary(info))
    print("\nJSON output:")
    import json
    print(json.dumps(info.to_dict(), indent=2))
