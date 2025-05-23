"""
PokeTibia Bot - Memory Management Module
Enhanced memory access system with better error handling, caching, 
and robustness for the PokeTibia Bot.
"""
import ctypes
import psutil
import time
import logging
import threading
from typing import Dict, List, Tuple, Any, Union, Optional, Type
from ctypes import wintypes

# Core memory access functionality


# Constants for memory access
PROCESS_ALL_ACCESS = 0x1F0FFF


class ProcessError(Exception):
    """Base exception for process-related errors."""
    pass


class ProcessNotFoundError(ProcessError):
    """Exception raised when a process is not found."""
    pass


class MemoryAccessError(ProcessError):
    """Exception raised when memory access fails."""
    pass


class MemoryManager:
    """
    Enhanced memory manager with robust error handling, caching, and reconnection.
    Implements the MemoryProvider interface from the architecture.
    """
    def __init__(self, module_name: str, auto_reconnect: bool = True, cache_enabled: bool = True):
        """
        Initialize the memory manager.
        
        Args:
            module_name: Name of the process executable
            auto_reconnect: Whether to automatically attempt reconnection
            cache_enabled: Whether to enable memory read caching
        """
        self.module_name = module_name
        self.auto_reconnect = auto_reconnect
        self.cache_enabled = cache_enabled
        self.logger = logging.getLogger(__name__)
        
        # Memory cache
        self.memory_cache = {}
        self.cache_timestamp = {}
        self.cache_duration = 0.1  # 100ms cache duration
        self.cache_timeout = 10.0   # 10s maximum cache lifetime
        
        # Connection state
        self.connected = False
        self.pid = None
        self.handle = None
        self.base_addr = None
        self.module_size = None
        self.is_wow64 = False
        self.ptr_type = None
        self.last_connect_attempt = 0
        self.reconnect_interval = 5.0  # 5 seconds between reconnection attempts
        
        # Blocked regions to avoid reading from
        self.blocked_regions = []
        
        # Reconnection monitoring
        self.monitor_thread = None
        self.stop_monitoring = False
        
        # Initialize DLLs
        self._init_dlls()
        
        # Attempt initial connection
        self.initialize()
    
    def _init_dlls(self) -> None:
        """Initialize Windows DLLs for memory access."""
        try:
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self.psapi = ctypes.WinDLL("Psapi.dll", use_last_error=True)
        except Exception as e:
            self.logger.error(f"Failed to load required DLLs: {e}")
            raise RuntimeError(f"Failed to load required DLLs: {e}")
    
    def initialize(self) -> bool:
        """
        Initialize the memory manager and connect to the process.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            # Connect to the process
            self._connect()
            
            # Start reconnection monitoring if enabled
            if self.auto_reconnect and not self.monitor_thread:
                self.stop_monitoring = False
                self.monitor_thread = threading.Thread(target=self._reconnection_monitor, daemon=True)
                self.monitor_thread.start()
                self.logger.debug("Reconnection monitoring started")
            
            return self.connected
        except Exception as e:
            self.logger.error(f"Initialization error: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up resources used by the memory manager."""
        # Stop reconnection monitoring
        if self.monitor_thread:
            self.stop_monitoring = True
            self.monitor_thread.join(timeout=1.0)
            self.monitor_thread = None
        
        # Close handle
        self._close_handle()
        
        # Clear cache
        self.memory_cache.clear()
        self.cache_timestamp.clear()
    
    def read_memory(self, address: int, data_type: Type = ctypes.c_int32, 
                   retries: int = 3, delay: float = 0.01, 
                   use_cache: bool = True) -> Any:
        """
        Read a value from memory at the specified address.
        
        Args:
            address: Memory address to read from
            data_type: Type of data to read
            retries: Number of retry attempts
            delay: Delay between retries in seconds
            use_cache: Whether to use cache for this read
            
        Returns:
            The value read from memory
            
        Raises:
            MemoryAccessError: If reading fails after all retries
        """
        # Check if connected
        if not self.connected:
            if self.auto_reconnect:
                self._try_reconnect()
                if not self.connected:
                    raise MemoryAccessError(f"Not connected to process {self.module_name}")
            else:
                raise MemoryAccessError(f"Not connected to process {self.module_name}")
        
        # Check if address is in a blocked region
        for start, end in self.blocked_regions:
            if start <= address <= end:
                raise MemoryAccessError(f"Address {hex(address)} is in a blocked region")
        
        # Check cache if enabled
        cache_key = (address, str(data_type))
        if self.cache_enabled and use_cache:
            current_time = time.time()
            if (cache_key in self.memory_cache and 
                current_time - self.cache_timestamp.get(cache_key, 0) < self.cache_duration):
                return self.memory_cache[cache_key]
            
            # Clear old cache entries
            self._clear_old_cache_entries(current_time)
        
        # Verify address is reasonable
        if not (0 <= address < (2**64)):
            raise ValueError(f"Invalid address: {hex(address)}")
        
        # Attempt to read with retries
        last_error = None
        for i in range(retries):
            try:
                # Create buffer for the data
                buffer = data_type()
                read = ctypes.c_size_t()
                
                # Read the memory
                if not self.kernel32.ReadProcessMemory(
                    self.handle, 
                    ctypes.c_void_p(address), 
                    ctypes.byref(buffer), 
                    ctypes.sizeof(buffer), 
                    ctypes.byref(read)
                ):
                    error_code = ctypes.get_last_error()
                    raise MemoryAccessError(f"Read failed (Error {error_code}): {ctypes.WinError(error_code)}")
                
                # Verify we read the right amount of data
                if read.value != ctypes.sizeof(buffer):
                    raise MemoryAccessError(f"Partial read: {read.value}/{ctypes.sizeof(buffer)} bytes at {hex(address)}")
                
                # Cache the result if enabled
                if self.cache_enabled and use_cache:
                    self.memory_cache[cache_key] = buffer.value
                    self.cache_timestamp[cache_key] = time.time()
                
                return buffer.value
            
            except Exception as e:
                last_error = e
                if i < retries - 1:  # Not the last retry
                    self.logger.debug(f"Read attempt {i+1}/{retries} failed for {hex(address)}: {e}")
                    time.sleep(delay)
                    
                    # Check if we need to reconnect
                    if isinstance(e, MemoryAccessError) and "Handle is invalid" in str(e):
                        self._try_reconnect()
                        if not self.connected:
                            break  # No point retrying if reconnection failed
        
        # If we get here, all attempts failed
        self.logger.error(f"Failed to read {hex(address)} after {retries} attempts")
        if last_error:
            raise last_error
        else:
            raise MemoryAccessError(f"Failed to read memory at {hex(address)}")
    
    def resolve_pointer_chain(self, base_address: int, offsets: List[int]) -> int:
        """
        Resolve a pointer chain starting from the base address.
        
        Args:
            base_address: Base address to start from
            offsets: List of offsets to follow
            
        Returns:
            Final resolved address
            
        Raises:
            MemoryAccessError: If resolving fails
        """
        # Start with the base address
        addr = self.base_addr + base_address if self.base_addr is not None else base_address
        self.logger.debug(f"Resolving pointer chain starting at {hex(addr)}")
        
        # Follow each offset in the chain
        for i, offset in enumerate(offsets):
            # Read the pointer value
            try:
                ptr = self.read_memory(addr, self.ptr_type)
            except MemoryAccessError as e:
                raise MemoryAccessError(f"Failed to resolve pointer at step {i+1}: {e}")
            
            # Apply the offset
            addr = ptr + offset
            self.logger.debug(f"  Step {i+1}: {hex(ptr)} + {hex(offset)} = {hex(addr)}")
            
            # Verify address is reasonable
            if not (0 <= addr < (2**48)):  # 48-bit is typical virtual address space
                raise ValueError(f"Pointer {hex(addr)} seems invalid (out of bounds)")
        
        return addr
    
    def is_process_running(self) -> bool:
        """
        Check if the target process is running.
        
        Returns:
            True if process is running, False otherwise
        """
        if self.pid is None:
            return False
        
        try:
            # Check if process still exists
            process = psutil.Process(self.pid)
            return process.is_running() and process.name().lower() == self.module_name.lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    def clear_cache(self) -> None:
        """Clear the memory read cache."""
        self.memory_cache.clear()
        self.cache_timestamp.clear()
        self.logger.debug("Memory cache cleared")
    
    def _connect(self) -> None:
        """
        Connect to the process and initialize memory access.
        
        Raises:
            ProcessNotFoundError: If process is not found
            MemoryAccessError: If connection fails
        """
        try:
            # Record attempt time
            self.last_connect_attempt = time.time()
            
            # Find process
            self.pid = self._find_process_pid()
            if not self.pid:
                self.connected = False
                raise ProcessNotFoundError(f"Process '{self.module_name}' not found")
            
            # Open process handle
            self.handle = self._open_process(self.pid)
            
            # Detect architecture
            self.is_wow64 = self._detect_wow64(self.handle)
            self.ptr_type = ctypes.c_uint32 if self.is_wow64 else ctypes.c_uint64
            
            # Get module information
            module_info = self._get_module_info(self.handle, self.module_name)
            if module_info:
                self.base_addr, self.module_size = module_info
                self.logger.info(f"Connected to {self.module_name} (PID: {self.pid})" +
                               f", Base address: {hex(self.base_addr)}, Size: {self.module_size}")
            else:
                self.logger.warning(f"Connected to {self.module_name} (PID: {self.pid}) but couldn't get module info")
            
            # Clear cache on new connection
            self.clear_cache()
            
            self.connected = True
        
        except ProcessNotFoundError:
            self.connected = False
            raise
        
        except Exception as e:
            self._close_handle()
            self.connected = False
            raise MemoryAccessError(f"Failed to connect to process: {e}")
    
    def _find_process_pid(self) -> Optional[int]:
        """
        Find the process ID by name.
        
        Returns:
            Process ID or None if not found
        """
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == self.module_name.lower():
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        return None
    
    def _open_process(self, pid: int) -> int:
        """
        Open a handle to the process.
        
        Args:
            pid: Process ID
            
        Returns:
            Process handle
            
        Raises:
            MemoryAccessError: If opening the process fails
        """
        handle = self.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not handle:
            error_code = ctypes.get_last_error()
            raise MemoryAccessError(f"Failed to open process (Error {error_code}): {ctypes.WinError(error_code)}")
        
        return handle
    
    def _detect_wow64(self, handle: int) -> bool:
        """
        Detect if process is 32-bit running on 64-bit system.
        
        Args:
            handle: Process handle
            
        Returns:
            True if process is 32-bit on 64-bit system
        """
        is_wow = wintypes.BOOL()
        self.kernel32.IsWow64Process(handle, ctypes.byref(is_wow))
        return bool(is_wow.value)
    
    def _get_module_info(self, handle: int, module_name: str) -> Optional[Tuple[int, int]]:
        """
        Get information about a module in the process.
        
        Args:
            handle: Process handle
            module_name: Module name
            
        Returns:
            Tuple of (base_address, module_size) or None if not found
            
        Raises:
            MemoryAccessError: If getting module information fails
        """
        try:
            # Define MODULEINFO structure
            class MODULEINFO(ctypes.Structure):
                _fields_ = [
                    ("lpBaseOfDll", wintypes.LPVOID),
                    ("SizeOfImage", wintypes.DWORD),
                    ("EntryPoint", wintypes.LPVOID),
                ]
            
            # Enumerate modules
            hMods = (wintypes.HMODULE * 1024)()
            needed = wintypes.DWORD()
            if not self.psapi.EnumProcessModules(
                handle, ctypes.byref(hMods), ctypes.sizeof(hMods), ctypes.byref(needed)
            ):
                error_code = ctypes.get_last_error()
                raise MemoryAccessError(f"Failed to enumerate modules (Error {error_code}): {ctypes.WinError(error_code)}")
            
            # Find the target module
            count = needed.value // ctypes.sizeof(wintypes.HMODULE)
            for i in range(count):
                mod = hMods[i]
                name_buf = ctypes.create_unicode_buffer(256)
                
                self.psapi.GetModuleBaseNameW(handle, mod, name_buf, ctypes.sizeof(name_buf))
                
                if name_buf.value.lower() == module_name.lower():
                    # Get module information
                    mi = MODULEINFO()
                    self.psapi.GetModuleInformation(handle, mod, ctypes.byref(mi), ctypes.sizeof(mi))
                    return mi.lpBaseOfDll, mi.SizeOfImage
            
            # Module not found
            return None
        
        except Exception as e:
            if isinstance(e, MemoryAccessError):
                raise
            raise MemoryAccessError(f"Failed to get module information: {e}")
    
    def _close_handle(self) -> None:
        """Close the process handle safely."""
        if hasattr(self, 'handle') and self.handle:
            try:
                self.kernel32.CloseHandle(self.handle)
                self.logger.debug("Process handle closed")
            except Exception as e:
                self.logger.warning(f"Error closing handle: {e}")
            
            self.handle = None
    
    def _try_reconnect(self) -> bool:
        """
        Attempt to reconnect to the process.
        
        Returns:
            True if reconnection was successful
        """
        # Check if we tried reconnecting recently
        current_time = time.time()
        if current_time - self.last_connect_attempt < self.reconnect_interval:
            return False
        
        # Close existing handle if any
        self._close_handle()
        
        try:
            self._connect()
            return self.connected
        except Exception as e:
            self.logger.warning(f"Reconnection attempt failed: {e}")
            return False
    
    def _reconnection_monitor(self) -> None:
        """Background thread for monitoring connection and reconnecting as needed."""
        while not self.stop_monitoring:
            try:
                # Check if process is still running
                if self.connected and not self.is_process_running():
                    self.logger.warning(f"Process {self.module_name} is no longer running")
                    self.connected = False
                    self._close_handle()
                
                # Try to reconnect if disconnected
                elif not self.connected:
                    if self._try_reconnect():
                        self.logger.info(f"Successfully reconnected to {self.module_name}")
            
            except Exception as e:
                self.logger.error(f"Error in reconnection monitor: {e}")
            
            # Sleep for a while
            for _ in range(10):  # Check stop flag more frequently
                if self.stop_monitoring:
                    break
                time.sleep(0.1)
    
    def _clear_old_cache_entries(self, current_time: float) -> None:
        """
        Clear cache entries that have exceeded the timeout.
        
        Args:
            current_time: Current time for comparison
        """
        # Find old entries
        old_keys = [
            key for key, timestamp in self.cache_timestamp.items()
            if current_time - timestamp > self.cache_timeout
        ]
        
        # Remove old entries
        for key in old_keys:
            if key in self.memory_cache:
                del self.memory_cache[key]
            if key in self.cache_timestamp:
                del self.cache_timestamp[key]


class SimpleMemoryManager:
    """
    Simplified memory manager for basic memory access.
    Useful for minimal implementations with reduced overhead.
    """
    def __init__(self, module_name: str):
        """
        Initialize the simple memory manager.
        
        Args:
            module_name: Name of the process executable
        """
        self.module_name = module_name
        self.logger = logging.getLogger(__name__)
        
        # Initialize DLLs
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        
        # Connection state
        self.pid = None
        self.handle = None
        
        # Initialize
        self.initialize()
    
    def initialize(self) -> bool:
        """
        Initialize the memory manager and connect to the process.
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            # Find process ID
            self.pid = self._find_process_pid()
            if not self.pid:
                raise ProcessNotFoundError(f"Process '{self.module_name}' not found")
            
            # Open process handle
            self.handle = self._open_process(self.pid)
            
            self.logger.info(f"Connected to {self.module_name} (PID: {self.pid})")
            return True
        
        except Exception as e:
            self.logger.error(f"Initialization error: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up resources used by the memory manager."""
        self._close_handle()
    
    def read_memory(self, address: int, data_type: Type = ctypes.c_int32) -> Any:
        """
        Read a value from memory at the specified address.
        
        Args:
            address: Memory address to read from
            data_type: Type of data to read
            
        Returns:
            The value read from memory
            
        Raises:
            MemoryAccessError: If reading fails
        """
        try:
            # Create buffer for the data
            buffer = data_type()
            read = ctypes.c_size_t()
            
            # Read the memory
            if not self.kernel32.ReadProcessMemory(
                self.handle, 
                ctypes.c_void_p(address), 
                ctypes.byref(buffer), 
                ctypes.sizeof(buffer), 
                ctypes.byref(read)
            ):
                error_code = ctypes.get_last_error()
                raise MemoryAccessError(f"Read failed (Error {error_code}): {ctypes.WinError(error_code)}")
            
            return buffer.value
        
        except Exception as e:
            self.logger.error(f"Failed to read {hex(address)}: {e}")
            if isinstance(e, MemoryAccessError):
                raise
            raise MemoryAccessError(f"Failed to read memory at {hex(address)}: {e}")
    
    def resolve_pointer_chain(self, base_address: int, offsets: List[int]) -> int:
        """
        Resolve a pointer chain starting from the base address.
        
        Args:
            base_address: Base address to start from
            offsets: List of offsets to follow
            
        Returns:
            Final resolved address
            
        Raises:
            MemoryAccessError: If resolving fails
        """
        # Simple implementation without extra features
        addr = base_address
        
        # Follow each offset in the chain
        for i, offset in enumerate(offsets):
            try:
                # Use c_uint32 as default pointer type
                ptr = self.read_memory(addr, ctypes.c_uint32)
                addr = ptr + offset
            except MemoryAccessError as e:
                raise MemoryAccessError(f"Failed to resolve pointer at step {i+1}: {e}")
        
        return addr
    
    
    def is_process_running(self) -> bool:
        """
        Check if the target process is running.
        
        Returns:
            True if process is running, False otherwise
        """
        if self.pid is None:
            return False
        
        try:
            process = psutil.Process(self.pid)
            return process.is_running() and process.name().lower() == self.module_name.lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    def _find_process_pid(self) -> Optional[int]:
        """
        Find the process ID by name.
        
        Returns:
            Process ID or None if not found
        """
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == self.module_name.lower():
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        return None
    
    def _open_process(self, pid: int) -> int:
        """
        Open a handle to the process.
        
        Args:
            pid: Process ID
            
        Returns:
            Process handle
            
        Raises:
            MemoryAccessError: If opening the process fails
        """
        handle = self.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not handle:
            error_code = ctypes.get_last_error()
            raise MemoryAccessError(f"Failed to open process (Error {error_code}): {ctypes.WinError(error_code)}")
        
        return handle
    
    def _close_handle(self) -> None:
        """Close the process handle safely."""
        if hasattr(self, 'handle') and self.handle:
            try:
                self.kernel32.CloseHandle(self.handle)
                self.logger.debug("Process handle closed")
            except Exception as e:
                self.logger.warning(f"Error closing handle: {e}")
            
            self.handle = None


# Factory function for creating memory managers
def get_memory_manager(module_name: str, simple: bool = False, 
                       auto_reconnect: bool = True, cache_enabled: bool = True):
    """
    Create and initialize a memory manager for the specified process.
    
    Args:
        module_name: Name of the process executable
        simple: Whether to use SimpleMemoryManager (less features but smaller overhead)
        auto_reconnect: Whether to enable auto reconnection (ignored for SimpleMemoryManager)
        cache_enabled: Whether to enable memory cache (ignored for SimpleMemoryManager)
        
    Returns:
        MemoryProvider: Initialized memory manager
        
    Raises:
        ProcessNotFoundError: If process is not found
        MemoryAccessError: If connection fails
    """
    if simple:
        return SimpleMemoryManager(module_name)
    else:
        return MemoryManager(module_name, auto_reconnect, cache_enabled)


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Example usage
    try:
        # Try to find the process name from command line
        import sys
        process_name = sys.argv[1] if len(sys.argv) > 1 else "PokeAlliance_dx.exe"
        
        # Create memory manager
        memory = get_memory_manager(process_name)
        
        # Basic info
        print(f"Connected to {process_name} (PID: {memory.pid})")
        print(f"Base address: {hex(memory.base_addr) if memory.base_addr else 'Unknown'}")
        print(f"Module size: {memory.module_size if memory.module_size else 'Unknown'}")
        print(f"Architecture: {'32-bit (WOW64)' if memory.is_wow64 else '64-bit'}")
        
        # Keep running for reconnection testing
        print("\nMemory manager running. Press Ctrl+C to exit...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting...")
        
    except ProcessNotFoundError as e:
        print(f"Error: {e}")
        print(f"Make sure {process_name} is running")
    except Exception as e:
        print(f"Error: {e}")