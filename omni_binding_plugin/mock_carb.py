"""
Mock carb module for testing USD binding system outside of Omniverse
This provides the same interface as the real carb module but with simple print statements
"""

def log_info(message):
    """Mock carb.log_info"""
    print(f"[INFO] {message}")

def log_warn(message):
    """Mock carb.log_warn"""
    print(f"[WARN] {message}")

def log_error(message):
    """Mock carb.log_error"""
    print(f"[ERROR] {message}")

def log_verbose(message):
    """Mock carb.log_verbose"""
    print(f"[VERBOSE] {message}")

# For compatibility with any other carb usage
class MockCarb:
    @staticmethod
    def log_info(message):
        print(f"[INFO] {message}")
    
    @staticmethod 
    def log_warn(message):
        print(f"[WARN] {message}")
        
    @staticmethod
    def log_error(message):
        print(f"[ERROR] {message}")
        
    @staticmethod
    def log_verbose(message):
        print(f"[VERBOSE] {message}")

# Create a singleton instance
_mock_carb = MockCarb()

# Export the functions at module level
__all__ = ['log_info', 'log_warn', 'log_error', 'log_verbose']
